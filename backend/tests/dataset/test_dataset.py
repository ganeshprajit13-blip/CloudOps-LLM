import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from model.config import BASE_MODEL_NAME, TRAIN_FILE
from model.dataset import generate_synthetic_dataset, scan_for_secrets, split_dataset, validate_example
from model.prompts import CLOUDOPS_SYSTEM_PROMPT, format_instruction_prompt



def test_model_config():
    assert BASE_MODEL_NAME == "Qwen/Qwen2.5-3B-Instruct"
    assert TRAIN_FILE.name == "train.jsonl"


def test_validate_example_valid():
    valid_ex = {
        "instruction": "Analyze this AWS incident.",
        "input": "EC2 is running. Inbound TCP port 443 is missing from Security Group sg-123.",
        "output": json.dumps({
            "problem": "HTTPS website is unreachable",
            "probable_root_cause": "Security Group sg-123 is likely blocking TCP 443",
            "evidence": ["EC2 instance is running", "TCP 443 missing from sg-123"],
            "impact": "Users cannot connect via HTTPS",
            "recommendation": "Review sg-123 inbound rules and allow TCP 443",
            "confidence": 0.94
        })
    }
    is_valid, errors = validate_example(valid_ex)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_example_invalid_confidence():
    invalid_ex = {
        "instruction": "Analyze incident.",
        "input": "EC2 running.",
        "output": json.dumps({
            "problem": "Issue",
            "probable_root_cause": "Cause",
            "evidence": ["Ev1"],
            "impact": "Impact",
            "recommendation": "Rec",
            "confidence": 1.5  # Invalid > 1.0
        })
    }
    is_valid, errors = validate_example(invalid_ex)
    assert is_valid is False
    assert any("Confidence must be a float between 0.0 and 1.0" in e for e in errors)


def test_validate_example_causal_evidence_failure():
    causal_ex = {
        "instruction": "Analyze incident.",
        "input": "EC2 running.",
        "output": json.dumps({
            "problem": "Issue",
            "probable_root_cause": "Cause",
            "evidence": ["The Security Group is the root cause of outage"],  # Causal claim in evidence
            "impact": "Impact",
            "recommendation": "Rec",
            "confidence": 0.90
        })
    }
    is_valid, errors = validate_example(causal_ex)
    assert is_valid is False
    assert any("Evidence contains causal claim" in e for e in errors)


def test_secret_scanner():
    text_with_key = "Access key is AKIA1234567890ABCDEF for test account."
    found = scan_for_secrets(text_with_key)
    assert len(found) == 1
    assert found[0] == "AKIA1234567890ABCDEF"


def test_dataset_splitting():
    raw = generate_synthetic_dataset(50)
    train_set, val_set, test_set = split_dataset(raw, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=42)

    assert len(train_set) == 40
    assert len(val_set) == 5
    assert len(test_set) == 5

    # Test data leakage prevention
    train_inputs = {(ex["instruction"], ex["input"]) for ex in train_set}
    val_inputs = {(ex["instruction"], ex["input"]) for ex in val_set}
    test_inputs = {(ex["instruction"], ex["input"]) for ex in test_set}

    assert len(train_inputs.intersection(val_inputs)) == 0
    assert len(train_inputs.intersection(test_inputs)) == 0
    assert len(val_inputs.intersection(test_inputs)) == 0


def test_prompt_formatting():
    formatted = format_instruction_prompt("Analyze incident", "EC2 running")
    assert "CloudOps LLM" in formatted
    assert "Task: Analyze incident" in formatted
    assert "Infrastructure Context:\nEC2 running" in formatted


def test_prompt_concise_and_valid_json_constraints():
    """Verify that CLOUDOPS_SYSTEM_PROMPT enforces concise evidence and strict valid JSON output."""
    prompt = CLOUDOPS_SYSTEM_PROMPT
    assert "raw JSON ONLY" in prompt
    assert "No markdown code fences" in prompt or "no ```json" in prompt
    assert "maximum 3 to 5 concise items" in prompt or "3-5" in prompt or "3 to 5" in prompt
    assert "grounded in the input" in prompt
    assert "within 512 tokens" in prompt or "concise and compact" in prompt
    assert "close the JSON object" in prompt

