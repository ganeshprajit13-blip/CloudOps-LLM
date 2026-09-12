# CloudOps LLM — Instruction-Tuning Dataset (Phase 4)

## 1. Overview
This directory contains the instruction-tuning dataset for adapting **Qwen2.5-3B-Instruct** using **LoRA / QLoRA** (Phase 5). 

The dataset teaches the model to operate as a professional, advisor-only **CloudOps Infrastructure Troubleshooting Advisor** that performs evidence-grounded probabilistic root cause analysis.

---

## 2. Directory Structure

```text
data/
├── examples/
│   ├── example_incidents.json        # Curated reference incident scenarios
│   ├── normalized_cloud_context.json  # Sample normalized context feed
│   └── raw_aws_data.json             # Sample raw AWS telemetry input
├── processed/
│   ├── train.jsonl                   # 80% Training set (176 examples)
│   ├── validation.jsonl              # 10% Validation set (22 examples)
│   └── test.jsonl                    # 10% Test set (22 examples)
└── schemas/
    └── incident_schema.json          # Target JSON output schema definition
```

---

## 3. JSONL Example Format

Each line in `data/processed/*.jsonl` is a JSON object with three required fields:
```json
{
  "instruction": "Analyze this AWS infrastructure incident and determine the probable root cause.",
  "input": "EC2 instance i-0a1b2c3d4e5f67890 is running. CPU utilization is 31%. Inbound TCP port 443 is missing from Security Group sg-0987654321fedcba0.",
  "output": "{\"problem\": \"Website is unreachable over HTTPS\", \"probable_root_cause\": \"Security Group sg-0987654321fedcba0 is likely blocking inbound HTTPS traffic on TCP port 443\", \"evidence\": [\"EC2 instance i-0a1b2c3d4e5f67890 is in running state\", \"Inbound TCP port 443 is missing from Security Group sg-0987654321fedcba0\"], \"impact\": \"Users are unable to establish secure HTTPS connections\", \"recommendation\": \"Review Security Group sg-0987654321fedcba0 inbound rules and allow TCP port 443 from expected source CIDRs\", \"confidence\": 0.94}"
}
```

---

## 4. Diagnosis Output JSON Schema

Every generated diagnosis string parses into a JSON object strictly adhering to:
- `problem` (string): Description of observed operational issue.
- `probable_root_cause` (string): Probabilistic root cause statement (uses "likely", "may be").
- `evidence` (array of strings): Factual evidence statements directly supported by the input.
- `impact` (string): Operational consequence.
- `recommendation` (string): Actionable, safe advisory step for human administrator execution.
- `confidence` (number): Numeric confidence score strictly between `0.00` and `1.00`.

---

## 5. Covered Incident Categories

The dataset spans 8 major cloud troubleshooting categories:
1. **EC2**: Instance states, high CPU, disk pressure, memory exhaustion, network drop.
2. **Security Groups**: Missing/blocked inbound rules (TCP 443, 80, 22), improper CIDR sources.
3. **Networking**: Missing default routes (0.0.0.0/0), IGW/NAT Gateway availability, subnet routing.
4. **Load Balancer (ALB)**: Target group health check failures, path mismatches, unhealthy target states.
5. **CloudWatch**: Sustained metric anomalies, alarm state triggers, multi-metric correlation.
6. **CloudTrail**: Audit of recent administrative changes (Security Group rule additions/revocations, route changes).
7. **IAM**: `AccessDenied` errors, missing action policy permissions (`PutMetricData`, `GetObject`).
8. **Multi-Signal & Uncertainty**: Competing hypotheses, insufficient telemetry context, non-causal safety enforcement.

---

## 6. How to Validate the Dataset

Run the automated validation script from the project root:
```powershell
python scripts/validate_dataset.py
```

The script audits:
- Valid JSONL line parsing
- Required top-level keys (`instruction`, `input`, `output`)
- Strict JSON schema validation on `output`
- Confidence numeric range (`0.0 <= confidence <= 1.0`)
- Evidence non-emptiness & factual compliance (rejects causal claims in evidence)
- Security scanning (detects accidental AWS keys, passwords, or tokens)
- Data leakage & duplicate detection across splits

---

## 7. Consumption in Phase 5

In Phase 5, `Qwen2.5-3B-Instruct` will be adapted using Hugging Face PEFT + LoRA/QLoRA by loading `data/processed/train.jsonl` and `validation.jsonl` directly.
