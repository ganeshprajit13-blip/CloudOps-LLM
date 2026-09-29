# CloudOps Platform — Product Deep Dive

## 1. What is CloudOps?

**CloudOps** is an AI-powered cloud operations platform for AWS infrastructure monitoring, intelligent troubleshooting, and technical support. It combines:

- **AI Troubleshooter**: Automated, read-only AWS diagnostic pipeline powered by Qwen2.5-3B + QLoRA
- **Support Agent**: RAG-grounded conversational technical assistant for CloudOps, AWS, and AI/LLM questions
- **Live AWS Telemetry**: Real-time Boto3 collection of EC2, VPC, Security Group, CloudWatch, and CloudTrail data
- **ChromaDB Vector Store**: Two dedicated knowledge bases (troubleshooter knowledge + support knowledge)

---

## 2. Advisory-Only Architecture

**CloudOps is strictly advisory-only. It does NOT automatically modify AWS infrastructure.**

CloudOps never:
- Opens or closes Security Group rules automatically
- Starts, stops, reboots, or terminates EC2 instances
- Modifies Route Tables, VPC configurations, or NACLs
- Executes IAM permission changes
- Runs any write AWS API operations

All AWS API calls made by CloudOps are read-only:
- `ec2:Describe*` — Read EC2/VPC/SG/NACL configurations
- `cloudwatch:GetMetricStatistics` — Read CloudWatch metrics
- `cloudtrail:LookupEvents` — Read audit logs
- `ssm:SendCommand` — Execute read-only PowerShell/bash checks on the instance

---

## 3. AI Troubleshooter

The **AI Troubleshooter** (`/troubleshoot`) is CloudOps's primary diagnostic tool. It:

1. Accepts an infrastructure question and optional EC2 instance ID
2. Executes parallel read-only AWS API queries (EC2, VPC, Security Groups, CloudWatch, CloudTrail, SSM)
3. Extracts discrete failure signals from raw telemetry
4. Embeds signals into ChromaDB to retrieve matching runbook solutions
5. Passes context to Qwen2.5-3B + QLoRA for structured reasoning
6. Validates the output against live AWS evidence
7. Returns a 6-field structured diagnosis: Problem Summary, Root Cause, Evidence, Impact, Recommendation, Confidence Score

### Confidence Score
The confidence score (0.0 to 1.0) reflects how strongly the live AWS evidence supports the diagnosis. High confidence (>0.8) means specific signals match the diagnosis. Low confidence (<0.5) means insufficient telemetry to confirm.

---

## 4. Support Agent

The **CloudOps Support Agent** (`/support`) is a conversational AI assistant that answers questions about:
- CloudOps platform features and architecture
- AWS cloud infrastructure concepts
- Troubleshooting guidance and best practices
- AI/LLM technologies (QLoRA, RAG, ChromaDB, Qwen2.5)

The Support Agent uses:
- **RAG retrieval** from a dedicated ChromaDB knowledge base (`cloudops_support` collection)
- **Entity-aware reranking** to surface the most relevant knowledge chunks
- **Qwen2.5-3B + QLoRA** local model (when configured) or intelligent synthesis
- **Conversation history** for follow-up question resolution
- **Grounding rules** to prevent hallucinations about AWS behavior

---

## 5. What Information Does the Troubleshooter Use?

The AI Troubleshooter collects:
- **EC2 Instance Details**: State, type, VPC ID, subnet ID, Security Group IDs, public/private IP
- **VPC & Subnet**: Subnet CIDR, availability zone, public IP auto-assignment setting
- **Security Group Rules**: All inbound and outbound rules (protocols, ports, sources)
- **Route Tables**: All routes associated with the instance's subnet
- **Network ACLs**: NACL rules for the subnet
- **CloudWatch Metrics**: CPUUtilization for the last 15 minutes (1-minute granularity)
- **CloudTrail Events**: Last 10 management events within 2 hours of analysis
- **SSM Host Check**: IIS/nginx/httpd service status, port listening status

---

## 6. Does CloudOps Automatically Fix AWS Problems?

**No.** CloudOps provides intelligent diagnosis and recommended remediation steps — it does not automatically execute those steps.

After the AI Troubleshooter provides a recommendation:
1. Review the diagnosis and evidence on the CloudOps dashboard
2. Evaluate the recommended steps
3. Apply the changes manually using the AWS Console, AWS CLI, or Terraform

This advisory design ensures human oversight over all infrastructure changes.

---

## 7. AI Stack Used by CloudOps

| Component | Technology |
| :--- | :--- |
| Base LLM | Qwen2.5-3B-Instruct (open-source, runs locally) |
| Fine-tuning | QLoRA (4-bit NF4, LoRA r=16, alpha=32) |
| Adapter (Troubleshooter) | outputs/adapter/ |
| Adapter (Support Agent) | outputs/support_agent_adapter/ |
| Embedding Model | sentence-transformers/all-MiniLM-L6-v2 |
| Vector Store | ChromaDB (persistent, cosine similarity) |
| Knowledge Base (Troubleshooter) | cloudops_knowledge collection |
| Knowledge Base (Support Agent) | cloudops_support collection |
| Quantization | BitsAndBytes 4-bit (GPU) or float32 (CPU) |
| AWS Integration | Boto3 (read-only) |

---

## 8. Regions and Availability

CloudOps connects to the AWS region configured in its backend environment (default: `us-east-1`). All Boto3 collectors use the configured region and assume the IAM role with read-only permissions.
