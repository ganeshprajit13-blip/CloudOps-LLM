"""
Unit tests for Final Combined CloudOps Training Dataset.
"""

import os
import json
import pytest

COMBINED_DIR = "data/processed/combined"
ALL_CASES_PATH = os.path.join(COMBINED_DIR, "all_cases.jsonl")
TRAIN_PATH = os.path.join(COMBINED_DIR, "train.jsonl")
VAL_PATH = os.path.join(COMBINED_DIR, "validation.jsonl")
TEST_PATH = os.path.join(COMBINED_DIR, "test.jsonl")
MANIFEST_PATH = os.path.join(COMBINED_DIR, "dataset_manifest.json")

REPORT_MD_PATH = "data/reports/final_dataset_coverage.md"
STATS_JSON_PATH = "data/reports/final_dataset_statistics.json"

def test_combined_files_exist():
    assert os.path.exists(ALL_CASES_PATH), f"Missing: {ALL_CASES_PATH}"
    assert os.path.exists(TRAIN_PATH), f"Missing: {TRAIN_PATH}"
    assert os.path.exists(VAL_PATH), f"Missing: {VAL_PATH}"
    assert os.path.exists(TEST_PATH), f"Missing: {TEST_PATH}"
    assert os.path.exists(MANIFEST_PATH), f"Missing: {MANIFEST_PATH}"

def test_total_cases_and_splits_match():
    with open(ALL_CASES_PATH, "r", encoding="utf-8") as f:
        all_cases = [json.loads(line) for line in f if line.strip()]
        
    with open(TRAIN_PATH, "r", encoding="utf-8") as f:
        train_cases = [json.loads(line) for line in f if line.strip()]
        
    with open(VAL_PATH, "r", encoding="utf-8") as f:
        val_cases = [json.loads(line) for line in f if line.strip()]
        
    with open(TEST_PATH, "r", encoding="utf-8") as f:
        test_cases = [json.loads(line) for line in f if line.strip()]

    assert len(all_cases) == 871, f"Expected 871 total usable cases, got {len(all_cases)}"
    assert len(train_cases) + len(val_cases) + len(test_cases) == len(all_cases)

def test_schema_and_provenance():
    with open(ALL_CASES_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            item = json.loads(line)
            assert "instruction" in item and item["instruction"], f"Line {i} missing instruction"
            assert "input" in item and item["input"], f"Line {i} missing input"
            assert "output" in item and item["output"], f"Line {i} missing output"
            assert "_source_dataset" in item, f"Line {i} missing _source_dataset"
            
            # Parse output
            out_val = item["output"]
            if isinstance(out_val, str):
                out_dict = json.loads(out_val)
            else:
                out_dict = out_val
                
            assert "probable_root_cause" in out_dict, f"Line {i} missing probable_root_cause"
            assert "evidence" in out_dict and len(out_dict["evidence"]) > 0, f"Line {i} missing evidence"

            if item["_source_dataset"] == "RCAEval":
                meta = item.get("_metadata", {})
                assert "provenance" in meta, f"Line {i} missing provenance for RCAEval case"

def test_zero_duplicates_and_no_leakage():
    with open(TRAIN_PATH, "r", encoding="utf-8") as f:
        train_inputs = {json.loads(line)["input"].strip() for line in f if line.strip()}
        
    with open(VAL_PATH, "r", encoding="utf-8") as f:
        val_inputs = {json.loads(line)["input"].strip() for line in f if line.strip()}
        
    with open(TEST_PATH, "r", encoding="utf-8") as f:
        test_inputs = {json.loads(line)["input"].strip() for line in f if line.strip()}

    # Disjoint check
    assert len(train_inputs.intersection(val_inputs)) == 0, "Train and Validation inputs overlap!"
    assert len(train_inputs.intersection(test_inputs)) == 0, "Train and Test inputs overlap!"
    assert len(val_inputs.intersection(test_inputs)) == 0, "Validation and Test inputs overlap!"

def test_reports_and_manifest():
    assert os.path.exists(REPORT_MD_PATH)
    assert os.path.exists(STATS_JSON_PATH)
    
    with open(STATS_JSON_PATH, "r", encoding="utf-8") as f:
        stats = json.load(f)
        
    assert stats["total_usable_cases"] == 871
    assert stats["source_counts"]["CloudOps"] == 406
    assert stats["source_counts"]["RCAEval"] == 465

def test_protected_original_files_intact():
    orig_train = "data/processed/train.jsonl"
    orig_val = "data/processed/validation.jsonl"
    orig_test = "data/processed/test.jsonl"
    orig_exp = "data/raw/expanded/sample_synthetic_expanded.jsonl"

    for path in [orig_train, orig_val, orig_test, orig_exp]:
        assert os.path.exists(path), f"Protected original file missing: {path}"
        assert os.path.getsize(path) > 0, f"Protected original file empty: {path}"

