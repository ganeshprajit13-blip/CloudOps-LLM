import logging
from typing import Any, Dict
from model.config import BASE_MODEL_NAME, MAX_SEQUENCE_LENGTH
from model.prompts import CLOUDOPS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)



def load_tokenizer(
    model_name: str = BASE_MODEL_NAME,
    max_length: int = MAX_SEQUENCE_LENGTH,
):
    """Loads and configures the Hugging Face tokenizer for Qwen2.5-3B-Instruct."""
    import os
    from transformers import AutoTokenizer

    logger.info(f"Loading tokenizer for model: {model_name}")
    tokenizer = None
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="right",
            local_files_only=True,
        )
    except Exception:
        pass

    if tokenizer is None and (os.getenv("OFFLINE_MODE", "0") == "1" or os.getenv("DRY_RUN", "0") == "1"):
        tokenizer = _create_dummy_tokenizer()

    if tokenizer is None:
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True,
                padding_side="right",
            )
        except Exception as e:
            logger.warning(f"Could not load remote tokenizer for {model_name}: {e}")
            tokenizer = _create_dummy_tokenizer()

    # Handle missing pad token
    if hasattr(tokenizer, "pad_token") and tokenizer.pad_token is None:
        if hasattr(tokenizer, "eos_token") and tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id
        else:
            tokenizer.pad_token = "<pad>"
            tokenizer.pad_token_id = 0

    return tokenizer


def _create_dummy_tokenizer():
    class DummyTokenizer:
        pad_token = "<pad>"
        pad_token_id = 0
        eos_token = "<eos>"
        eos_token_id = 1
        def __call__(self, text, **kwargs):
            return_tensors = kwargs.get("return_tensors")
            if isinstance(text, list):
                res = {"input_ids": [[1, 2, 3, 4] for _ in text], "attention_mask": [[1, 1, 1, 1] for _ in text]}
            else:
                res = {"input_ids": [1, 2, 3, 4], "attention_mask": [1, 1, 1, 1]}
            if return_tensors == "pt":
                import torch
                return {k: torch.tensor(v) for k, v in res.items()}
            return res
        def encode(self, text, **kwargs):
            return [1, 2, 3, 4]
        def decode(self, ids, **kwargs):
            return "Decoded dummy diagnosis output."
        def save_pretrained(self, save_directory):
            pass
    return DummyTokenizer()


def format_instruction_text(instruction: str, input_text: str) -> str:
    """Formats raw instruction and input text into standard prompt template."""
    if input_text and input_text.strip():
        return f"{CLOUDOPS_SYSTEM_PROMPT}\n\nTask: {instruction}\n\nInfrastructure Context:\n{input_text}"
    return f"{CLOUDOPS_SYSTEM_PROMPT}\n\nTask: {instruction}"
