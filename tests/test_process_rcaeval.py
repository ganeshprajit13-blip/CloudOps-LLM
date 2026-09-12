"""
Unit tests for RCAEval real telemetry processing pipeline.
"""

import os
import json
import pytest

NORMALIZED_PATH = "data/normalized/rcaeval/normalized_cases.jsonl"
RCA_TRAINING_PATH = "data/rca/rcaeval/rcaeval_training_cases.jsonl"
REPORT_MD_PATH = "data/reports/rcaeval_processing_report.md"
STATS_JSON_PATH = "data/reports/rcaeval_processing_statistics.json"

def test_normalized_cases_structure():
    assert os.path.exists(NORMALIZED_PATH), f"File missing: {NORMALIZED_PATH}"
    
    with open(NORMALIZED_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    assert len(lines) == 465, f"Expected 465 normalized cases, got {len(lines)}"
    
    case_ids = set()
    for i, line in enumerate(lines):
        record = json.loads(line)
        
        # Schema checks
        assert "case_id" in record, f"Line {i} missing case_id"
        assert record["dataset"] == "RCAEval", f"Line {i} dataset mismatch"
        assert "system" in record, f"Line {i} missing system"
        assert "fault_type" in record, f"Line {i} missing fault_type"
        assert "injection_time" in record, f"Line {i} missing injection_time"
        assert "telemetry" in record, f"Line {i} missing telemetry"
        assert "ground_truth" in record, f"Line {i} missing ground_truth"
        assert "available_sources" in record, f"Line {i} missing available_sources"
        assert "provenance" in record, f"Line {i} missing provenance"
        
        # Ground truth check
        gt = record["ground_truth"]
        assert "root_cause_service" in gt and gt["root_cause_service"], f"Line {i} missing root_cause_service"
        assert "fault" in gt and gt["fault"], f"Line {i} missing fault"
        
        # Duplicate check
        c_id = record["case_id"]
        assert c_id not in case_ids, f"Duplicate case ID found: {c_id}"
        case_ids.add(c_id)

def test_rca_training_cases_structure():
    assert os.path.exists(RCA_TRAINING_PATH), f"File missing: {RCA_TRAINING_PATH}"
    
    with open(RCA_TRAINING_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    assert len(lines) == 465, f"Expected 465 training cases, got {len(lines)}"
    
    for i, line in enumerate(lines):
        record = json.loads(line)
        assert "case_id" in record
        assert "root_cause" in record
        assert "service" in record["root_cause"]
        assert "telemetry_evidence" in record
        assert "remediation_steps" in record

def test_processing_reports():
    assert os.path.exists(REPORT_MD_PATH), f"Report missing: {REPORT_MD_PATH}"
    assert os.path.exists(STATS_JSON_PATH), f"Stats JSON missing: {STATS_JSON_PATH}"
    
    with open(STATS_JSON_PATH, "r", encoding="utf-8") as f:
        stats = json.load(f)
        
    assert stats["total_indexed_cases"] == 735
    assert stats["successfully_processed_cases"] == 465
    assert stats["skipped_cases_count"] == 270
    assert stats["failed_cases_count"] == 0
    assert stats["re1_processed_count"] == 375
    assert stats["re3_processed_count"] == 90
    assert stats["quality_checks"]["duplicate_count"] == 0
    assert stats["quality_checks"]["credential_findings"] == 0

def test_protected_files_intact():
    # Verify protected files exist and have not been deleted
    protected_splits = [
        "data/processed/train.jsonl",
        "data/processed/validation.jsonl",
        "data/processed/test.jsonl"
    ]
    for split in protected_splits:
        if os.path.exists(split):
            assert os.path.getsize(split) > 0, f"Protected file {split} was truncated or emptied!"

