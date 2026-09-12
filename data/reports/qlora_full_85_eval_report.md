# CloudOps Full 85-Case QLoRA Evaluation Report

**Generated**: 2026-09-12 15:19:25  
**Base Model**: `Qwen/Qwen2.5-3B-Instruct`  
**Adapter Location**: [`outputs/adapter/`](file:///C:/Users/Prajit Radhakrishnan/OneDrive/Desktop/CloudOPS/outputs/adapter)  
**Test File**: [`data/processed/combined/test.jsonl`](file:///C:/Users/Prajit Radhakrishnan/OneDrive/Desktop/CloudOPS/data/processed/combined/test.jsonl) (Total Cases: 85)  
**Evaluation Artifact**: [`outputs/evaluation/full_85_evaluation.json`](file:///C:/Users/Prajit Radhakrishnan/OneDrive/Desktop/CloudOPS/outputs/evaluation/full_85_evaluation.json)  

---

## 1. Test Dataset Verification & Integrity

| Dataset Property | Audit Finding |
|------------------|---------------|
| **Test File Path** | `C:\Users\Prajit Radhakrishnan\OneDrive\Desktop\CloudOPS\data\processed\combined\test.jsonl` |
| **Total Test Cases** | **`85` cases** (All 85 evaluated, 0 skipped) |
| **SHA-256 Hash (Before)** | `bb1c15e9018a0a8e39dd2288501c7280f5de29da330c8df6fbefbcd64ed30a77` |
| **SHA-256 Hash (After)** | `bb1c15e9018a0a8e39dd2288501c7280f5de29da330c8df6fbefbcd64ed30a77` |
| **Integrity Audit Result** | **PASSED (100% Untouched & Unmodified)** |

---

## 2. Full 85-Case Model Comparison: Base Model vs Qwen + LoRA Adapter

| Evaluation Metric | Base Model (Un-adapted) | Qwen + LoRA Adapter | Metric Improvement |
|-------------------|-------------------------|---------------------|--------------------|
| **Cases Evaluated** | `85` | `85` | **100% Complete** |
| **Successfully Generated** | `85` | `85` | `+0` |
| **Failed Generations** | `0` | `0` | `0` |
| **JSON / Syntax Validity** | **100.0%** | **100.0%** | **+0.0%** |
| **Schema Validity Rate** | **100.0%** | **100.0%** | **+0.0%** |
| **Confidence Validity Rate** | **100.0%** | **100.0%** | **+0.0%** |
| **Evidence Grounding Rate** | **100.0%** | **100.0%** | **+0.0%** |
| **Advisory Safety Pass Rate** | **100.0%** | **97.65%** | **+-2.35%** |
| **Root Cause Correctness** | **42.35%** | **68.24%** | **+25.89%** |
| **Uncertainty Behavior Pass** | **100.0%** | **100.0%** | **+0.0%** |

---

## 3. Generation Performance Statistics

| Metric | Base Model | Fine-Tuned LoRA Model |
|--------|------------|-----------------------|
| **Average Generation Time** | `6.7726 sec` | `17.473 sec` |
| **Average Output Length** | `755.45 chars` | `915.87 chars` |

---

## 4. Failed Generation Diagnostics

- **Base Model Failed Count**: `0` cases
- **LoRA Model Failed Count**: `0` cases


> ✅ **Zero failed generations logged for fine-tuned LoRA model.** All 85 cases generated successfully.

---

## 5. Compliance Check

- ✅ Evaluation completed on ALL 85 untouched test set cases
- ✅ Zero cases skipped silently
- ✅ Base Model vs Qwen + LoRA comparison executed
- ✅ SHA-256 dataset integrity verified before and after
- ✅ Saved artifacts to `data/reports/qlora_full_85_eval_report.md` and `outputs/evaluation/full_85_evaluation.json`
