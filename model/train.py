import datetime
import os
import logging
from pathlib import Path
from typing import Any, Dict
import torch

logger = logging.getLogger(__name__)

from model.config import (
    BATCH_SIZE,
    GRADIENT_ACCUMULATION_STEPS,
    LEARNING_RATE,
    MAX_SEQUENCE_LENGTH,
    MODEL_MODE,
    MODEL_NAME,
    MODEL_OUTPUT_DIR,
    NUM_EPOCHS,
    TEST_FILE,
    TRAIN_FILE,
    VALIDATION_FILE,
)
from model.dataset import load_jsonl
from model.lora import apply_lora, create_lora_config, find_target_modules, get_parameter_count_info
from model.model_loader import get_torch_device, load_base_model
from model.tokenizer import format_instruction_text, load_tokenizer
from model.utils import print_hardware_report, save_adapter_artifacts


class CloudOpsSFTDataset(torch.utils.data.Dataset):
    """
    Supervised Fine-Tuning PyTorch Dataset for Causal LM.
    Provides per-example dictionary containing input_ids, attention_mask, and labels (-100 for padding).
    """

    def __init__(self, examples: list, tokenizer: Any, max_length: int = MAX_SEQUENCE_LENGTH):
        self.features = []
        pad_id = getattr(tokenizer, "pad_token_id", None)
        if pad_id is None:
            pad_id = getattr(tokenizer, "eos_token_id", 0)

        for ex in examples:
            instruction = ex.get("instruction", "")
            input_text = ex.get("input", "")
            output_text = ex.get("output", "")

            prompt_text = format_instruction_text(instruction, input_text)
            full_text = f"{prompt_text}\n\nDiagnosis Output:\n{output_text}"

            encoded = tokenizer(
                full_text,
                truncation=True,
                max_length=max_length,
                padding=False,
                return_tensors=None,
            )

            input_ids = encoded.get("input_ids", [1, 2, 3])
            attention_mask = encoded.get("attention_mask", [1, 1, 1])

            # Labels for Causal LM: pad tokens set to -100 so loss ignores them
            labels = [
                token_id if (mask == 1 and token_id != pad_id) else -100
                for token_id, mask in zip(input_ids, attention_mask)
            ]

            self.features.append({
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": labels,
            })

    def __len__(self) -> int:
        return len(self.features)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        item = self.features[idx]
        return {
            "input_ids": torch.tensor(item["input_ids"], dtype=torch.long),
            "attention_mask": torch.tensor(item["attention_mask"], dtype=torch.long),
            "labels": torch.tensor(item["labels"], dtype=torch.long),
        }


class CloudOpsTrainer:
    """Supervised fine-tuning trainer for CloudOps LLM."""

    def __init__(self, output_dir: Path | None = None, dry_run: bool = False):
        self.output_dir = output_dir or MODEL_OUTPUT_DIR
        self.dry_run = dry_run
        if dry_run:
            os.environ["DRY_RUN"] = "1"
        self.device = get_torch_device()

    def prepare_dataset(self, examples: list, tokenizer: Any) -> CloudOpsSFTDataset:
        """Tokenizes instruction tuning examples into PyTorch SFT Dataset."""
        return CloudOpsSFTDataset(examples, tokenizer, max_length=MAX_SEQUENCE_LENGTH)

    def run_training(self) -> Dict[str, Any]:
        """Runs the complete training and adapter export pipeline."""
        logger.info("=" * 60)
        logger.info("STARTING CLOUDOPS LLM PHASE 5A TRAINING PIPELINE")
        logger.info("=" * 60)

        # 1. Hardware Report
        print_hardware_report()

        # 2. Dataset Loading (Train & Validation only)
        logger.info(f"Loading datasets: Train={TRAIN_FILE.name}, Val={VALIDATION_FILE.name}")
        train_examples = load_jsonl(TRAIN_FILE)
        val_examples = load_jsonl(VALIDATION_FILE)
        test_examples = load_jsonl(TEST_FILE)

        logger.info(f"Dataset Counts -> Train: {len(train_examples)} | Val: {len(val_examples)} | Test: {len(test_examples)} (Held Out)")

        # 3. Load Tokenizer
        tokenizer = load_tokenizer()

        # 4. Load Base Model & Apply LoRA/QLoRA
        model, mode = load_base_model()
        target_modules = find_target_modules(model)

        lora_config = create_lora_config(target_modules=target_modules)
        peft_model = apply_lora(model, lora_config)

        total_p, train_p, pct = get_parameter_count_info(peft_model)

        metadata = {
            "model_name": MODEL_NAME,
            "mode": MODEL_MODE,
            "target_modules": target_modules,
            "total_parameters": total_p,
            "trainable_parameters": train_p,
            "trainable_percentage": pct,
            "train_examples_count": len(train_examples),
            "val_examples_count": len(val_examples),
            "epochs": NUM_EPOCHS,
            "learning_rate": LEARNING_RATE,
            "batch_size": BATCH_SIZE,
            "gradient_accumulation_steps": GRADIENT_ACCUMULATION_STEPS,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "dry_run": self.dry_run,
        }

        # 5. Prepare SFT Datasets
        train_dataset = self.prepare_dataset(train_examples, tokenizer)
        val_dataset = self.prepare_dataset(val_examples, tokenizer)

        if self.dry_run or not torch.cuda.is_available():
            logger.info("Dry run / CPU mode active: Validating dataset preparation & setup without heavy GPU training.")
            save_adapter_artifacts(peft_model, tokenizer, self.output_dir, metadata)
            logger.info("Phase 5A training setup & adapter artifact export completed successfully.")
            return metadata

        # Execute training on GPU using Hugging Face Trainer
        from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling

        logger.info("Initializing Hugging Face Trainer for GPU fine-tuning...")

        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False,
            pad_to_multiple_of=8,
        )

        training_args = TrainingArguments(
            output_dir=str(self.output_dir / "checkpoints"),
            num_train_epochs=NUM_EPOCHS,
            per_device_train_batch_size=BATCH_SIZE,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
            learning_rate=LEARNING_RATE,
            fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
            logging_steps=10,
            save_strategy="epoch",
            eval_strategy="epoch",
            save_total_limit=2,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            gradient_checkpointing=False,
            optim="adamw_torch",
            report_to="none",
        )

        trainer = Trainer(
            model=peft_model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            data_collator=data_collator,
        )

        logger.info("Starting model fine-tuning...")
        trainer.train()

        save_adapter_artifacts(peft_model, tokenizer, self.output_dir, metadata)
        logger.info("Phase 5A training finished cleanly.")

        return metadata
