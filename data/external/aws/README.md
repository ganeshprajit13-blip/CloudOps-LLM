# AWS Sample RCA Deep Investigations — AWS-Specific Incident Investigation Scenarios

## What It Contains

An official AWS sample repository published by Amazon Web Services under the
`aws-samples` GitHub organization. Contains structured incident investigation
scenarios specifically designed for testing LLM-based Root Cause Analysis (RCA)
and Retrieval-Augmented Generation (RAG) workflows on AWS infrastructure.

Scenario types included:
- **VoLTE call drops** — telecom on AWS infrastructure
- **Kubernetes canary deployment failures** — EKS-related incidents
- **IoT device disconnections** — IoT Core incidents
- Application-layer vs infrastructure-layer incident disambiguation

Each scenario includes:
- Structured incident reports
- Evidence logs and telemetry data
- Context files (architecture diagrams, runbooks)
- Ground truth for evaluation

Also includes:
- Reference LLM-based investigation application (source code)
- Deployment templates (AWS CDK/CloudFormation)
- RAG pipeline implementation
- Testing framework

## Source

- **Repository**: https://github.com/aws-samples/sample-rca-deep-investigations
- **Organization**: Amazon Web Services (aws-samples)
- **Type**: Official AWS sample — production-quality reference implementation

## License

**MIT No Attribution (MIT-0)**
Copyright Amazon.com, Inc. or its affiliates. All rights reserved.

Permits:
- Commercial use ✅
- Modification ✅
- Distribution ✅
- Sublicensing ✅
- Training use ✅
- **No attribution required** ✅

This is the most permissive license possible. Zero restrictions on use.

## Downloaded Files

| File | Size | SHA-256 |
|------|------|---------|
| `aws-sample-rca-deep-investigations-main.zip` | 571,350 bytes | `5D126D755185A5415BD6901414268175BB775CC85633295E656B603A12C5CD7D` |

Downloaded: 2026-09-11

## Data Types

- **Incidents**: Structured AWS incident scenarios with evidence
- **Logs**: Sample CloudWatch logs and application logs within scenarios
- **Configuration**: Architecture context and environment configurations

## Cloud/Provider

**AWS** — specifically designed for AWS infrastructure incidents

## Services Covered

- EC2 (compute)
- EKS / Kubernetes (container orchestration)
- IoT Core (IoT device management)
- CloudWatch (monitoring/logging)
- X-Ray (distributed tracing)
- CloudTrail (audit logging)
- Lambda (serverless)
- AWS networking (VPC, routing)

## Why It Is Useful for CloudOps

1. **AWS-native**: Directly targets AWS infrastructure — perfect alignment with our project
2. **Official AWS content**: Created by AWS engineers, not synthetic
3. **Structured for LLM**: Designed specifically for LLM-based RCA testing
4. **RAG-optimized**: Scenarios structured for RAG retrieval workflows
5. **Ground truth**: Each scenario has verified correct answers
6. **Multi-service**: Covers compute, networking, IoT, containers
7. **MIT-0 license**: Zero restrictions — fully usable for training

## Known Limitations

- Small number of scenarios (several, not hundreds)
- Focused on specific scenario types (VoLTE, Kubernetes, IoT)
- Includes application code (not just raw data)
- Scenarios are curated/illustrative, not from live production incidents

## Suitability for Training

✅ **YES** — MIT-0 license permits unrestricted training use. Scenario content
with structured incident evidence and ground truth is directly usable for
instruction-following RCA training after normalization.

## Suitability for RAG

✅ **YES** — Repository includes a reference RAG implementation. Scenario
incident reports, evidence logs, and context files are ideal RAG documents
for a CloudOps LLM. This is one of the best sources for AWS-specific RAG context.

## Manifest

See: `data/manifests/aws-sample-rca-deep-investigations.manifest.json`
