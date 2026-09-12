# Real Data Processing Report

**Generated**: 2026-09-11
**Pipeline Version**: 1.0.0
**Datasets Processed**: RCAEval v1.7.0, AWS Sample RCA Deep Investigations

---

## Executive Summary

| Metric | Count |
|--------|-------|
| Raw records processable from RCAEval ZIP | 1 (of 735 total) |
| Raw scenarios from AWS ZIP | 5 |
| Cases normalized | 6 |
| Duplicates removed | 0 |
| **Final usable real cases** | **6** |
| Overlap with existing 412 | 4 (keyword only) |
| Rejected records | 0 |

---

## Dataset 1: RCAEval v1.7.0

**Source**: https://github.com/phamquiluan/RCAEval  
**License**: MIT  
**SHA-256 (ZIP)**: C9F68B97E955220F9BDAD0E6C28BA083E96A6A0CB7610395307FE42925AE42AA

### Files Processed

| File | Status |
|------|--------|
| `legacy/simple_metrics.csv` | Extracted, sanitized, normalized |
| `README.md` | Extracted for provenance |
| `LICENSE` | Extracted for audit |
| Full 735-case dataset | NOT DOWNLOADED (~3.4-38 GB on HuggingFace/Zenodo) |

### Result

- **Raw records in ZIP**: 1 legacy time-series CSV (no ground-truth label)
- **Normalized cases**: 1
- Case has `has_root_cause=false` -- legacy format predates fault annotation
- Full 735-case dataset pending download authorization

### Full RCAEval Dataset Structure (reference, not downloaded)

| Subset | System | Cases | Fault Types |
|--------|--------|-------|-------------|
| RE1-OB | Online Boutique | 125 | cpu, mem, disk, delay, loss |
| RE1-SS | Sock Shop | 125 | cpu, mem, disk, delay, loss |
| RE1-TT | Train Ticket | 125 | cpu, mem, disk, delay, loss |
| RE2-OB | Online Boutique | 90 | cpu, mem, disk, delay, loss, socket |
| RE2-SS | Sock Shop | 90 | cpu, mem, disk, delay, loss, socket |
| RE2-TT | Train Ticket | 90 | cpu, mem, disk, delay, loss, socket |
| RE3-OB | Online Boutique | 30 | f1, f2, f3, f4, f5 |
| RE3-SS | Sock Shop | 30 | f1, f2, f3, f4 |
| RE3-TT | Train Ticket | 30 | f1, f2, f3, f4 |
| **Total** | | **735** | |

---

## Dataset 2: AWS Sample RCA Deep Investigations

**Source**: https://github.com/aws-samples/sample-rca-deep-investigations  
**License**: MIT-0 (No Attribution Required)  
**SHA-256**: 5D126D755185A5415BD6901414268175BB775CC85633295E656B603A12C5CD7D

### 219 Files Extracted, 219 Sanitized

### Scenarios Normalized

| Case ID | Domain | Difficulty | Root Cause Service | Has Logs | Has Remediation |
|---------|--------|------------|-------------------|---------|-----------------|
| `aws-care-transcript-supply-chain` | SupplyChain | hard | defect-classifier | Yes | Yes |
| `aws-iot-fleet-disconnect-cascade` | IoT | high | auth-service | Yes | No |
| `aws-k8s-canary-silent-poisoning` | Kubernetes | hard | inventory-service | Yes | No |
| `aws-ml-training-drift-schema-migration` | MLOps | expert | events-warehouse-db | Yes | No |
| `aws-volte-call-drop-handover` | Telecom/VoLTE | hard | mobility-controller | Yes | No |

---

## Sanitization

- **AWS files processed**: 219
- **RCAEval files processed**: 3
- **Patterns checked**: AWS access keys, secret keys, bearer tokens, passwords, emails
- **Private IPs**: Preserved (useful technical context in incident documents)
- **Redactions made**: 0 credentials or PII found and redacted

---

## Deduplication

- Cases before dedup: 6
- Duplicates removed: 0
- Final unique cases: 6
- Cross-dataset duplicates: 0 (completely different technical domains)

---

## Overlap with Existing 412 Examples

- Cases with keyword overlap: 4
- **Action**: Reported only -- NOT deduplicated
- Keyword overlap (e.g., 'Lambda', 'EKS') does not indicate content duplication

| Case ID | Keywords | Assessment |
|---------|----------|------------|
| `aws-care-transcript-supply-chain` | s3 | Low risk -- keyword overlap only, not content duplication |
| `aws-iot-fleet-disconnect-cascade` | cloudwatch | Low risk -- keyword overlap only, not content duplication |
| `aws-k8s-canary-silent-poisoning` | eks, alb | Low risk -- keyword overlap only, not content duplication |
| `aws-volte-call-drop-handover` | rds | Low risk -- keyword overlap only, not content duplication |

---

## Rejected Records

**0 records rejected.** All processable cases passed normalization and validation.

---

## Output Files

| File | Cases | Purpose |
|------|-------|---------|
| `data/normalized/rcaeval_cases.jsonl` | 1 | Normalized RCAEval |
| `data/normalized/aws_cases.jsonl` | 5 | Normalized AWS |
| `data/rca/rcaeval_rca.jsonl` | 1 | RCA-extracted RCAEval |
| `data/rca/aws_rca.jsonl` | 5 | RCA-extracted AWS |
| `data/rca/all_real_cases.jsonl` | 6 | All deduplicated real cases |
| `data/schemas/normalized_case.schema.json` | -- | JSON Schema for case format |
| `data/reports/real_data_statistics.json` | -- | Machine-readable statistics |

---

## Protected Files (Not Modified)

- `data/processed/train.jsonl` -- NOT MODIFIED
- `data/processed/validation.jsonl` -- NOT MODIFIED
- `data/processed/test.jsonl` -- NOT MODIFIED
- `data/external/` -- NOT MODIFIED (all originals preserved)

---

## Next Steps

1. Optionally download full RCAEval dataset (735 cases) from HuggingFace
2. Convert real cases to instruction/input/output JSONL format (Step 5)
3. Merge with existing 412 examples (Step 5)
4. Begin QLoRA fine-tuning
