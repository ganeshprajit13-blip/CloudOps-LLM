# CloudOps AI Troubleshooter Diagnostic Workflow & Schema

## 1. Diagnostic Execution Steps (`POST /api/analyze`)
When a user submits an inquiry on the AI Troubleshooter page (`/troubleshoot`), the backend executes a 9-step pipeline:

1. **Request Intake**: API accepts `resource_id` (e.g. `i-07243bdf548e18f5`) and `question` (e.g., "Why is my website unreachable?").
2. **AWS Telemetry Collection**: Executes parallel read-only queries against AWS APIs:
   - `EC2Collector`: State, public IP, status checks, attached ENIs, Security Group IDs.
   - `VPCCollector`: Subnet CIDRs, route tables, default gateway entries (`0.0.0.0/0 -> igw-xxx`).
   - `SecurityGroupCollector`: Inbound and outbound TCP/UDP port rules (Ports 80, 443, 3389, 22).
   - `CloudWatchCollector`: Metric data (`CPUUtilization`, status check failures).
   - `CloudTrailCollector`: Recent administrative API events (e.g. `RevokeSecurityGroupIngress`).
   - `SSMCollector`: Windows/Linux host checks via AWS Systems Manager Run Command (`Get-Service W3SVC`, `Get-NetTCPConnection`).
3. **Signal Extraction**: Telemetry data is parsed into discrete failure signals (e.g., `stopped_instance`, `missing_port_80_rule`, `missing_default_route`, `high_cpu_utilization`).
4. **RAG Retrieval**: Embeds the query and signals to retrieve top-k runbook chunks from ChromaDB.
5. **Model Prompting**: Constructs a system prompt containing live telemetry evidence and retrieved runbook facts.
6. **Qwen Model Reasoning**: Model generates structured diagnosis JSON using the fine-tuned 4-bit QLoRA adapter.
7. **Post-Inference Validation**: `DiagnosisValidator` verifies schema integrity, evidence grounding, and safety rules.
8. **Confidence Score Calculation**: Computes a floating-point score between `0.0` and `1.0` based on signal clarity and factual grounding.
9. **Structured Response Delivery**: Returns 6-field diagnosis payload to the frontend.

---

## 2. 6-Field Diagnosis Output Schema
Every diagnostic analysis returns a JSON response with 6 specific fields:

1. **Problem Summary (`problem`)**: Concise technical summary of the observed failure state.
2. **Probable Root Cause (`probable_root_cause`)**: Specific technical cause derived from verified telemetry signals and RAG patterns.
3. **Verifiable Evidence (`verifiable_evidence`)**: List of factual, empirical observations gathered directly from AWS APIs (e.g., instance state, CPU %, security group rule lists, listening ports).
4. **Operational Impact (`operational_impact`)**: Business and operational impact on services or users.
5. **Advisory Recommendation (`advisory_recommendation`)**: Clear, actionable remediation steps for cloud administrators.
6. **Confidence Score (`confidence_score`)**: Score from `0.0` to `1.0`:
   - **High Confidence (>0.85)**: Telemetry proof is unambiguous (e.g. Security Group explicitly lacks port 80 rule).
   - **Medium Confidence (0.50–0.85)**: Corroborated evidence with minor missing telemetry signals.
   - **Low Confidence (<0.50)**: Incomplete telemetry or indirect evidence.

---

## 3. Read-Only Telemetry & Safety Guarantee
- **Read-Only API Calls**: CloudOps collectors perform exclusively read-only AWS operations (`DescribeInstances`, `GetMetricData`, `LookupEvents`).
- **No Autonomous Remediation**: CloudOps provides advisory recommendations only and **never** performs automated infrastructure modifications or instance restarts.
