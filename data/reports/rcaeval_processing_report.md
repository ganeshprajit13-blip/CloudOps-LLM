# RCAEval Real Telemetry Processing Report

**Generated**: 2026-09-11  
**Dataset Source**: RCAEval Benchmark ([phamquiluan/RCAEval](https://huggingface.co/datasets/phamquiluan/RCAEval))  
**License**: MIT License  

---

## Executive Summary

| Metric | Count / Value |
|--------|---------------|
| **Total Cases Indexed (`cases.parquet`)** | **735** |
| **Local Telemetry Cases Discovered** | **465** |
| **Successfully Processed & Normalized Cases** | **465** |
| **Failed Cases** | **0** |
| **Skipped Cases (Not Downloaded Locally)** | **270** |
| **RE1 Metric Cases Processed** | **375** |
| **RE3 Multi-Source Cases Processed** | **90** |
| **Duplicate Cases Found** | **0** |
| **Credentials/Secrets Redacted/Found** | **0** |

---

## Telemetry Sources Availability

| Source | Cases Available | Total Telemetry Rows Processed |
|--------|-----------------|--------------------------------|
| **Metrics (`metrics.parquet`)** | 465 | 602,904 |
| **Logs (`logs.parquet`)** | 90 | 6,021,307 |
| **Traces (`traces.parquet`)** | 60 | 8,907,766 |
| **Total Telemetry Rows** | | **15,531,977** |

---

## Quality & Validation Checks

- **Duplicate Check**: Passed (0 duplicates found)
- **Ground Truth Check**: Passed (All 465 cases have valid `root_cause_service`, `fault`, and `inject_time`)
- **Parquet Integrity Check**: Passed (0 corrupted parquet files)
- **Timestamp Verification**: Passed (`inject_time` verified against `cases.parquet` and `inject_time.txt`)
- **Secret/Credential Audit**: Passed (0 credentials or hardcoded keys detected)
- **Provenance Verification**: Passed (All cases preserve original case ID, dataset URL, and license)

---

## Generated Output Files

| File Path | Purpose | Size (Bytes) | Cases Count |
|-----------|---------|--------------|-------------|
| [`data/normalized/rcaeval/normalized_cases.jsonl`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/data/normalized/rcaeval/normalized_cases.jsonl) | Normalized structured telemetry cases | 3,755,607 | 465 |
| [`data/rca/rcaeval/rcaeval_training_cases.jsonl`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/data/rca/rcaeval/rcaeval_training_cases.jsonl) | Training-ready RCA representation | 473,486 | 465 |
| [`data/reports/rcaeval_processing_statistics.json`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/data/reports/rcaeval_processing_statistics.json) | Detailed machine-readable statistics | - | - |

---

## Skipped Cases Breakdown

- **Total Skipped Cases**: 270 (RE2 suite: 270 microservice failure cases indexed in `cases.parquet` whose telemetry was not downloaded locally in this run to optimize storage).
- **Failed Cases**: 0

---

## Protection Compliance

- **412 CloudOps Baseline Examples**: Unmodified
- **Dataset Splits (`train.jsonl`, `validation.jsonl`, `test.jsonl`)**: Unmodified
- **Original RCAEval Raw Archives**: Unmodified & preserved under `data/external/rcaeval/`
