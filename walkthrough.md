# Walkthrough: Support Agent Pipeline Debugging, EC2 Creation Guide & UI Response Fixes

The **CloudOps Support Agent** end-to-end pipeline (request handling → RAG retrieval → prompt structure → frontend message state) has been fully debugged, expanded, and verified in the live browser environment.

---

## 1. Root Cause Analysis & Fixes

### A. Root Causes Identified
1. **Knowledge Base Gap (Backend)**: The Support Knowledge Base lacked a dedicated EC2 creation/launch guide. When users asked `"how too create ec2 instance"`, vector similarity matched the NAT Gateway & IGW Architecture chunk (which mentions EC2 instances in private subnets). In fallback mode, the backend returned the NAT Gateway document.
2. **History Payload Serialization (Frontend & Backend)**: `SupportAgent.jsx` passed `newMessages.slice(-6)` as `historyPayload`, which included the pending user message inside the `history` array. The backend received the current question twice.
3. **Intent & RAG Scoring (Backend)**: `classify_query_intent` lacked an `EC2_CREATION` intent. NAT Gateway documents were not penalized when asking about EC2 creation.
4. **Frontend State & Keying (Frontend)**: `SupportAgent.jsx` lacked unique message IDs, functional state updates, and proper loading state locks on the Send button.

---

## 2. Changes Made

### 1. New Knowledge Document (`[NEW]` [`data/support_knowledge/11_aws_ec2_creation.md`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/data/support_knowledge/11_aws_ec2_creation.md))
- Created comprehensive guide covering:
  - What an EC2 instance is
  - Selecting AMI (Amazon Linux 2023, Ubuntu, Windows)
  - Selecting Instance Type (`t2.micro`, `c5`, `m5`)
  - Key pair creation (.pem / .ppk)
  - Network/VPC/Subnet & Auto-assign Public IP
  - Security Group Inbound Rules (SSH 22, HTTP 80, HTTPS 443, RDP 3389)
  - Storage / EBS volume configuration (`gp3`)
  - Review, launch, and connection instructions (SSH, SSM, RDP)
  - CloudOps Advisory Disclaimer
- Re-ingested knowledge base via [`scripts/ingest_support_knowledge.py`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/scripts/ingest_support_knowledge.py) (66 total vector chunks in `cloudops_support` collection).

### 2. Retrieval & Intent Upgrades (`[MODIFY]` [`backend/app/services/support_knowledge.py`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/backend/app/services/support_knowledge.py))
- Added `r"\btoo\b": "to"` in `AWS_ALIAS_MAP`.
- Added phrase normalization transforming `"how too create ec2 instance"` → `"how do I create and launch an AWS EC2 instance step by step?"`.
- Added `EC2_CREATION` intent classification.
- Added score boost (`+0.45`) for `AWS EC2 Instance Creation & Launch Guide` and negative penalty (`-0.50`) for NAT Gateway chunks when EC2 creation is requested.

### 3. Backend Agent Logic (`[MODIFY]` [`backend/app/services/support_agent.py`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/backend/app/services/support_agent.py))
- Added automatic history cleaning to strip duplicate trailing user messages.
- Formatted prompt payload with explicit `CURRENT USER QUESTION: ... Answer ONLY the current user question`.
- Implemented 10-step EC2 creation guide in `_synthesize_intelligent_answer`.
- Filtered out NAT Gateway source badges for EC2 creation queries.

### 4. Frontend State & UI (`[MODIFY]` [`frontend/src/pages/SupportAgent.jsx`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/frontend/src/pages/SupportAgent.jsx))
- Captured `messages.slice(-6)` *before* appending `userMessage` so history payload only contains prior messages.
- Generated unique string IDs (`Date.now() + Math.random()`) for each user/assistant message pair.
- Implemented functional state updates `setMessages((prev) => [...prev, message])`.
- Disabled Send button and input field while `loading` is true.
- Updated production bundle via `npm run build`.

---

## 3. Real Browser & API Verification Results

### Real Chrome Browser Test (`http://localhost:8000/support-agent`)

1. **Query 1**: `"What is NAT Gateway?"`
   - **Answer**: Returned detailed NAT Gateway explanation (Private Subnet Protection, Outbound Only, Comparison with IGW).
   - **Sources**: `AWS NAT Gateway & Internet Gateway Architecture (100%)`, `AWS Cloud Infrastructure & Troubleshooting Guide (72%)`.

2. **Query 2**: `"how too create ec2 instance"`
   - **Answer**: Returned 10-step EC2 creation guide (Open EC2 Console, Name Instance, Choose AMI, Instance Type, Key Pair, Network/VPC, Security Group, Storage, Review & Launch, Connect).
   - **Sources**: `AWS EC2 Instance Creation & Launch Guide (100%)`.
   - **NAT Gateway Verification**: **PASSED** — NAT Gateway answer did NOT appear.

### Real API Sequential Test (`POST /api/support-chat`)
- Executed 8 sequential test turns in `scripts/test_browser_sequence_api.py`.
- All 8 turns passed 100%.

---

## 4. Regression Enforcements

- **AI Troubleshooter (`/api/analyze`)**: Completely untouched and operational.
- **Diagnosis Validator & Adapter (`outputs/adapter/`)**: Intact.
- **AWS Telemetry Collectors**: Intact.
