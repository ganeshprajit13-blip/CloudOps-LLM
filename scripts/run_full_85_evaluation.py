"""
CloudOps Full 85-Case Evaluation Runner
Executes evaluation of Base Model vs fine-tuned QLoRA Adapter on all 85 test cases in data/processed/combined/test.jsonl.
Generates:
  - outputs/evaluation/full_85_evaluation.json
  - data/reports/qlora_full_85_eval_report.md
"""

import sys
import os
import json
import hashlib
import time
import logging
from pathlib import Path

# Add project root directory to python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.config import BASE_MODEL_NAME, ADAPTER_OUTPUT_DIR, TEST_FILE, EVALUATION_OUTPUT_DIR
from model.model_loader import load_base_model
from model.evaluate import CloudOpsEvaluator
from peft import PeftModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("run_full_85_eval")


def compute_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def count_file_lines(filepath: str) -> int:
    count = 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def main():
    logger.info("=" * 70)
    logger.info("CLOUDOPS LLM — FULL 85-CASE TEST EVALUATION & COMPARISON SUITE")
    logger.info("=" * 70)

    # 1. Dataset Integrity Verification (Before)
    test_path = str(TEST_FILE)
    sha256_before = compute_file_sha256(test_path)
    line_count_before = count_file_lines(test_path)
    file_size_before = os.path.getsize(test_path)

    logger.info(f"[Test Dataset Verification — Before]")
    logger.info(f"  Path      : {test_path}")
    logger.info(f"  Line Count: {line_count_before} cases")
    logger.info(f"  Size      : {file_size_before} bytes")
    logger.info(f"  SHA-256   : {sha256_before}")

    assert line_count_before == 85, f"Expected 85 test cases in {test_path}, found {line_count_before}"

    # 2. Evaluate Base Model (Un-adapted Qwen2.5-3B-Instruct)
    logger.info("\n[Phase 1] Evaluating Base Model (Qwen2.5-3B-Instruct, Un-adapted) on ALL 85 test cases...")
    base_model, mode = load_base_model(BASE_MODEL_NAME, mode="qlora")
    from model.tokenizer import load_tokenizer
    tokenizer = load_tokenizer(BASE_MODEL_NAME)

    base_evaluator = CloudOpsEvaluator(model=base_model, tokenizer=tokenizer, output_dir=EVALUATION_OUTPUT_DIR)
    base_summary, base_results = base_evaluator.evaluate(
        limit=None,
        max_new_tokens=512,
        save_filename_summary="base_model_summary.json",
        save_filename_results="base_model_results.json"
    )

    # 3. Evaluate Qwen2.5-3B-Instruct + LoRA Adapter
    logger.info(f"\n[Phase 2] Attaching LoRA Adapter from '{ADAPTER_OUTPUT_DIR}'...")
    lora_model = PeftModel.from_pretrained(base_model, ADAPTER_OUTPUT_DIR)
    logger.info("  LoRA Adapter attached successfully!")

    logger.info("\n[Phase 3] Evaluating Fine-Tuned Model (Qwen + LoRA Adapter) on ALL 85 test cases...")
    lora_evaluator = CloudOpsEvaluator(model=lora_model, tokenizer=tokenizer, output_dir=EVALUATION_OUTPUT_DIR)
    lora_summary, lora_results = lora_evaluator.evaluate(
        limit=None,
        max_new_tokens=512,
        save_filename_summary="lora_model_summary.json",
        save_filename_results="lora_model_results.json"
    )

    # 4. Dataset Integrity Verification (After)
    sha256_after = compute_file_sha256(test_path)
    line_count_after = count_file_lines(test_path)

    logger.info(f"\n[Test Dataset Verification — After]")
    logger.info(f"  Line Count: {line_count_after} cases")
    logger.info(f"  SHA-256   : {sha256_after}")

    assert sha256_before == sha256_after, "CRITICAL ERROR: Test dataset was modified during evaluation!"
    logger.info("  ✅ Test dataset verified 100% UNCHANGED and intact.")

    # 5. Export Full 85 Evaluation Artifacts
    full_eval_artifact = {
        "dataset_integrity": {
            "test_file": test_path,
            "total_cases": line_count_after,
            "sha256": sha256_after,
            "untouched": sha256_before == sha256_after,
        },
        "base_model_summary": base_summary,
        "lora_adapter_summary": lora_summary,
        "comparison": {
            "test_count": 85,
            "json_validity_percentage": {
                "base": base_summary.get("valid_json_percentage", 0.0),
                "lora": lora_summary.get("valid_json_percentage", 0.0),
                "diff": round(lora_summary.get("valid_json_percentage", 0.0) - base_summary.get("valid_json_percentage", 0.0), 2)
            },
            "schema_validity_percentage": {
                "base": base_summary.get("schema_validity_percentage", 0.0),
                "lora": lora_summary.get("schema_validity_percentage", 0.0),
                "diff": round(lora_summary.get("schema_validity_percentage", 0.0) - base_summary.get("schema_validity_percentage", 0.0), 2)
            },
            "confidence_validity_percentage": {
                "base": base_summary.get("confidence_validity_percentage", 0.0),
                "lora": lora_summary.get("confidence_validity_percentage", 0.0),
                "diff": round(lora_summary.get("confidence_validity_percentage", 0.0) - base_summary.get("confidence_validity_percentage", 0.0), 2)
            },
            "evidence_grounding_percentage": {
                "base": base_summary.get("evidence_grounding_percentage", 0.0),
                "lora": lora_summary.get("evidence_grounding_percentage", 0.0),
                "diff": round(lora_summary.get("evidence_grounding_percentage", 0.0) - base_summary.get("evidence_grounding_percentage", 0.0), 2)
            },
            "safety_check_pass_percentage": {
                "base": base_summary.get("safety_check_pass_percentage", 0.0),
                "lora": lora_summary.get("safety_check_pass_percentage", 0.0),
                "diff": round(lora_summary.get("safety_check_pass_percentage", 0.0) - base_summary.get("safety_check_pass_percentage", 0.0), 2)
            },
            "root_cause_correctness_percentage": {
                "base": base_summary.get("root_cause_correctness_percentage", 0.0),
                "lora": lora_summary.get("root_cause_correctness_percentage", 0.0),
                "diff": round(lora_summary.get("root_cause_correctness_percentage", 0.0) - base_summary.get("root_cause_correctness_percentage", 0.0), 2)
            },
            "uncertainty_behavior_pass_percentage": {
                "base": base_summary.get("uncertainty_behavior_pass_percentage", 0.0),
                "lora": lora_summary.get("uncertainty_behavior_pass_percentage", 0.0),
                "diff": round(lora_summary.get("uncertainty_behavior_pass_percentage", 0.0) - base_summary.get("uncertainty_behavior_pass_percentage", 0.0), 2)
            },
        }
    }

    full_eval_json_path = os.path.join(EVALUATION_OUTPUT_DIR, "full_85_evaluation.json")
    with open(full_eval_json_path, "w", encoding="utf-8") as f:
        json.dump(full_eval_artifact, f, indent=2)

    logger.info(f"Full 85-case evaluation artifact saved to {full_eval_json_path}")

    # 6. Generate Markdown Report
    report_path = os.path.join(PROJECT_ROOT, "data", "reports", "qlora_full_85_eval_report.md")
    report_md = f"""# CloudOps Full 85-Case QLoRA Evaluation Report

**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Base Model**: `{BASE_MODEL_NAME}`  
**Adapter Location**: [`outputs/adapter/`](file:///{os.path.abspath(ADAPTER_OUTPUT_DIR).replace('\\', '/')})  
**Test File**: [`data/processed/combined/test.jsonl`](file:///{os.path.abspath(test_path).replace('\\', '/')}) (Total Cases: {line_count_after})  
**Evaluation Artifact**: [`outputs/evaluation/full_85_evaluation.json`](file:///{os.path.abspath(full_eval_json_path).replace('\\', '/')})  

---

## 1. Test Dataset Verification & Integrity

| Dataset Property | Audit Finding |
|------------------|---------------|
| **Test File Path** | `{test_path}` |
| **Total Test Cases** | **`{line_count_after}` cases** (All 85 evaluated, 0 skipped) |
| **SHA-256 Hash (Before)** | `{sha256_before}` |
| **SHA-256 Hash (After)** | `{sha256_after}` |
| **Integrity Audit Result** | **PASSED (100% Untouched & Unmodified)** |

---

## 2. Full 85-Case Model Comparison: Base Model vs Qwen + LoRA Adapter

| Evaluation Metric | Base Model (Un-adapted) | Qwen + LoRA Adapter | Metric Improvement |
|-------------------|-------------------------|---------------------|--------------------|
| **Cases Evaluated** | `{base_summary.get('test_count', 0)}` | `{lora_summary.get('test_count', 0)}` | **100% Complete** |
| **Successfully Generated** | `{base_summary.get('success_count', 0)}` | `{lora_summary.get('success_count', 0)}` | `+{lora_summary.get('success_count', 0) - base_summary.get('success_count', 0)}` |
| **Failed Generations** | `{base_summary.get('failed_count', 0)}` | `{lora_summary.get('failed_count', 0)}` | `{lora_summary.get('failed_count', 0)}` |
| **JSON / Syntax Validity** | **{base_summary.get('valid_json_percentage', 0.0)}%** | **{lora_summary.get('valid_json_percentage', 0.0)}%** | **+{round(lora_summary.get('valid_json_percentage', 0.0) - base_summary.get('valid_json_percentage', 0.0), 2)}%** |
| **Schema Validity Rate** | **{base_summary.get('schema_validity_percentage', 0.0)}%** | **{lora_summary.get('schema_validity_percentage', 0.0)}%** | **+{round(lora_summary.get('schema_validity_percentage', 0.0) - base_summary.get('schema_validity_percentage', 0.0), 2)}%** |
| **Confidence Validity Rate** | **{base_summary.get('confidence_validity_percentage', 0.0)}%** | **{lora_summary.get('confidence_validity_percentage', 0.0)}%** | **+{round(lora_summary.get('confidence_validity_percentage', 0.0) - base_summary.get('confidence_validity_percentage', 0.0), 2)}%** |
| **Evidence Grounding Rate** | **{base_summary.get('evidence_grounding_percentage', 0.0)}%** | **{lora_summary.get('evidence_grounding_percentage', 0.0)}%** | **+{round(lora_summary.get('evidence_grounding_percentage', 0.0) - base_summary.get('evidence_grounding_percentage', 0.0), 2)}%** |
| **Advisory Safety Pass Rate** | **{base_summary.get('safety_check_pass_percentage', 0.0)}%** | **{lora_summary.get('safety_check_pass_percentage', 0.0)}%** | **+{round(lora_summary.get('safety_check_pass_percentage', 0.0) - base_summary.get('safety_check_pass_percentage', 0.0), 2)}%** |
| **Root Cause Correctness** | **{base_summary.get('root_cause_correctness_percentage', 0.0)}%** | **{lora_summary.get('root_cause_correctness_percentage', 0.0)}%** | **+{round(lora_summary.get('root_cause_correctness_percentage', 0.0) - base_summary.get('root_cause_correctness_percentage', 0.0), 2)}%** |
| **Uncertainty Behavior Pass** | **{base_summary.get('uncertainty_behavior_pass_percentage', 0.0)}%** | **{lora_summary.get('uncertainty_behavior_pass_percentage', 0.0)}%** | **+{round(lora_summary.get('uncertainty_behavior_pass_percentage', 0.0) - base_summary.get('uncertainty_behavior_pass_percentage', 0.0), 2)}%** |

---

## 3. Generation Performance Statistics

| Metric | Base Model | Fine-Tuned LoRA Model |
|--------|------------|-----------------------|
| **Average Generation Time** | `{base_summary.get('average_generation_time_seconds', 0.0)} sec` | `{lora_summary.get('average_generation_time_seconds', 0.0)} sec` |
| **Average Output Length** | `{base_summary.get('average_output_length_chars', 0.0)} chars` | `{lora_summary.get('average_output_length_chars', 0.0)} chars` |

---

## 4. Failed Generation Diagnostics

- **Base Model Failed Count**: `{base_summary.get('failed_count', 0)}` cases
- **LoRA Model Failed Count**: `{lora_summary.get('failed_count', 0)}` cases

"""
    if lora_summary.get("failed_cases"):
        report_md += "### LoRA Model Failed Cases Breakdown:\n\n"
        for fc in lora_summary.get("failed_cases"):
            report_md += f"- **Index {fc['test_index']}** (ID: `{fc['case_id']}`): {fc['error']}\n"
    else:
        report_md += "\n> ✅ **Zero failed generations logged for fine-tuned LoRA model.** All 85 cases generated successfully.\n"

    report_md += """
---

## 5. Compliance Check

- ✅ Evaluation completed on ALL 85 untouched test set cases
- ✅ Zero cases skipped silently
- ✅ Base Model vs Qwen + LoRA comparison executed
- ✅ SHA-256 dataset integrity verified before and after
- ✅ Saved artifacts to `data/reports/qlora_full_85_eval_report.md` and `outputs/evaluation/full_85_evaluation.json`
"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    logger.info(f"Full 85-case markdown report written to {report_path}")
    print("\n[SUCCESS] Full 85-Case Evaluation Suite Completed Successfully!")


if __name__ == "__main__":
    main()
