import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import torch
import torch.nn as nn

from model.config import BASE_MODEL_NAME, LORA_ALPHA, LORA_DROPOUT, LORA_R, MODEL_MODE
from model.lora import create_lora_config, find_target_modules, get_parameter_count_info
from model.tokenizer import format_instruction_text
from model.train import CloudOpsTrainer
from model.utils import get_hardware_info


class DummyQwenLayer(nn.Module):

    def __init__(self):
        super().__init__()
        self.q_proj = nn.Linear(10, 10)
        self.k_proj = nn.Linear(10, 10)
        self.v_proj = nn.Linear(10, 10)
        self.o_proj = nn.Linear(10, 10)


class DummyQwenModel(nn.Module):

    def __init__(self):
        super().__init__()
        self.layer = DummyQwenLayer()


def test_model_config():
    assert BASE_MODEL_NAME == "Qwen/Qwen2.5-3B-Instruct"
    assert MODEL_MODE in ["qlora", "lora"]
    assert LORA_R == 16
    assert LORA_ALPHA == 32
    assert LORA_DROPOUT == 0.05


def test_hardware_detection():
    hw = get_hardware_info()
    assert "cuda_available" in hw
    assert "device_name" in hw
    assert isinstance(hw["cuda_available"], bool)


def test_find_target_modules():
    dummy_model = DummyQwenModel()
    targets = find_target_modules(dummy_model)
    assert "q_proj" in targets
    assert "v_proj" in targets
    assert "k_proj" in targets
    assert "o_proj" in targets


def test_lora_config_creation():
    config = create_lora_config(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=["q_proj", "v_proj"])
    assert config.r == 16
    assert config.lora_alpha == 32
    assert config.lora_dropout == 0.05
    assert "q_proj" in config.target_modules


def test_parameter_count_info():
    dummy_model = DummyQwenModel()
    total_p, train_p, pct = get_parameter_count_info(dummy_model)
    assert total_p > 0
    assert train_p == total_p
    assert pct == 100.0


def test_tokenizer_prompt_formatting():
    formatted = format_instruction_text("Analyze EC2 failure", "EC2 instance i-123 is stopped.")
    assert "CloudOps LLM" in formatted
    assert "Task: Analyze EC2 failure" in formatted
    assert "Infrastructure Context:\nEC2 instance i-123 is stopped." in formatted


def test_trainer_dry_run(tmp_path):
    out_dir = tmp_path / "adapters"
    trainer = CloudOpsTrainer(output_dir=out_dir, dry_run=True)
    meta = trainer.run_training()

    assert meta["model_name"] == BASE_MODEL_NAME
    assert meta["train_examples_count"] > 0
    assert meta["dry_run"] is True
    assert (out_dir / "training_metadata.json").exists()


def test_prepare_dataset_sft_dataset():
    from model.tokenizer import load_tokenizer
    from model.train import CloudOpsTrainer, CloudOpsSFTDataset

    tokenizer = load_tokenizer()
    trainer = CloudOpsTrainer(dry_run=True)

    examples = [
        {
            "instruction": "Troubleshoot EC2 outage.",
            "input": "EC2 instance is stopped.",
            "output": '{"problem": "EC2 instance stopped", "confidence": 0.95}'
        }
    ]

    dataset = trainer.prepare_dataset(examples, tokenizer)
    assert isinstance(dataset, CloudOpsSFTDataset)
    assert len(dataset) == 1

    sample = dataset[0]
    assert "input_ids" in sample
    assert "attention_mask" in sample
    assert "labels" in sample

    assert isinstance(sample["input_ids"], torch.Tensor)
    assert isinstance(sample["attention_mask"], torch.Tensor)
    assert isinstance(sample["labels"], torch.Tensor)

    assert sample["input_ids"].ndim == 1
    assert sample["attention_mask"].ndim == 1
    assert sample["labels"].ndim == 1
    assert sample["input_ids"].shape[0] == sample["labels"].shape[0]
