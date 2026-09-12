"""
Unit Test Suite for Phase 5B: Inference, Safe JSON Extraction, Validation, and Evaluation.
"""

import os
import sys
import json
import pytest
from pathlib import Path

# Add project root directory to python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from model.inference import (
    safe_extract_json,
    validate_diagnosis_schema,
    enforce_advisory_safety,
    generate_diagnosis,
    FORBIDDEN_AUTONOMOUS_TERMS,
)
from model.evaluate import CloudOpsEvaluator


def test_safe_extract_json():
    """Test extracting JSON from various text formats."""
    # Plain JSON string
    raw_json = '{"problem": "Test issue", "confidence": 0.9}'
    parsed = safe_extract_json(raw_json)
    assert parsed is not None
    assert parsed["problem"] == "Test issue"

    # Markdown json code block
    markdown_json = "Here is the diagnosis:\n```json\n{\n  \"problem\": \"Codeblock issue\",\n  \"confidence\": 0.8\n}\n```"
    parsed_md = safe_extract_json(markdown_json)
    assert parsed_md is not None
    assert parsed_md["problem"] == "Codeblock issue"

    # Invalid text
    invalid_text = "This is not JSON text at all."
    assert safe_extract_json(invalid_text) is None


def test_validate_diagnosis_schema():
    """Test diagnosis schema validation rules."""
    valid_data = {
        "problem": "Service down",
        "probable_root_cause": "Port 80 blocked",
        "evidence": ["Security group inbound rules"],
        "impact": "Users get connection timeout",
        "recommendation": "Check port 80 rule",
        "confidence": 0.85,
    }
    is_valid, err = validate_diagnosis_schema(valid_data)
    assert is_valid is True
    assert err is None

    # Missing field
    invalid_data = valid_data.copy()
    del invalid_data["recommendation"]
    is_valid, err = validate_diagnosis_schema(invalid_data)
    assert is_valid is False
    assert "recommendation" in err

    # Out of range confidence
    bad_conf_data = valid_data.copy()
    bad_conf_data["confidence"] = 1.5
    is_valid, err = validate_diagnosis_schema(bad_conf_data)
    assert is_valid is False
    assert "confidence" in err.lower()


def test_enforce_advisory_safety():
    """Test detecting and sanitizing autonomous execution claims."""
    unsafe_data = {
        "problem": "Security Group port 443 closed",
        "probable_root_cause": "Port missing",
        "evidence": [],
        "impact": "Traffic blocked",
        "recommendation": "I fixed the Security Group rule.",
        "confidence": 0.9,
    }
    sanitized = enforce_advisory_safety(unsafe_data)
    rec = sanitized["recommendation"].lower()
    assert "i fixed" not in rec or "review" in rec
    assert "consider taking corrective action" in rec or "review" in rec


def test_generate_diagnosis_fallback():
    """Test generate_diagnosis handling with fallback heuristic."""
    question = "Why is my website unreachable?"
    context = {"security_groups": [{"inbound_rules": []}]}

    result = generate_diagnosis(
        model=None,
        tokenizer=None,
        incident_query=question,
        cloud_context=context,
        force_fallback=True,
    )

    assert "error" not in result
    assert "problem" in result
    assert "probable_root_cause" in result
    assert isinstance(result["evidence"], list)
    assert 0.0 <= result["confidence"] <= 1.0


def test_evaluator_runs():
    """Test CloudOpsEvaluator instantiation and execution."""
    evaluator = CloudOpsEvaluator(model=None, tokenizer=None)
    summary, results = evaluator.evaluate(limit=2)

    assert isinstance(summary, dict)
    assert "valid_json_percentage" in summary
    assert "schema_validity_percentage" in summary
    assert isinstance(results, list)
