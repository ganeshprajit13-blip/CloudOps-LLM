# CloudOps LLM — Backend Foundation (Phase 1, Phase 2 & Phase 3)

## 1. Project Overview
**CloudOps LLM — AI Cloud Infrastructure Troubleshooter**

CloudOps LLM is an AI-powered advisory system designed to assist cloud administrators by analyzing AWS infrastructure signals, logs, metrics, network configurations, and knowledge bases to identify probable root causes of incidents and recommend actionable, non-autonomous remediations.

---

## 2. Phase 3 Scope: Data Normalization & Preprocessing

Phase 3 transforms raw, nested AWS Boto3 API responses into a clean, compact, structured, and LLM-friendly **CloudOps Data Representation**.

### Data Transformation Pipeline
```text
AWS Telemetry (Boto3)
        ↓
Raw Telemetry JSON
        ↓
Normalizer Layer (EC2, CloudWatch, CloudTrail, VPC, Security Groups, ALB)
        ↓
Signal Extraction (high_cpu, port_not_allowed, unhealthy_target, missing_default_route)
        ↓
Evidence Generation (Factual human-readable evidence statements)
        ↓
Preprocessed CloudOps Context (Structured JSON feed for future RAG + LLM)
```

> [!IMPORTANT]
> **Observation vs. Causality**: Phase 3 extractors strictly output **OBSERVED SIGNALS** and **FACTUAL EVIDENCE STATEMENTS**. Phase 3 **NEVER** asserts causal root-cause claims (e.g. "Security Group caused the outage"). Causal reasoning belongs entirely to the future LLM layer.

---

## 3. Signal Severity Model

Extracted signals utilize a standardized severity classification representing the importance of an **observed signal** (not the certainty of a root cause):
- `info`: Standard operational metric or signal (e.g., normal CPU utilization).
- `low`: Informational variation or minor signal.
- `medium`: Recent configuration change or management event (e.g., CloudTrail event).
- `high`: Critical observable condition (e.g., missing inbound HTTPS port 443 rule, unhealthy ALB target, CPU > 80%).
- `critical`: High-priority infrastructure signal.

---

## 4. Minimum Read-Only IAM Permissions
To query live AWS infrastructure, configure AWS credentials with a least-privilege read-only IAM policy containing:
- `ec2:DescribeInstances`
- `ec2:DescribeVpcs`
- `ec2:DescribeSubnets`
- `ec2:DescribeRouteTables`
- `ec2:DescribeInternetGateways`
- `ec2:DescribeNatGateways`
- `ec2:DescribeSecurityGroups`
- `cloudwatch:GetMetricStatistics`
- `cloudtrail:LookupEvents`
- `elasticloadbalancing:DescribeLoadBalancers`
- `elasticloadbalancing:DescribeTargetGroups`
- `elasticloadbalancing:DescribeTargetHealth`

---

## 5. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Root running status |
| `GET` | `/health` | Health check endpoint |
| `GET` | `/api/aws/ec2` | Read-only EC2 telemetry |
| `GET` | `/api/aws/cloudwatch` | Read-only CloudWatch metrics |
| `GET` | `/api/aws/cloudtrail` | Read-only CloudTrail events |
| `GET` | `/api/aws/vpc` | Read-only VPC infrastructure |
| `GET` | `/api/aws/security-groups` | Read-only Security Groups & rules |
| `GET` | `/api/aws/load-balancers` | Read-only ALBs, Target Groups & Target Health |
| `GET` | `/api/aws/infrastructure` | Aggregated raw telemetry data |
| `GET` | `/api/cloud/context` | Preprocessed, normalized CloudOps context with signals & evidence |
| `GET` | `/api/cloud/signals` | Extracted observable signals list |
| `GET` | `/docs` | Interactive Swagger API Docs |

---

## 6. Testing

### Run All Unit Tests (Phase 1, Phase 2, Phase 3)
Run `pytest` to execute all test suites:
```powershell
pytest
```

### Sample Data & Synthetic Verification
Synthetic raw telemetry and expected normalized context sample files are provided under:
- `backend/data/examples/raw_aws_data.json`
- `backend/data/examples/normalized_cloud_context.json`

---

## 7. Upcoming Roadmap
- **Phase 1 (Completed)**: Core FastAPI foundation & health routes.
- **Phase 2 (Completed)**: AWS Read-Only Boto3 telemetry integration.
- **Phase 3 (Completed)**: Telemetry normalization, signal extraction & evidence generation.
- **Phase 4**: CloudOps dataset creation & validation.
- **Phase 5**: Qwen2.5-3B-Instruct model adaptation with LoRA/QLoRA.
- **Phase 6**: Knowledge base ingestion & RAG vectorstore (ChromaDB).
- **Phase 7**: End-to-end AI analysis engine pipeline.
- **Phase 8**: Analysis REST API endpoints (`/api/analyze`).
- **Phase 9**: PostgreSQL storage for incident history & admin feedback.
- **Phase 10**: Integration, testing, and hardening.
- **Phase 11**: Real controlled AWS incident validation & evaluation.
