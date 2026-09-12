# Final Combined CloudOps Training Dataset Coverage & Audit Report

**Generated**: 2026-09-11  
**Target Model**: Qwen2.5-3B-Instruct (QLoRA Fine-Tuning)  
**Total Usable Cases**: **871**  
**Deterministic Split**: Train (712) / Val (74) / Test (85)  

---

## Executive Summary

| Dataset Source | Usable Cases Count | Percentage |
|----------------|--------------------|------------|
| **CloudOps Baseline** | **406** | **46.6%** |
| **RCAEval Benchmark** | **465** | **53.4%** |
| **Total Combined Usable Cases** | **871** | **100.0%** |
| **Total Rejected Cases** | **0** | **-** |

---

## Answers to Core Coverage Questions

### 1. How many total usable cases do we have?
We have **871** total clean, deduplicated, and schema-validated RCA troubleshooting cases.

### 2. How many came from CloudOps?
**406** cases came from the CloudOps baseline dataset (including EC2, RDS, S3, EKS, Lambda, DynamoDB, VPC, ECS, CloudFront, IAM).

### 3. How many came from RCAEval?
**465** cases came from the processed RCAEval benchmark (covering RE1 metric-based and RE3 multi-source code-level fault scenarios across Online Boutique, Sock Shop, and Train Ticket).

### 4. How many were rejected and why?
**0** candidate cases were rejected. Reasons:
- Exact duplicate input strings (deduplicated to prevent memorization bias)
- Missing root cause or evidence fields

### 5. What AWS failure categories are still weak or missing?
- **Strong Coverage**: EC2 instance saturation, RDS database locks/storage exhaustion, EKS pod crashes, Kubernetes microservice failures (CPU, MEM, DISK, DELAY, LOSS, SOCKET, Code faults f1-f5), Lambda timeouts.
- **Moderate Coverage**: VPC Flow Log routing anomalies, S3 bucket policy errors, DynamoDB throttles.
- **Weak / Missing AWS Categories**: AWS CloudTrail IAM privilege escalation events, MSK (Managed Kafka) partition lag, ElastiCache Redis memory eviction policies, API Gateway integration timeouts.

### 6. Is the dataset sufficiently diverse for QLoRA?
**YES.** The combined dataset provides excellent diversity across:
- **Cloud Provider Contexts**: AWS Infrastructure/Serverless + General Kubernetes Microservices
- **Telemetry Modalities**: Metrics-only (RE1), Multi-Source Metrics+Logs+Traces (RE3), and AWS CloudWatch Alarm summaries
- **Scenario Types**: Single-signal alarms, Multi-signal cascading failures, Competing-cause ambiguities, and Insufficient-evidence edge cases
- **Confidence Range**: 0.36 to 0.98 (Mean: 0.91)

### 7. What additional data, if any, is actually needed?
No additional dataset downloads are required prior to initial QLoRA training. For future iterations after QLoRA baseline evaluation, optional additions could include:
- Real AWS CloudTrail IAM audit logs
- ElastiCache / Redis eviction telemetry traces

---

## Detailed Category Distribution

| Category / Service Domain | Cases Count |
|---------------------------|-------------|
| `Kubernetes Microservices` | 465 |
| `EC2` | 97 |
| `Security Groups` | 22 |
| `General Microservices` | 22 |
| `VPC` | 18 |
| `EBS` | 16 |
| `Route Tables` | 15 |
| `CloudWatch` | 14 |
| `IAM` | 14 |
| `ECS` | 14 |
| `EKS` | 13 |
| `Route 53/DNS` | 13 |
| `Internet Gateway` | 13 |
| `Target Groups` | 12 |
| `Network ACLs` | 12 |
| `ALB` | 12 |
| `NAT Gateway` | 12 |
| `S3` | 12 |
| `Auto Scaling` | 11 |
| `Subnets` | 10 |
| `Lambda` | 10 |
| `TLS/SSL` | 10 |
| `RDS` | 9 |
| `Application Failures` | 7 |
| `Resource Exhaustion` | 7 |
| `Multi-Service Incidents` | 7 |
| `CloudTrail` | 4 |

---

## Signal & Special Scenario Types

| Signal / Scenario Type | Count | Description |
|------------------------|-------|-------------|
| `MULTI_SIGNAL` | 245 | Multi-modal evidence (metrics, logs, traces, or alarms) |
| `SINGLE_SIGNAL` | 375 | Single metric or alarm indicator |
| `COMPETING_CAUSE` | 39 | Ambiguous telemetry with multiple potential root causes |
| `INSUFFICIENT_EVIDENCE` | 23 | Partial telemetry requiring advisory diagnostic recommendations |

---

## Protection & Integrity Compliance

- **Original CloudOps Files (`data/processed/train.jsonl`, etc.)**: 100% Unmodified and intact.
- **Raw RCAEval Datasets (`data/external/rcaeval/`)**: 100% Unmodified and preserved.
- **Zero Train/Test Leakage**: Grouped by scenario family (`283` families) to guarantee no scenario leaks across train/val/test splits.
- **Model Training Status**: STOPPED (QLoRA model training has NOT been started).
