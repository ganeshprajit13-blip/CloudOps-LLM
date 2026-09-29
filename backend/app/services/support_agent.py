import os
import json
import logging
import threading
import time
from typing import List, Dict, Any, Optional, Tuple

from app.services.support_knowledge import query_support_knowledge, classify_query_intent, normalize_support_query
from app.services.fallback_llm import call_fallback_llm, is_fallback_llm_available
from app.core.config import settings

logger = logging.getLogger("cloudops.services.support_agent")

SUPPORT_ADAPTER_DIR = os.path.join(os.getcwd(), "outputs", "support_agent_adapter")
BASE_MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"


class SupportModelManager:
    """
    Singleton manager for loading local Qwen2.5-3B-Instruct + Support Agent QLoRA adapter
    from outputs/support_agent_adapter/ for primary offline inference.
    """
    _lock = threading.Lock()
    _model = None
    _tokenizer = None
    _status = "UNINITIALIZED"

    @classmethod
    def get_instance(cls):
        if cls._model is not None and cls._tokenizer is not None:
            return cls._model, cls._tokenizer, cls._status

        with cls._lock:
            if cls._model is not None and cls._tokenizer is not None:
                return cls._model, cls._tokenizer, cls._status

            logger.info("Initializing local Support Agent model (Qwen2.5-3B + outputs/support_agent_adapter)...")
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
                from peft import PeftModel

                if not os.path.exists(os.path.join(SUPPORT_ADAPTER_DIR, "adapter_config.json")):
                    logger.warning(f"Support Agent adapter not found at '{SUPPORT_ADAPTER_DIR}'.")
                    cls._status = "ADAPTER_NOT_FOUND"
                    return None, None, cls._status

                tokenizer = AutoTokenizer.from_pretrained(SUPPORT_ADAPTER_DIR)
                if torch.cuda.is_available():
                    from transformers import BitsAndBytesConfig
                    quant_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_compute_dtype=torch.float16
                    )
                    model = AutoModelForCausalLM.from_pretrained(
                        BASE_MODEL_NAME,
                        quantization_config=quant_config,
                        device_map="auto",
                        trust_remote_code=True,
                        local_files_only=True
                    )
                else:
                    model = AutoModelForCausalLM.from_pretrained(
                        BASE_MODEL_NAME,
                        torch_dtype=torch.float32,
                        trust_remote_code=True,
                        local_files_only=True
                    )

                model = PeftModel.from_pretrained(model, SUPPORT_ADAPTER_DIR)
                cls._model = model
                cls._tokenizer = tokenizer
                cls._status = "LOADED"
                logger.info("Local Support Agent model loaded successfully with 4-bit QLoRA adapter.")
                return cls._model, cls._tokenizer, cls._status
            except Exception as err:
                logger.error(f"Failed to load local Support Agent model: {err}")
                cls._status = f"FAILED: {err}"
                return None, None, cls._status


def generate_support_system_prompt(context_str: str) -> str:
    """Constructs a grounded system prompt for the CloudOps Support Agent."""
    return (
        "You are CloudOps Support Agent, a technical support assistant for the CloudOps LLM platform.\n\n"
        "Your job is to answer the user's EXACT question directly, clearly, and conversationally.\n\n"
        "STRICT RESPONSE RULES:\n"
        "1. READ the user's question carefully. Identify the EXACT entity they are asking about.\n"
        "2. Answer THAT specific entity first — do not start with a different, tangentially related topic.\n"
        "3. Use retrieved knowledge as supporting factual reference, NOT as text to dump verbatim.\n"
        "4. NEVER open your answer by explaining a different AWS service than the one asked about.\n"
        "5. For AWS concept questions ('What is X?'), lead with a direct 1-sentence definition of X.\n"
        "6. For troubleshooting questions ('Why is X broken?'), lead with the most likely root cause.\n"
        "7. For how-to questions ('How do I do X?'), provide step-by-step instructions.\n"
        "8. For comparison questions ('X vs Y?'), use a structured table or bullet list.\n"
        "9. Understand follow-up questions from conversation history naturally (resolve 'it', 'this', 'that').\n"
        "10. You are advisory-only. You NEVER automatically modify AWS infrastructure.\n"
        "11. Be concise for simple questions. Be detailed for complex questions.\n"
        "12. If the retrieved context is about a different topic than the question, ignore it and answer from knowledge.\n"
        "13. If genuinely uncertain about a specific detail, say so clearly rather than hallucinating.\n"
        "14. For out-of-scope questions (unrelated to CloudOps/AWS/cloud/DevOps/AI), respond: "
        "'I'm focused on CloudOps, AWS, cloud infrastructure, DevOps, and AI technologies. "
        "I can help with questions in those areas.'\n\n"
        f"RETRIEVED KNOWLEDGE BASE CONTEXT:\n{context_str.strip() if context_str.strip() else 'No relevant knowledge context retrieved.'}"
    )


def resolve_followup_context(user_message: str, history: List[Dict[str, str]]) -> str:
    """
    Inspects recent conversation history to resolve pronouns and entity references.
    Returns augmented query string for retrieval.
    """
    msg_lower = user_message.lower().strip()
    pronoun_triggers = [
        "it", "this", "that", "how is it", "why do we need it", "how is it different",
        "instead", "is it inside", "how does it work", "what does it do", "can it",
        "when is it used", "why use it", "how to configure it"
    ]

    if not any(p in msg_lower for p in pronoun_triggers) or not history:
        return user_message

    # Entity extraction from recent history (last 6 messages)
    entity_map = [
        (["nacl", "network access control list", "network acl"], "NACL Network Access Control List"),
        (["nat gateway", "nat "], "NAT Gateway"),
        (["internet gateway", "igw"], "Internet Gateway"),
        (["security group", "inbound rule", "outbound rule"], "Security Group"),
        (["cloudtrail", "audit log", "who changed"], "CloudTrail"),
        (["cloudwatch", "metric", "alarm", "cpuutilization"], "CloudWatch"),
        (["qlora", "lora", "quantization", "4-bit"], "QLoRA"),
        (["rag", "retrieval augmented", "chromadb", "embedding"], "RAG"),
        (["vpc", "virtual private cloud"], "VPC Virtual Private Cloud"),
        (["subnet", "public subnet", "private subnet"], "subnet"),
        (["route table", "routing"], "Route Table"),
        (["iam", "identity access", "iam role"], "IAM role"),
        (["dns", "domain name", "route 53"], "DNS Route 53"),
        (["rdp", "remote desktop", "3389"], "RDP Remote Desktop Protocol"),
        (["docker", "container", "dockerfile"], "Docker container"),
        (["kubernetes", "k8s", "pod "], "Kubernetes"),
        (["terraform", "hcl", "infrastructure as code"], "Terraform"),
        (["ec2", "instance", "virtual machine"], "EC2 instance"),
        (["ami", "amazon machine image"], "AMI Amazon Machine Image"),
        (["ebs", "elastic block store", "volume"], "EBS Elastic Block Store"),
        (["iis", "w3svc", "internet information services"], "IIS web server"),
        (["cloudops", "troubleshooter", "support agent"], "CloudOps"),
    ]

    for prev_msg in reversed(history[-6:]):
        prev_content = prev_msg.get("content", "").lower()
        for keywords, entity_label in entity_map:
            if any(kw in prev_content for kw in keywords):
                augmented = f"{user_message} (context: {entity_label})"
                logger.info(f"Follow-up resolution: '{user_message}' -> '{augmented}'")
                return augmented

    return user_message


def is_local_answer_insufficient(
    answer: Optional[str],
    retrieved_chunks: List[Dict[str, Any]],
    user_query: str
) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether the local model's response is insufficient, ungrounded,
    or low confidence — justifying fallback LLM invocation.
    """
    if not answer or not answer.strip():
        return True, "Empty response from local model"

    ans_clean = answer.strip()
    ans_lower = ans_clean.lower()

    if len(ans_clean) < 35:
        return True, f"Response too short ({len(ans_clean)} chars)"

    refusal_phrases = [
        "i don't know",
        "i do not know",
        "i cannot answer",
        "i can't answer",
        "not enough information",
        "insufficient information",
        "information is currently unavailable",
        "information is unavailable",
        "as an ai, i cannot",
        "no relevant knowledge",
        "i am unable to provide",
        "i lack the information",
        "sufficient information is currently unavailable"
    ]
    for phrase in refusal_phrases:
        if phrase in ans_lower:
            return True, f"Local model returned uncertainty/refusal phrase: '{phrase}'"

def _synthesize_rca_remediation(rca_context: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """
    Synthesizes a structured, guided AI Support Remediation workflow (CHECK, FIX, VERIFY)
    based strictly on provided RCA diagnostic context. Does not invent commands or auto-execute.
    """
    import re
    problem = rca_context.get("problem") or rca_context.get("incident") or "Cloud Infrastructure Issue"
    resource_id = rca_context.get("target_resource_id") or rca_context.get("resource_id") or rca_context.get("target_resource") or "target-resource"
    resource_type = rca_context.get("resource_type") or "AWS Resource"
    root_cause = rca_context.get("probable_root_cause") or rca_context.get("root_cause") or "Undetermined cause"
    recommendation = rca_context.get("recommendation") or rca_context.get("recommended_remediation") or "Review telemetry and configuration."
    evidence_list = rca_context.get("evidence") or []
    impact = rca_context.get("user_impact") or rca_context.get("impact") or "Service connectivity or availability is impacted."
    confidence = rca_context.get("confidence", 0.9)

    evidence_text = ""
    if isinstance(evidence_list, list):
        evidence_text = "\n".join([f"- {e}" for e in evidence_list])
    elif isinstance(evidence_list, str):
        evidence_text = f"- {evidence_list}"

    combined_text = f"{problem} {root_cause} {recommendation} {evidence_text}".lower()

    # Detect if evidence or root cause indicates insufficient telemetry
    is_insufficient = (
        "insufficient" in combined_text or
        "undetermined" in combined_text or
        "inconclusive" in combined_text or
        (isinstance(confidence, (int, float)) and confidence < 0.40)
    )

    if is_insufficient:
        answer_text = (
            f"### 📋 Issue Summary\n"
            f"**Target Resource**: `{resource_id}` ({resource_type})\n"
            f"**Observed Problem**: {problem}\n"
            f"**Diagnostic Status**: **Insufficient Telemetry Evidence Available**\n\n"
            f"> ⚠️ **Safety Mode**: AI Support is in **READ / EXPLAIN** mode. **No fix will be invented or applied** without verified empirical evidence.\n\n"
            f"---\n\n"
            f"### 🔍 1. REQUIRED EVIDENCE TO COLLECT\n"
            f"The collected telemetry does not contain sufficient empirical evidence to establish root cause. Before applying any remediation:\n\n"
            f"1. **EC2 Instance State**: Confirm that instance `{resource_id}` is `running` with `2/2 status checks passed`.\n"
            f"2. **Host Telemetry (SSM)**: Verify AWS Systems Manager SSM Agent status on the host to enable OS service state checks (e.g. W3SVC, Windows Firewall, port bindings).\n"
            f"3. **Network Telemetry**: Audit attached Security Groups, Route Tables, and NACL inbound/outbound rules for explicit blocks.\n"
            f"4. **CloudWatch Metrics**: Collect CPUUtilization, NetworkIn/Out, and disk metrics over a 30-minute window.\n\n"
            f"---\n\n"
            f"### 🛠️ 2. RECOMMENDED NEXT STEP\n"
            f"Re-run the scan on the **AI Troubleshooter** (`/troubleshoot`) with **Live Data Collection** enabled after verifying IAM read permissions (`ReadOnlyAccess`)."
        )
        return {
            "answer": answer_text,
            "reply": answer_text,
            "sources": [],
            "provider": "local_guided_remediation",
            "fallback_used": False
        }

    # Case 1: W3SVC / IIS Stopped
    if "w3svc" in combined_text or "iis" in combined_text or "world wide web publishing" in combined_text:
        answer_text = (
            f"### 📋 Issue Summary\n"
            f"**Target Resource**: `{resource_id}` ({resource_type})\n"
            f"**Observed Problem**: {problem}\n"
            f"**Probable Root Cause**: {root_cause}\n\n"
            f"> ⚠️ **Safety Mode**: AI Support is in **READ / EXPLAIN** mode. No automated server modifications will be executed.\n\n"
            f"---\n\n"
            f"### 🔍 1. CHECK (Diagnostic / Preliminary Verification)\n"
            f"Connect to Windows EC2 instance `{resource_id}` via **AWS SSM Session Manager** or Remote Desktop (RDP), then run PowerShell:\n\n"
            f"```powershell\n"
            f"# Inspect W3SVC (World Wide Web Publishing Service) operational status\n"
            f"Get-Service W3SVC\n"
            f"```\n\n"
            f"---\n\n"
            f"### 🛠️ 2. FIX (Step-by-Step Remediation)\n"
            f"If `Status` is `Stopped`:\n\n"
            f"1. Open Administrator PowerShell on target instance `{resource_id}`.\n"
            f"2. Execute the service start command:\n"
            f"```powershell\n"
            f"Start-Service W3SVC\n"
            f"```\n"
            f"3. (Optional) Configure Automatic startup type to prevent downtime upon reboot:\n"
            f"```powershell\n"
            f"Set-Service -Name W3SVC -StartupType Automatic\n"
            f"```\n\n"
            f"---\n\n"
            f"### ✅ 3. VERIFY (Validation & Expected Result)\n"
            f"1. Re-check W3SVC service status:\n"
            f"```powershell\n"
            f"Get-Service W3SVC\n"
            f"```\n"
            f"2. Verify local IIS web server responsiveness:\n"
            f"```powershell\n"
            f"curl http://localhost\n"
            f"```\n"
            f"3. Test public HTTP access from external browser to `http://<EC2-Public-IP>`.\n\n"
            f"**Expected Result**:\n"
            f"`Get-Service W3SVC` returns `Status: Running`, and the IIS web server responds successfully."
        )
        return {
            "answer": answer_text,
            "reply": answer_text,
            "sources": [{"title": "Windows IIS W3SVC Troubleshooting Guide", "category": "host_services", "relevance": 1.0}],
            "provider": "local_guided_remediation",
            "fallback_used": False
        }

    # Case 2: Security Group Missing HTTP Port 80
    if "port 80" in combined_text or ("http" in combined_text and ("missing" in combined_text or "block" in combined_text or "rule" in combined_text)):
        sg_id = "sg-xxxxxxxx"
        sg_match = re.search(r"sg-[0-9a-f]{8,17}", combined_text)
        if sg_match:
            sg_id = sg_match.group(0)

        answer_text = (
            f"### 📋 Issue Summary\n"
            f"**Target Resource**: `{resource_id}` ({resource_type})\n"
            f"**Security Group**: `{sg_id}`\n"
            f"**Observed Problem**: {problem}\n"
            f"**Probable Root Cause**: {root_cause}\n\n"
            f"> ⚠️ **Safety Mode**: AI Support is in **READ / EXPLAIN** mode. No automated Security Group modifications will be executed.\n\n"
            f"---\n\n"
            f"### 🔍 1. CHECK (Diagnostic / Preliminary Verification)\n"
            f"Inspect inbound rules for attached Security Group `{sg_id}`:\n\n"
            f"```bash\n"
            f"# AWS CLI: Describe inbound security group rules\n"
            f"aws ec2 describe-security-groups --group-ids {sg_id} --query \"SecurityGroups[*].IpPermissions\"\n"
            f"```\n\n"
            f"---\n\n"
            f"### 🛠️ 2. FIX (Step-by-Step Remediation)\n"
            f"**Option A: AWS Management Console**\n"
            f"1. Open **AWS EC2 Console** → Go to **Network & Security** → **Security Groups**.\n"
            f"2. Select Security Group `{sg_id}`.\n"
            f"3. Select **Inbound rules** tab → Click **Edit inbound rules**.\n"
            f"4. Click **Add rule**:\n"
            f"   - **Type**: `HTTP`\n"
            f"   - **Protocol**: `TCP`\n"
            f"   - **Port Range**: `80`\n"
            f"   - **Source**: `0.0.0.0/0` (Anywhere IPv4)\n"
            f"5. Click **Save rules**.\n\n"
            f"**Option B: AWS CLI Command**\n"
            f"```bash\n"
            f"aws ec2 authorize-security-group-ingress \\\n"
            f"  --group-id {sg_id} \\\n"
            f"  --protocol tcp \\\n"
            f"  --port 80 \\\n"
            f"  --cidr 0.0.0.0/0\n"
            f"```\n\n"
            f"---\n\n"
            f"### ✅ 3. VERIFY (Validation & Expected Result)\n"
            f"1. Verify Security Group rule authorization:\n"
            f"```bash\n"
            f"aws ec2 describe-security-groups --group-ids {sg_id} --output table\n"
            f"```\n"
            f"2. Test HTTP connectivity from client:\n"
            f"```bash\n"
            f"curl -I http://<EC2-Public-IP>\n"
            f"```\n\n"
            f"**Expected Result**:\n"
            f"Inbound TCP 80 rule is active on `{sg_id}`, and HTTP connection succeeds with HTTP `200 OK`."
        )
        return {
            "answer": answer_text,
            "reply": answer_text,
            "sources": [{"title": "AWS Security Group Inbound Rule Configuration", "category": "network_security", "relevance": 1.0}],
            "provider": "local_guided_remediation",
            "fallback_used": False
        }

    # Case 3: Security Group Missing HTTPS Port 443
    if "port 443" in combined_text or ("https" in combined_text and ("missing" in combined_text or "block" in combined_text or "rule" in combined_text)):
        sg_id = "sg-xxxxxxxx"
        sg_match = re.search(r"sg-[0-9a-f]{8,17}", combined_text)
        if sg_match:
            sg_id = sg_match.group(0)

        answer_text = (
            f"### 📋 Issue Summary\n"
            f"**Target Resource**: `{resource_id}` ({resource_type})\n"
            f"**Security Group**: `{sg_id}`\n"
            f"**Observed Problem**: {problem}\n"
            f"**Probable Root Cause**: {root_cause}\n\n"
            f"> ⚠️ **Safety Mode**: AI Support is in **READ / EXPLAIN** mode. No automated Security Group modifications will be executed.\n\n"
            f"---\n\n"
            f"### 🔍 1. CHECK (Diagnostic / Preliminary Verification)\n"
            f"Inspect Security Group `{sg_id}` inbound HTTPS rules:\n\n"
            f"```bash\n"
            f"aws ec2 describe-security-groups --group-ids {sg_id} --query \"SecurityGroups[*].IpPermissions\"\n"
            f"```\n\n"
            f"---\n\n"
            f"### 🛠️ 2. FIX (Step-by-Step Remediation)\n"
            f"**Option A: AWS Management Console**\n"
            f"1. Open **AWS EC2 Console** → **Security Groups** → Select `{sg_id}`.\n"
            f"2. Click **Inbound rules** tab → **Edit inbound rules**.\n"
            f"3. Add rule:\n"
            f"   - **Type**: `HTTPS`\n"
            f"   - **Protocol**: `TCP`\n"
            f"   - **Port Range**: `443`\n"
            f"   - **Source**: `0.0.0.0/0` (Anywhere IPv4)\n"
            f"4. Click **Save rules**.\n\n"
            f"**Option B: AWS CLI Command**\n"
            f"```bash\n"
            f"aws ec2 authorize-security-group-ingress \\\n"
            f"  --group-id {sg_id} \\\n"
            f"  --protocol tcp \\\n"
            f"  --port 443 \\\n"
            f"  --cidr 0.0.0.0/0\n"
            f"```\n\n"
            f"---\n\n"
            f"### ✅ 3. VERIFY (Validation & Expected Result)\n"
            f"1. Test HTTPS connection:\n"
            f"```bash\n"
            f"curl -Iv https://<EC2-Public-IP>\n"
            f"```\n\n"
            f"**Expected Result**:\n"
            f"Inbound TCP 443 rule is active on `{sg_id}`, and HTTPS handshake completes successfully."
        )
        return {
            "answer": answer_text,
            "reply": answer_text,
            "sources": [{"title": "AWS Security Group Inbound Rule Configuration", "category": "network_security", "relevance": 1.0}],
            "provider": "local_guided_remediation",
            "fallback_used": False
        }

    # Case 4: High CPU Utilization
    if "cpu" in combined_text or "utilization" in combined_text:
        answer_text = (
            f"### 📋 Issue Summary\n"
            f"**Target Resource**: `{resource_id}` ({resource_type})\n"
            f"**Observed Problem**: {problem}\n"
            f"**Probable Root Cause**: {root_cause}\n\n"
            f"> ⚠️ **Safety Mode**: AI Support is in **READ / EXPLAIN** mode. No process terminations or instance state changes will be executed automatically.\n\n"
            f"---\n\n"
            f"### 🔍 1. CHECK (Diagnostic / Preliminary Verification)\n"
            f"Identify processes consuming high CPU on `{resource_id}`:\n\n"
            f"**Linux**:\n"
            f"```bash\n"
            f"ps aux --sort=-%cpu | head -10\n"
            f"top -bn1 | head -20\n"
            f"```\n\n"
            f"**Windows (PowerShell)**:\n"
            f"```powershell\n"
            f"Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, Id, CPU\n"
            f"```\n\n"
            f"---\n\n"
            f"### 🛠️ 2. FIX (Step-by-Step Remediation)\n"
            f"1. Terminate or restart stuck/runaway processes:\n"
            f"   - **Linux**: `kill -9 <PID>` or `systemctl restart <service-name>`\n"
            f"   - **Windows**: `Stop-Process -Id <PID>`\n"
            f"2. If CPU utilization is caused by legitimate traffic volume:\n"
            f"   - Scale instance `{resource_id}` to a larger instance type (e.g. `t3.medium` -> `t3.large`).\n"
            f"   - Audit CloudWatch CPU Credit Balance for burstable `t2`/`t3` instance throttling.\n\n"
            f"---\n\n"
            f"### ✅ 3. VERIFY (Validation & Expected Result)\n"
            f"1. Re-evaluate process CPU usage:\n"
            f"   - **Linux**: `ps aux --sort=-%cpu | head -5`\n"
            f"   - **Windows**: `Get-Process | Sort-Object CPU -Descending | Select-Object -First 5`\n"
            f"2. Monitor CloudWatch `CPUUtilization` metric.\n\n"
            f"**Expected Result**:\n"
            f"Top process CPU usage drops below threshold (<70%), and overall CPU utilization normalizes."
        )
        return {
            "answer": answer_text,
            "reply": answer_text,
            "sources": [{"title": "AWS EC2 High CPU Diagnostics & Remediation", "category": "compute", "relevance": 1.0}],
            "provider": "local_guided_remediation",
            "fallback_used": False
        }

    # Case 5: Disk Full / Storage Capacity Exceeded
    if "disk" in combined_text or "storage" in combined_text:
        answer_text = (
            f"### 📋 Issue Summary\n"
            f"**Target Resource**: `{resource_id}` ({resource_type})\n"
            f"**Observed Problem**: {problem}\n"
            f"**Probable Root Cause**: {root_cause}\n\n"
            f"> ⚠️ **Safety Mode**: AI Support is in **READ / EXPLAIN** mode. No automated file deletion or volume modifications will be executed.\n\n"
            f"---\n\n"
            f"### 🔍 1. CHECK (Diagnostic / Preliminary Verification)\n"
            f"Inspect filesystem usage and largest directories on `{resource_id}`:\n\n"
            f"**Linux**:\n"
            f"```bash\n"
            f"df -h\n"
            f"du -sh /var/log/* | sort -hr | head -10\n"
            f"```\n\n"
            f"**Windows (PowerShell)**:\n"
            f"```powershell\n"
            f"Get-PSDrive -PSProvider FileSystem\n"
            f"```\n\n"
            f"---\n\n"
            f"### 🛠️ 2. FIX (Step-by-Step Remediation)\n"
            f"**Option A: Clean Up Temporary Files & Logs**\n"
            f"- **Linux**: Truncate old system logs: `sudo journalctl --vacuum-time=3d`\n"
            f"- **Windows**: Truncate IIS logs in `C:\\inetpub\\logs\\LogFiles\\`\n\n"
            f"**Option B: Expand EBS Volume Size**\n"
            f"1. Open **AWS EC2 Console** → **Volumes** → Select root volume for `{resource_id}`.\n"
            f"2. Click **Actions** → **Modify Volume** → Increase volume size (e.g. 30 GB to 50 GB).\n"
            f"3. Extend OS filesystem partition:\n"
            f"   - **Linux**: `sudo growpart /dev/xvda 1` && `sudo resize2fs /dev/xvda1`\n"
            f"   - **Windows**: Open Disk Management → Extend Volume.\n\n"
            f"---\n\n"
            f"### ✅ 3. VERIFY (Validation & Expected Result)\n"
            f"1. Check free storage capacity:\n"
            f"   - **Linux**: `df -h`\n"
            f"   - **Windows**: `Get-PSDrive`\n\n"
            f"**Expected Result**:\n"
            f"Filesystem shows >20% free space available."
        )
        return {
            "answer": answer_text,
            "reply": answer_text,
            "sources": [{"title": "AWS EBS Volume Expansion & Disk Cleanup Guide", "category": "storage", "relevance": 1.0}],
            "provider": "local_guided_remediation",
            "fallback_used": False
        }

    # Default / General RCA Guided Remediation Fallback
    answer_text = (
        f"### 📋 Issue Summary\n"
        f"**Target Resource**: `{resource_id}` ({resource_type})\n"
        f"**Observed Problem**: {problem}\n"
        f"**Probable Root Cause**: {root_cause}\n"
        f"**User Impact**: {impact}\n\n"
        f"> ⚠️ **Safety Mode**: AI Support is in **READ / EXPLAIN** mode. No automated modifications will be executed.\n\n"
        f"---\n\n"
        f"### 🔍 1. CHECK (Diagnostic / Preliminary Verification)\n"
        f"Verify resource configuration and telemetry evidence:\n"
        f"{evidence_text if evidence_text else '- Telemetry shows resource operational anomalies.'}\n\n"
        f"---\n\n"
        f"### 🛠️ 2. FIX (Step-by-Step Remediation)\n"
        f"Execute the recommended remediation step manually:\n\n"
        f"```text\n"
        f"{recommendation}\n"
        f"```\n\n"
        f"---\n\n"
        f"### ✅ 3. VERIFY (Validation & Expected Result)\n"
        f"1. Re-evaluate resource telemetry and status checks.\n"
        f"2. Confirm that service metrics return to healthy thresholds.\n\n"
        f"**Expected Result**:\n"
        f"Resource `{resource_id}` state normalizes and service availability is restored."
    )
    return {
        "answer": answer_text,
        "reply": answer_text,
        "sources": [{"title": "CloudOps RCA Guided Remediation", "category": "general", "relevance": 1.0}],
        "provider": "local_guided_remediation",
        "fallback_used": False
    }


def ask_support_agent(
    user_message: str,
    history: List[Dict[str, str]] = None,
    rca_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main Support Agent Pipeline:
    1. RCA Context Guided Remediation Interception (if rca_context provided)
    2. Greeting & Advisory Guardrail Intent Interception
    3. Follow-Up Resolution & Query Normalization
    4. Support RAG Retrieval with Entity-Aware Reranking
    5. PRIMARY: Local Knowledge Synthesis (or QLoRA model if enabled)
    6. FALLBACK: Fallback LLM if local answer insufficient
    7. GRACEFUL DEGRADATION if both fail
    """
    history = history or []
    logger.info(f"Support Agent query received: '{user_message}' (has_rca_context={rca_context is not None})")

    # If RCA Context is passed from Troubleshooter, synthesize guided remediation workflow
    if rca_context and isinstance(rca_context, dict):
        return _synthesize_rca_remediation(rca_context, user_message)

    if not user_message or not user_message.strip():
        return {
            "answer": "Please provide a valid question or technical inquiry.",
            "reply": "Please provide a valid question or technical inquiry.",
            "sources": [],
            "provider": "local_guardrail",
            "fallback_used": False
        }

    # Clean history: remove duplicate of current query
    cleaned_history = []
    for m in history:
        if isinstance(m, dict) and m.get("role") and m.get("content"):
            if m.get("role") == "user" and m.get("content", "").strip().lower() == user_message.strip().lower():
                continue
            cleaned_history.append({"role": m["role"], "content": m["content"]})

    # 1. Greeting Intent
    intent = classify_query_intent(user_message)
    if intent == "GREETING":
        greeting_text = (
            "Hi! I'm the **CloudOps Support Agent**. I can help you with:\n\n"
            "- **AWS** cloud infrastructure (EC2, VPC, Security Groups, IAM, CloudWatch, CloudTrail)\n"
            "- **CloudOps** platform features (AI Troubleshooter, diagnosis output, advisory-only behavior)\n"
            "- **DevOps** topics (Docker, Kubernetes, Terraform, CI/CD)\n"
            "- **AI/LLM** architecture (QLoRA, RAG, ChromaDB, Qwen2.5)\n\n"
            "What would you like to know?"
        )
        return {
            "answer": greeting_text,
            "reply": greeting_text,
            "sources": [],
            "provider": "local_guardrail",
            "fallback_used": False
        }

    # 2. Out of scope
    if intent == "OUT_OF_SCOPE":
        oos_text = (
            "I'm focused on **CloudOps**, AWS cloud infrastructure, DevOps, and the AI technologies used by this platform. "
            "I can help with questions about EC2, VPC, Security Groups, IAM, CloudWatch, CloudTrail, Docker, Kubernetes, Terraform, QLoRA, and RAG. "
            "I'm not able to help with that particular topic."
        )
        return {
            "answer": oos_text,
            "reply": oos_text,
            "sources": [],
            "provider": "local_guardrail",
            "fallback_used": False
        }

    # 3. Advisory Guardrails
    if intent == "GUARDRAILS" or (
        any(k in user_message.lower() for k in ["change", "open port", "modify", "delete", "fix it for me"])
        and "automatically" in user_message.lower()
    ):
        guardrail_text = (
            "As the **CloudOps Support Agent**, I provide technical guidance and diagnostic advisory recommendations. "
            "I do **not** automatically execute AWS infrastructure modifications or autonomously modify your resources "
            "(such as Security Groups, Route Tables, or EC2 instances).\n\n"
            "To resolve infrastructure issues or update security configurations:\n"
            "1. Run a diagnostic scan on the **AI Troubleshooter** page (`/troubleshoot`).\n"
            "2. Review the 6-field output diagnosis and evidence.\n"
            "3. Apply the recommended remediation steps manually using your AWS Console or Terraform."
        )
        return {
            "answer": guardrail_text,
            "reply": guardrail_text,
            "sources": [],
            "provider": "local_guardrail",
            "fallback_used": False
        }

    try:
        # 4. Resolve follow-up pronouns
        augmented_query = resolve_followup_context(user_message, cleaned_history)

        # 5. Entity-Aware RAG Retrieval
        retrieved_chunks, detected_intent = query_support_knowledge(augmented_query, top_k=3, min_score=0.25)
        logger.info(f"Retrieved {len(retrieved_chunks)} chunks. Intent: {detected_intent}")

        # Build context string and sources payload
        sources = []
        context_str = ""
        seen_titles = set()

        for idx, item in enumerate(retrieved_chunks, start=1):
            title = item.get("title", "Support Guide")
            # Source filtering: skip NAT/IGW docs for EC2 creation queries
            if detected_intent == "EC2_CREATION" and any(
                k in title.lower() for k in ["nat gateway", "internet gateway"]
            ):
                continue
            if title not in seen_titles and len(sources) < 3:
                seen_titles.add(title)
                rel_score = item.get("relevance", item.get("score", 1.0))
                sources.append({
                    "title": title,
                    "category": item.get("category", "general"),
                    "relevance": rel_score,
                    "score": rel_score
                })
            context_str += f"\n--- Knowledge Ref #{idx}: {title} ---\n{item['content']}\n"

        system_prompt = generate_support_system_prompt(context_str)
        bounded_history = cleaned_history[-6:]

        # =========================================================================
        # 6. PRIMARY: Local Support QLoRA Model (if enabled)
        # =========================================================================
        local_answer: Optional[str] = None
        use_local_model_env = os.getenv("USE_LOCAL_SUPPORT_MODEL", "0")

        if use_local_model_env == "1":
            model, tokenizer, status = SupportModelManager.get_instance()
            if model is not None and tokenizer is not None:
                try:
                    chat = [{"role": "system", "content": system_prompt}]
                    chat.extend(bounded_history)
                    chat.append({"role": "user", "content": f"CURRENT USER QUESTION:\n{user_message}"})

                    prompt_text = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
                    inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)

                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=512,
                        temperature=0.3,
                        do_sample=True,
                        pad_token_id=tokenizer.eos_token_id
                    )
                    gen_text = tokenizer.decode(
                        outputs[0][inputs["input_ids"].shape[1]:],
                        skip_special_tokens=True
                    ).strip()
                    if gen_text:
                        local_answer = gen_text
                        logger.info("Local Support QLoRA model generated answer successfully.")
                except Exception as local_err:
                    logger.warning(f"Local Support Model generation error: {local_err}")

        # Fall through to intelligent synthesis if model not used or failed
        if not local_answer:
            local_answer = _synthesize_intelligent_answer(
                augmented_query, detected_intent, retrieved_chunks, bounded_history, user_message
            )

        # =========================================================================
        # 7. FALLBACK DECISION
        # =========================================================================
        is_insufficient, fallback_reason = is_local_answer_insufficient(
            local_answer, retrieved_chunks, user_message
        )

        if not is_insufficient:
            logger.info("Local synthesis answer is sufficient.")
            return {
                "answer": local_answer,
                "reply": local_answer,
                "sources": sources,
                "provider": "local_qlora",
                "fallback_used": False
            }

        # =========================================================================
        # 8. FALLBACK LLM
        # =========================================================================
        logger.info(f"Local answer flagged insufficient ({fallback_reason}). Triggering Fallback LLM...")
        fallback_result = call_fallback_llm(
            question=user_message,
            rag_context=context_str,
            history=bounded_history,
            local_model_answer=local_answer,
            fallback_reason=fallback_reason
        )

        if fallback_result.get("success") and fallback_result.get("answer"):
            fallback_answer = fallback_result["answer"]
            valid_sources = sources if len(retrieved_chunks) > 0 else []
            logger.info(f"Fallback LLM completed (model: {fallback_result.get('model_used')}).")
            return {
                "answer": fallback_answer,
                "reply": fallback_answer,
                "sources": valid_sources,
                "provider": "fallback_llm",
                "fallback_used": True
            }

        # =========================================================================
        # 9. GRACEFUL DEGRADATION
        # =========================================================================
        logger.warning(f"Fallback LLM failed: {fallback_result.get('error')}. Using local response.")

        if local_answer and "unavailable in the support knowledge base" not in local_answer.lower() and len(local_answer.strip()) > 30:
            return {
                "answer": local_answer,
                "reply": local_answer,
                "sources": sources,
                "provider": "local_fallback_failure",
                "fallback_used": True
            }

        clarification_msg = (
            f"Regarding **\"{user_message.strip()}\"**:\n\n"
            "I could not retrieve a matching document for this specific inquiry. "
            "Could you clarify the specific AWS service, resource configuration, or troubleshooting step you need help with?"
        )
        return {
            "answer": clarification_msg,
            "reply": clarification_msg,
            "sources": [],
            "provider": "local_fallback_failure",
            "fallback_used": True
        }

    except Exception as exc:
        logger.error(f"Support Agent processing error: {exc}", exc_info=True)
        return {
            "answer": "The CloudOps Support Agent encountered a temporary processing error. Please retry your inquiry.",
            "reply": "The CloudOps Support Agent encountered a temporary processing error. Please retry your inquiry.",
            "sources": [],
            "provider": "local_fallback_failure",
            "fallback_used": True
        }


def _synthesize_intelligent_answer(
    query: str,
    intent: str,
    chunks: List[Dict[str, Any]],
    history: List[Dict[str, str]],
    original_query: str = ""
) -> str:
    """
    Synthesizes direct, factual technical answers covering 30+ intent categories.
    Falls back to best retrieved chunk when no specific case matches.
    """
    q_lower = (original_query or query).lower()

    # ================================================================
    # GREETING / OUT_OF_SCOPE / GUARDRAILS (handled upstream, but safe fallback)
    # ================================================================
    if intent == "GREETING":
        return "Hi! I'm the CloudOps Support Agent. How can I help you with AWS, CloudOps, or DevOps today?"

    if intent == "OUT_OF_SCOPE":
        return (
            "I'm focused on CloudOps, AWS cloud infrastructure, DevOps, and AI technologies. "
            "I can help with questions about EC2, VPC, Security Groups, IAM, CloudWatch, CloudTrail, "
            "Docker, Kubernetes, Terraform, QLoRA, and RAG. I'm not able to help with that particular topic."
        )

    # ================================================================
    # VPC
    # ================================================================
    if intent == "VPC" or ("vpc" in q_lower and "what is" in q_lower) or ("virtual private cloud" in q_lower and "what" in q_lower):
        return (
            "A **VPC (Virtual Private Cloud)** is a logically isolated, private network within AWS where you run your "
            "cloud resources — EC2 instances, RDS databases, Lambda functions, and more.\n\n"
            "### Key VPC Components:\n"
            "- **CIDR Block**: IP address range for your VPC (e.g., `10.0.0.0/16` = 65,536 IPs)\n"
            "- **Subnets**: Subdivisions of the VPC in specific Availability Zones (public or private)\n"
            "- **Route Tables**: Rules that direct network traffic between subnets and to the internet\n"
            "- **Internet Gateway (IGW)**: Connects your VPC to the public internet\n"
            "- **NAT Gateway**: Gives private subnet instances outbound internet access\n"
            "- **Security Groups**: Stateful instance-level firewalls\n"
            "- **NACLs**: Stateless subnet-level firewalls\n\n"
            "Every AWS account gets a **Default VPC** per region for quick use. Production workloads should use **custom VPCs** "
            "with properly designed public/private subnet architecture.\n\n"
            "In **CloudOps**, VPC configuration is inspected during diagnostics to detect missing routes, firewall gaps, and subnet misconfigurations."
        )

    # ================================================================
    # SUBNET
    # ================================================================
    if intent == "SUBNET" or ("subnet" in q_lower and "what is" in q_lower):
        return (
            "A **subnet** (subnetwork) is a range of IP addresses within your VPC, confined to a single **Availability Zone**. "
            "Subnets partition your VPC into segments for security, routing, and availability isolation.\n\n"
            "### Public Subnet vs Private Subnet:\n"
            "| Feature | Public Subnet | Private Subnet |\n"
            "| :--- | :--- | :--- |\n"
            "| Internet Access | Direct via Internet Gateway | Outbound via NAT Gateway only |\n"
            "| EC2 Public IP | Has public or Elastic IP | Private IP only |\n"
            "| Route Table | `0.0.0.0/0 → igw-xxx` | `0.0.0.0/0 → nat-xxx` |\n"
            "| Use Cases | Web servers, load balancers | Databases, app backends |\n\n"
            "AWS reserves 5 IP addresses from each subnet (first 4 + last). A `/24` subnet provides 251 usable IPs."
        )

    # ================================================================
    # ROUTE TABLE
    # ================================================================
    if intent == "ROUTE_TABLE" or ("route table" in q_lower):
        return (
            "A **Route Table** contains rules (routes) that determine where network traffic is directed inside your VPC.\n\n"
            "### Key Route Entries:\n"
            "| Destination | Target | Meaning |\n"
            "| :--- | :--- | :--- |\n"
            "| `10.0.0.0/16` | local | VPC-internal traffic stays local |\n"
            "| `0.0.0.0/0` | `igw-xxxxxxxx` | Public internet via Internet Gateway |\n"
            "| `0.0.0.0/0` | `nat-xxxxxxxx` | Outbound internet via NAT Gateway |\n\n"
            "### Rules:\n"
            "- Every **public subnet** must have: `0.0.0.0/0 → igw-xxxxxxxx`\n"
            "- Every **private subnet** needing outbound internet must have: `0.0.0.0/0 → nat-xxxxxxxx`\n"
            "- Each subnet can be associated with only one route table at a time\n\n"
            "In **CloudOps**, the AI Troubleshooter reads route tables via `ec2:DescribeRouteTables` and produces "
            "`missing_igw_route` or `missing_nat_route` signals when entries are missing."
        )

    # ================================================================
    # EC2 CREATION
    # ================================================================
    if intent == "EC2_CREATION" or (
        any(k in q_lower for k in ["create", "launch", "setup", "make", "spin up"]) and
        any(k in q_lower for k in ["ec2", "instance"])
    ):
        return (
            "To create and launch an **Amazon EC2 instance**, follow these steps:\n\n"
            "1. **Open EC2 Console** → Click **Launch Instance**\n"
            "2. **Name your instance** (e.g., `web-server-prod`)\n"
            "3. **Choose an AMI**: Amazon Linux 2023, Ubuntu 22.04 LTS, or Windows Server\n"
            "4. **Select instance type**: `t3.micro` (free tier) or appropriate size for your workload\n"
            "5. **Configure key pair**: Select or create a `.pem` key (needed for SSH/RDP password)\n"
            "6. **Network settings**: Choose VPC, subnet, and enable **Auto-assign Public IP** for public access\n"
            "7. **Configure Security Group**: Add inbound rules:\n"
            "   - HTTP (port 80) and HTTPS (port 443) from `0.0.0.0/0` for web servers\n"
            "   - SSH (port 22) or RDP (port 3389) restricted to your IP\n"
            "8. **Configure storage**: Set root EBS volume size (8 GB Linux / 30 GB Windows, `gp3` type)\n"
            "9. **Launch** → instance transitions to `running` with `2/2 status checks passed`\n"
            "10. **Connect**: SSH (`ssh -i key.pem ec2-user@<Public-IP>`), SSM Session Manager, or RDP\n\n"
            "CloudOps is advisory-only — it explains the procedure but does not automatically launch instances."
        )

    # ================================================================
    # IAM
    # ================================================================
    if intent == "IAM" or ("iam" in q_lower and any(k in q_lower for k in ["what is", "what are", "role", "user", "policy"])):
        return (
            "**AWS IAM (Identity and Access Management)** is the service that controls authentication and authorization in AWS.\n\n"
            "### Core IAM Concepts:\n"
            "- **IAM User**: A person or application with permanent credentials (access key or password)\n"
            "- **IAM Group**: Collection of users — attach policies to a group for easier management\n"
            "- **IAM Role**: An identity with permissions that can be **assumed** by AWS services, users, or federated identities. Roles use **temporary credentials** (no permanent keys) — the recommended approach for EC2/Lambda/ECS permissions\n"
            "- **IAM Policy**: JSON document defining allowed or denied actions (e.g., `ec2:Describe*`, `s3:GetObject`)\n\n"
            "### Principle of Least Privilege:\n"
            "Grant only the minimum permissions needed. Avoid wildcard `*` on resources in production. "
            "Use **IAM Access Analyzer** to audit and remove excessive permissions.\n\n"
            "**CloudOps** uses a read-only IAM role with `ec2:Describe*`, `cloudwatch:GetMetricStatistics`, "
            "`cloudtrail:LookupEvents`, and SSM permissions — never write permissions."
        )

    # ================================================================
    # DNS
    # ================================================================
    if intent == "DNS" or ("dns" in q_lower and "what is" in q_lower) or ("domain name system" in q_lower):
        return (
            "**DNS (Domain Name System)** is the internet's directory service that translates human-readable hostnames "
            "(like `www.example.com`) into IP addresses (like `54.210.12.34`) that computers use to route traffic.\n\n"
            "### Common DNS Record Types:\n"
            "| Record | Purpose |\n"
            "| :--- | :--- |\n"
            "| **A** | Maps domain to IPv4 address |\n"
            "| **CNAME** | Alias pointing to another domain |\n"
            "| **MX** | Mail server record |\n"
            "| **TXT** | Text verification (SPF, DKIM) |\n"
            "| **NS** | Authoritative name servers |\n\n"
            "### Amazon Route 53:\n"
            "AWS's managed DNS service. Supports simple, weighted, latency-based, failover, and geolocation routing policies. "
            "Also provides domain registration and health checks.\n\n"
            "**VPC DNS**: Enable **DNS hostnames** and **DNS resolution** settings in your VPC for EC2 instances "
            "to receive public DNS names and resolve AWS service endpoints."
        )

    # ================================================================
    # RDP / WINDOWS EC2
    # ================================================================
    if intent == "RDP_WINDOWS" or any(k in q_lower for k in ["rdp", "remote desktop", "3389", "windows ec2"]):
        if any(k in q_lower for k in ["cant", "cannot", "can't", "unable", "not working", "failing", "troubleshoot", "why"]):
            return (
                "**RDP (Remote Desktop Protocol)** connections to Windows EC2 fail for these reasons (check in order):\n\n"
                "1. **Security Group missing port 3389** — Most common cause. Add inbound TCP rule: Port 3389 from your IP\n"
                "2. **EC2 not running** — Verify instance state is `running` in EC2 Console\n"
                "3. **No public IP** — Instance must have a Public IPv4 or Elastic IP assigned\n"
                "4. **Route table missing IGW route** — Public subnet must have `0.0.0.0/0 → igw-xxx`\n"
                "5. **NACL blocking port 3389** — Subnet NACL must allow TCP 3389 inbound + ephemeral ports (1024-65535) outbound\n"
                "6. **Windows Firewall blocking RDP** — Use SSM Session Manager to run: `Enable-NetFirewallRule -DisplayGroup 'Remote Desktop'`\n"
                "7. **RDP Service stopped** — Run via SSM: `Start-Service TermService`\n"
                "8. **Wrong password** — Re-decrypt using correct `.pem` key via EC2 Console → Connect → Get Password\n\n"
                "In **CloudOps**, the AI Troubleshooter automatically checks #1-5 and reports the exact missing configuration as evidence."
            )
        else:
            return (
                "**RDP (Remote Desktop Protocol)** is Microsoft's protocol for graphical remote access to Windows computers. "
                "It operates on **TCP port 3389**.\n\n"
                "### Connecting to a Windows EC2 Instance:\n"
                "1. In EC2 Console → Select instance → **Connect** → **RDP client** tab\n"
                "2. Click **Get password** → Upload your `.pem` private key → **Decrypt password**\n"
                "3. Click **Download remote desktop file** or manually enter `<Public-IP>:3389`\n"
                "4. Username: `Administrator`, Password: the decrypted password\n\n"
                "### Prerequisites:\n"
                "- Instance state: `running`\n"
                "- Security Group: TCP port 3389 inbound open from your IP\n"
                "- Public IP or Elastic IP assigned\n"
                "- Route table: `0.0.0.0/0 → igw-xxx` in the subnet\n\n"
                "**Tip**: Use **AWS SSM Session Manager** as an alternative — gives browser-based PowerShell access without opening port 3389."
            )

    # ================================================================
    # NACL vs SECURITY GROUP
    # ================================================================
    if intent == "NACL_VS_SG" or ("nacl" in q_lower and ("security group" in q_lower or "sg" in q_lower or "vs" in q_lower or "difference" in q_lower)):
        return (
            "### NACL vs Security Group — Key Differences\n\n"
            "| Feature | NACL | Security Group |\n"
            "| :--- | :--- | :--- |\n"
            "| **Level** | Subnet (applies to all resources in subnet) | Instance/ENI (per resource) |\n"
            "| **State** | **Stateless** — both inbound and outbound rules needed | **Stateful** — return traffic auto-allowed |\n"
            "| **Rule types** | ALLOW and **DENY** | ALLOW only |\n"
            "| **Rule order** | Evaluated in numeric order (lowest first) | All rules evaluated simultaneously |\n"
            "| **Default inbound** | Default NACL: Allow all. Custom NACL: Deny all | Block all inbound |\n"
            "| **Default outbound** | Default NACL: Allow all. Custom NACL: Deny all | Allow all outbound |\n\n"
            "### When to Use Which?\n"
            "- **Security Groups**: Primary instance-level firewall — use for all port-level access control\n"
            "- **NACLs**: Subnet-wide perimeter defense — use to **explicitly DENY** malicious IPs or enforce compliance isolation"
        )

    # ================================================================
    # NACL (standalone)
    # ================================================================
    if intent == "NACL" or ("nacl" in q_lower and "what is" in q_lower):
        return (
            "A **NACL (Network Access Control List)** is a stateless, subnet-level security layer in AWS VPC "
            "that acts as a firewall for all inbound and outbound traffic entering or leaving a subnet.\n\n"
            "### Key Properties:\n"
            "- **Subnet-level**: Applies to ALL resources in the subnet (not individual instances)\n"
            "- **Stateless**: Return traffic is NOT automatically allowed — you must add both inbound AND outbound rules\n"
            "- **ALLOW and DENY rules**: Unlike Security Groups, NACLs can explicitly DENY specific IP ranges\n"
            "- **Numeric rule order**: Rules are processed from lowest rule number first (e.g., rule 100 before rule 200)\n\n"
            "### Important: Ephemeral Ports\n"
            "Since NACLs are stateless, you must allow outbound **ephemeral ports (1024-65535)** so clients can receive "
            "response traffic from your servers.\n\n"
            "In **CloudOps**, NACL rules are inspected during network connectivity diagnostics to find blocked traffic paths."
        )

    # ================================================================
    # NAT GATEWAY
    # ================================================================
    if intent == "NAT_GATEWAY" or ("nat gateway" in q_lower):
        if "internet gateway" in q_lower or "vs" in q_lower or "difference" in q_lower:
            return (
                "### NAT Gateway vs Internet Gateway\n\n"
                "| Feature | Internet Gateway (IGW) | NAT Gateway |\n"
                "| :--- | :--- | :--- |\n"
                "| **Purpose** | Bidirectional internet access for public resources | Outbound-only internet for private resources |\n"
                "| **Traffic** | Inbound and outbound | Outbound only (blocks inbound) |\n"
                "| **Subnet** | Attached at VPC level, routes in public subnets | Deployed inside a public subnet |\n"
                "| **EC2 IP** | Needs public or Elastic IP | Uses private IP only |\n"
                "| **Use case** | Public web servers, load balancers | Private DB/app servers downloading updates |\n\n"
                "**Rule**: NAT Gateway must be placed in a **public subnet** (with an IGW route). "
                "Private subnet route table points to the NAT Gateway for outbound internet."
            )
        return (
            "A **NAT Gateway** (Network Address Translation Gateway) is a managed AWS networking service that allows "
            "EC2 instances in a **private subnet** to make outbound internet connections (software updates, external APIs) "
            "while blocking all unsolicited inbound connections from the internet.\n\n"
            "### How It Works:\n"
            "1. Private EC2 (`10.0.2.15`) sends request to internet\n"
            "2. Private subnet route table: `0.0.0.0/0 → nat-xxxxxxxx`\n"
            "3. NAT Gateway (in public subnet) translates source IP to its **Elastic IP**\n"
            "4. Traffic exits via Internet Gateway\n"
            "5. Return traffic goes back through NAT Gateway to private EC2\n\n"
            "**Key point**: NAT Gateway must be in a **public subnet**. Private instances only need their private IP.\n\n"
            "In **CloudOps**, `missing_nat_route` signal = private subnet route table lacks `0.0.0.0/0 → nat-xxx` entry."
        )

    # ================================================================
    # INTERNET GATEWAY
    # ================================================================
    if intent == "INTERNET_GATEWAY" or ("internet gateway" in q_lower and "what is" in q_lower):
        return (
            "An **Internet Gateway (IGW)** is a horizontally scaled, redundant AWS VPC component that enables "
            "bidirectional communication between your VPC and the public internet.\n\n"
            "### How to Use IGW:\n"
            "1. Create IGW and **attach it to your VPC** (one IGW per VPC)\n"
            "2. Add a route to the subnet's route table: `0.0.0.0/0 → igw-xxxxxxxx`\n"
            "3. Assign a **Public IPv4 or Elastic IP** to your EC2 instance\n"
            "4. Ensure Security Group allows inbound traffic on required ports\n\n"
            "### IGW vs NAT Gateway:\n"
            "- **IGW**: Bidirectional — supports inbound public connections AND outbound internet\n"
            "- **NAT Gateway**: Outbound only — private instances reach internet, but public cannot initiate inbound connections\n\n"
            "In **CloudOps**, `missing_igw_route` signal = public subnet route table lacks the IGW entry."
        )

    # ================================================================
    # SECURITY GROUP (standalone)
    # ================================================================
    if intent == "SECURITY_GROUP" or ("security group" in q_lower and "what is" in q_lower):
        return (
            "An **AWS Security Group** is a stateful virtual firewall that controls inbound and outbound network traffic "
            "to and from your EC2 instances and other AWS resources.\n\n"
            "### Key Properties:\n"
            "- **Stateful**: Allowed inbound traffic automatically permits return outbound traffic (no explicit outbound rule needed)\n"
            "- **Allow rules only**: Cannot create DENY rules (use NACLs for explicit denies)\n"
            "- **Default behavior**: All inbound BLOCKED, all outbound ALLOWED by default\n"
            "- **Instance-level**: Evaluated at the network interface of each specific resource\n"
            "- **Dynamic**: Rule changes apply immediately without restarting instances\n\n"
            "### Common Inbound Rules:\n"
            "| Port | Protocol | Use |\n"
            "| :--- | :--- | :--- |\n"
            "| 22 | TCP | SSH (Linux) |\n"
            "| 80 | TCP | HTTP web traffic |\n"
            "| 443 | TCP | HTTPS web traffic |\n"
            "| 3389 | TCP | RDP (Windows) |\n\n"
            "In **CloudOps**, `missing_port_80_rule`, `missing_port_443_rule`, and `missing_rdp_rule` signals "
            "are produced when required inbound rules are absent."
        )

    # ================================================================
    # EC2 UNREACHABLE
    # ================================================================
    if intent == "EC2_UNREACHABLE" or any(k in q_lower for k in ["unreachable", "not reachable", "website down", "cannot reach"]):
        return (
            "When an EC2-hosted website or service is unreachable, check these in order:\n\n"
            "**Step 1: EC2 Instance State**\n"
            "- Must be `running`. If `stopped`, all services are offline.\n\n"
            "**Step 2: Public IP**\n"
            "- Instance must have a Public IPv4 or Elastic IP. Without one, no inbound internet access.\n\n"
            "**Step 3: Security Group Inbound Rules**\n"
            "- HTTP (port 80) from `0.0.0.0/0` for web traffic\n"
            "- HTTPS (port 443) from `0.0.0.0/0` for HTTPS traffic\n"
            "- Missing rule = connection timeout from the browser\n\n"
            "**Step 4: Route Table**\n"
            "- Public subnet must have `0.0.0.0/0 → igw-xxxxxxxx` (Internet Gateway route)\n\n"
            "**Step 5: NACL Rules**\n"
            "- NACL must allow TCP 80/443 inbound AND ephemeral ports (1024-65535) outbound\n\n"
            "**Step 6: Web Server Status**\n"
            "- IIS (Windows): `Get-Service W3SVC` → must be `Running`\n"
            "- Nginx/Apache (Linux): `systemctl status nginx` → must be `active`\n\n"
            "The **CloudOps AI Troubleshooter** automates all these checks and pinpoints the exact failure."
        )

    # ================================================================
    # HIGH CPU
    # ================================================================
    if intent == "HIGH_CPU" or any(k in q_lower for k in ["high cpu", "cpu spike", "cpu 100", "cpu usage"]):
        return (
            "**High CPU Utilization on EC2** — Diagnosis & Resolution:\n\n"
            "### Common Causes:\n"
            "- **Runaway application process** — bug or infinite loop consuming all CPU\n"
            "- **Traffic spike** — sudden increase in concurrent requests\n"
            "- **Instance undersized** — workload exceeds instance capacity\n"
            "- **CPU credit exhaustion** — t2/t3 burstable instances throttle when credits reach 0\n"
            "- **Malware or crypto miner** — unauthorized process\n\n"
            "### Diagnosis:\n"
            "```bash\n"
            "# Linux\n"
            "top -bn1 | head -20\n"
            "ps aux --sort=-%cpu | head -10\n\n"
            "# Windows (via SSM PowerShell)\n"
            "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, Id\n"
            "```\n\n"
            "### Resolution:\n"
            "- Kill runaway process (`kill <PID>` or `Stop-Process -Id <PID>`)\n"
            "- Scale vertically to a larger instance type if consistently >70%\n"
            "- Add Auto Scaling Group for horizontal scaling\n"
            "- Check T-instance CPU credit balance in CloudWatch\n\n"
            "CloudWatch `CPUUtilization` metric tracks this — set an alarm at 80% for proactive alerting."
        )

    # ================================================================
    # IIS
    # ================================================================
    if intent == "IIS" or any(k in q_lower for k in ["iis", "w3svc", "iis stopped"]):
        return (
            "**IIS (Internet Information Services)** is the Microsoft Windows web server. "
            "When IIS stops, your website becomes unreachable even though the EC2 instance is still running.\n\n"
            "### Check IIS Status via AWS SSM:\n"
            "```powershell\n"
            "Get-Service W3SVC\n"
            "```\n"
            "If status shows `Stopped`, IIS is the root cause.\n\n"
            "### Start/Restart IIS:\n"
            "```powershell\n"
            "Start-Service W3SVC    # Start IIS\n"
            "iisreset /restart      # Full restart of all IIS services\n"
            "```\n\n"
            "### Common Causes of IIS Stopping:\n"
            "- Application pool crash (memory error or unhandled exception)\n"
            "- Disk space full — IIS logs at `C:\\inetpub\\logs\\LogFiles\\` filling C: drive\n"
            "- Windows update requiring restart\n"
            "- Manual stop or configuration script error\n\n"
            "In **CloudOps**, the AI Troubleshooter checks `Get-Service W3SVC` via SSM and produces an `iis_stopped` signal."
        )

    # ================================================================
    # CLOUDWATCH
    # ================================================================
    if intent == "CLOUDWATCH" or ("cloudwatch" in q_lower and "what is" in q_lower):
        return (
            "**Amazon CloudWatch** is AWS's monitoring and observability service that collects metrics, logs, and events "
            "from AWS resources and your applications.\n\n"
            "### What CloudWatch Monitors:\n"
            "- **EC2 metrics**: CPUUtilization, NetworkIn/Out, DiskReadOps, StatusCheckFailed\n"
            "- **Custom metrics**: Memory, disk space (via CloudWatch Agent)\n"
            "- **Logs**: Application logs, VPC Flow Logs, CloudTrail events\n"
            "- **Lambda, RDS, S3** and 70+ AWS services\n\n"
            "### CloudWatch Alarms:\n"
            "Alarms watch a metric and trigger actions when thresholds are breached:\n"
            "- Send SNS notification (email/SMS)\n"
            "- Trigger Auto Scaling\n"
            "- Stop/restart/terminate EC2 instance\n\n"
            "### CPUUtilization:\n"
            "The most common EC2 metric. In CloudOps, the AI Troubleshooter queries CPUUtilization for the last 15 minutes. "
            "The `high_cpu_utilization` signal is only raised when CURRENT readings exceed the configured threshold.\n\n"
            "**CloudWatch vs CloudTrail**: CloudWatch is for performance/health monitoring. "
            "CloudTrail is for API auditing and change tracking."
        )

    # ================================================================
    # CLOUDTRAIL
    # ================================================================
    if intent == "CLOUDTRAIL" or ("cloudtrail" in q_lower and "what is" in q_lower):
        return (
            "**AWS CloudTrail** records every API call and management event in your AWS account, answering: "
            "**Who did what, when, and from where?**\n\n"
            "### What CloudTrail Records:\n"
            "- Which IAM user or role made the request\n"
            "- Which API action was called (e.g., `AuthorizeSecurityGroupIngress`, `StopInstances`)\n"
            "- Timestamp, source IP, and affected resource\n\n"
            "### How to Find Who Changed a Security Group:\n"
            "1. Go to **CloudTrail > Event History**\n"
            "2. Filter by **Event name**: `AuthorizeSecurityGroupIngress` (added rule) or `RevokeSecurityGroupIngress` (removed)\n"
            "3. Inspect the event JSON: `userIdentity.arn` shows who made the change\n\n"
            "### Retention:\n"
            "- **Event History**: 90 days (free, no setup needed)\n"
            "- **Trail to S3**: Unlimited retention (create a Trail for long-term audit)\n\n"
            "**CloudTrail vs CloudWatch**: CloudTrail = who changed infrastructure. CloudWatch = is infrastructure healthy.\n\n"
            "In **CloudOps**, CloudTrail events are queried to correlate recent changes with incident start times."
        )

    # ================================================================
    # WHO CHANGED SECURITY GROUP (specific CloudTrail query)
    # ================================================================
    if "who changed" in q_lower or "who modified" in q_lower or "who deleted" in q_lower:
        return (
            "To find who changed, modified, or deleted an AWS resource, use **AWS CloudTrail**:\n\n"
            "### For Security Group changes:\n"
            "1. **AWS Console** → CloudTrail → **Event history**\n"
            "2. Filter **Event name**: `AuthorizeSecurityGroupIngress` (inbound rule added)\n"
            "   or `RevokeSecurityGroupIngress` (inbound rule removed)\n"
            "3. The event details show:\n"
            "   - `userIdentity.arn` — exactly who made the change (IAM user or role)\n"
            "   - `sourceIPAddress` — where the request originated\n"
            "   - `requestParameters.groupId` — which Security Group was changed\n\n"
            "### Other common CloudTrail event names:\n"
            "| Action | CloudTrail Event |\n"
            "| :--- | :--- |\n"
            "| Security Group rule added | `AuthorizeSecurityGroupIngress` |\n"
            "| Security Group rule removed | `RevokeSecurityGroupIngress` |\n"
            "| EC2 stopped | `StopInstances` |\n"
            "| EC2 terminated | `TerminateInstances` |\n"
            "| IAM policy attached | `AttachRolePolicy` |\n\n"
            "CloudTrail Event History covers the **last 90 days**. Create a Trail to S3 for longer retention."
        )

    # ================================================================
    # DOCKER
    # ================================================================
    if intent == "DOCKER" or ("docker" in q_lower and "what is" in q_lower):
        return (
            "**Docker** is an open-source platform for building, packaging, and running applications in **containers** — "
            "lightweight, portable, isolated units that include the application code, runtime, and all dependencies.\n\n"
            "### Why Docker?\n"
            "- **Consistency**: Eliminates 'works on my machine' issues — containers run identically everywhere\n"
            "- **Portability**: Run locally, on EC2, or in managed services (ECS, EKS, Fargate)\n"
            "- **Speed**: Containers start in milliseconds vs minutes for VMs\n\n"
            "### Core Concepts:\n"
            "- **Image**: Read-only template built from a Dockerfile\n"
            "- **Container**: Running instance of an image\n"
            "- **Dockerfile**: Instructions to build an image (FROM, RUN, COPY, EXPOSE, CMD)\n"
            "- **Docker Hub / Amazon ECR**: Image registries\n\n"
            "### Basic Commands:\n"
            "```bash\n"
            "docker build -t my-app .      # Build image\n"
            "docker run -p 8080:8080 my-app # Run container\n"
            "docker ps                      # List running containers\n"
            "docker logs <container-id>     # View logs\n"
            "```"
        )

    # ================================================================
    # KUBERNETES
    # ================================================================
    if intent == "KUBERNETES" or ("kubernetes" in q_lower and "what is" in q_lower):
        return (
            "**Kubernetes (K8s)** is an open-source container orchestration platform that automates deploying, "
            "scaling, and managing containerized applications across a cluster of nodes.\n\n"
            "### Core Concepts:\n"
            "- **Pod**: Smallest deployable unit — one or more containers sharing network/storage\n"
            "- **Deployment**: Manages Pod replicas with scaling and rolling update strategy\n"
            "- **Service**: Stable network endpoint for a group of Pods (ClusterIP, NodePort, LoadBalancer)\n"
            "- **Namespace**: Virtual cluster for isolation within K8s\n"
            "- **Ingress**: HTTP/HTTPS routing rules for external access\n"
            "- **ConfigMap / Secret**: Configuration and sensitive data for containers\n\n"
            "### AWS Kubernetes Services:\n"
            "- **Amazon EKS**: Managed Kubernetes — AWS runs the control plane\n"
            "- **AWS Fargate**: Serverless containers — no EC2 nodes to manage\n"
            "- **Amazon ECR**: Managed Docker image registry\n\n"
            "**Docker builds containers. Kubernetes runs and orchestrates them at scale.**"
        )

    # ================================================================
    # TERRAFORM
    # ================================================================
    if intent == "TERRAFORM" or ("terraform" in q_lower and "what is" in q_lower):
        return (
            "**Terraform** is an open-source Infrastructure as Code (IaC) tool by HashiCorp that lets you define "
            "and provision cloud infrastructure using declarative HCL configuration files.\n\n"
            "### Why Terraform?\n"
            "- **Repeatability**: Deploy identical dev/staging/prod environments from the same code\n"
            "- **Version control**: Infrastructure changes tracked in Git\n"
            "- **Multi-cloud**: Supports AWS, Azure, GCP, Kubernetes, and 1000+ providers\n"
            "- **Plan before apply**: Preview changes before affecting real infrastructure\n\n"
            "### Core Workflow:\n"
            "```bash\n"
            "terraform init     # Download providers and modules\n"
            "terraform plan     # Preview changes (no modification)\n"
            "terraform apply    # Apply changes to real infrastructure\n"
            "terraform destroy  # Tear down all managed resources\n"
            "```\n\n"
            "### Best Practice:\n"
            "Store Terraform state remotely in **S3** with **DynamoDB locking** to prevent team conflicts. "
            "Never commit `terraform.tfstate` to Git."
        )

    # ================================================================
    # CI/CD
    # ================================================================
    if intent == "CICD" or any(k in q_lower for k in ["ci/cd", "cicd", "continuous integration", "continuous delivery"]):
        return (
            "**CI/CD (Continuous Integration / Continuous Delivery)** is the DevOps practice of automating "
            "the software build, test, and deployment lifecycle.\n\n"
            "- **Continuous Integration (CI)**: Automatically build and test code on every commit\n"
            "- **Continuous Delivery (CD)**: Automatically deploy tested code to staging/production\n\n"
            "### Common CI/CD Tools:\n"
            "| Tool | Type |\n"
            "| :--- | :--- |\n"
            "| GitHub Actions | Cloud-native, GitHub repos |\n"
            "| GitLab CI | Built into GitLab |\n"
            "| Jenkins | Self-hosted, enterprise |\n"
            "| AWS CodePipeline | AWS-native end-to-end |\n"
            "| AWS CodeBuild | Managed build service |\n\n"
            "### Benefits:\n"
            "- Catch bugs early with automated testing\n"
            "- Faster, reliable releases\n"
            "- No manual deployment steps\n"
            "- Rollback capability on failed deployments"
        )

    # ================================================================
    # CLOUDWATCH (alarms specifically)
    # ================================================================
    if "alarm" in q_lower and "cloudwatch" in q_lower:
        return (
            "A **CloudWatch Alarm** monitors a single metric and performs actions when the metric breaches a threshold.\n\n"
            "### Alarm States:\n"
            "- **OK**: Metric is within threshold\n"
            "- **ALARM**: Metric has breached threshold\n"
            "- **INSUFFICIENT_DATA**: Not enough data points yet\n\n"
            "### Alarm Actions:\n"
            "- Send **SNS notification** (email, SMS, Lambda trigger)\n"
            "- **Auto Scaling** action (scale out/in)\n"
            "- EC2 action (stop, terminate, reboot, recover)\n\n"
            "### Creating a CPU Alarm:\n"
            "1. CloudWatch > Alarms > Create Alarm\n"
            "2. Select metric: `AWS/EC2 > CPUUtilization` with your InstanceId dimension\n"
            "3. Threshold: Greater than 80% for 2 of 3 evaluation periods (5 min each)\n"
            "4. Action: Notify SNS topic → email alert"
        )

    # ================================================================
    # QLoRA
    # ================================================================
    if intent == "QLORA" or "qlora" in q_lower:
        return (
            "**QLoRA** (Quantized Low-Rank Adaptation) is a parameter-efficient fine-tuning technique that "
            "freezes the base LLM parameters in **4-bit NormalFloat (NF4)** precision while training lightweight "
            "low-rank adapter matrices.\n\n"
            "### Why CloudOps Uses QLoRA:\n"
            "- **Memory reduction**: Reduces 16-bit model VRAM from ~12 GB down to ~3.5 GB\n"
            "- **LoRA config**: `r=16, alpha=32` — applied to attention and projection layers\n"
            "  (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`)\n"
            "- **Preserved quality**: Retains baseline reasoning while enabling rapid fine-tuning\n"
            "- **Separate adapters**: CloudOps maintains distinct adapters for:\n"
            "  - AI Troubleshooter: `outputs/adapter/`\n"
            "  - Support Agent: `outputs/support_agent_adapter/`\n\n"
            "**Quantization** uses BitsAndBytes 4-bit on GPU, float32 on CPU."
        )

    # ================================================================
    # RAG
    # ================================================================
    if intent == "RAG" or ("rag" in q_lower and "what is" in q_lower):
        return (
            "**RAG (Retrieval-Augmented Generation)** is an AI architecture pattern that combines "
            "a **vector retrieval system** with a **language model** to ground responses in factual documents.\n\n"
            "### How RAG Works:\n"
            "1. **Encode**: User query is converted to a dense vector embedding\n"
            "2. **Retrieve**: Embedding is used to search a vector store (ChromaDB) for similar documents\n"
            "3. **Augment**: Retrieved context is injected into the LLM prompt\n"
            "4. **Generate**: LLM generates a response grounded in the retrieved facts\n\n"
            "### Why RAG Beats Pure LLM:\n"
            "- Reduces hallucinations — answers are grounded in actual documents\n"
            "- No retraining needed to add new knowledge — just update the vector store\n"
            "- Provides source attribution (you can show which documents were retrieved)\n\n"
            "### CloudOps RAG Stack:\n"
            "- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim)\n"
            "- Vector store: **ChromaDB** (persistent, cosine similarity, HNSW index)\n"
            "- Collections: `cloudops_knowledge` (Troubleshooter) + `cloudops_support` (Support Agent)"
        )

    # ================================================================
    # LLM / TRANSFORMER
    # ================================================================
    if intent == "LLM" or any(k in q_lower for k in ["transformer", "large language model", "llm", "attention mechanism"]):
        return (
            "A **Transformer** is the deep learning architecture that powers modern Large Language Models (LLMs). "
            "Introduced in the 2017 paper 'Attention Is All You Need', it uses **self-attention mechanisms** "
            "to process sequences in parallel and capture long-range dependencies.\n\n"
            "### Key Components:\n"
            "- **Self-Attention**: Allows each token to attend to all other tokens in the sequence\n"
            "- **Multi-Head Attention**: Multiple attention heads learn different relationship patterns\n"
            "- **Feed-Forward Layers**: Transform representations after attention\n"
            "- **Positional Encoding**: Injects sequence order information\n\n"
            "### CloudOps LLM:\n"
            "CloudOps uses **Qwen2.5-3B-Instruct** — a 3-billion parameter open-source transformer. "
            "Fine-tuned with **QLoRA** (4-bit NF4) for CloudOps-specific infrastructure diagnosis tasks. "
            "Runs fully locally — no external API calls for inference."
        )

    # ================================================================
    # EC2 BASICS / WHAT IS EC2
    # ================================================================
    if intent == "EC2" or ("ec2" in q_lower and "what is" in q_lower):
        return (
            "**Amazon EC2 (Elastic Compute Cloud)** is AWS's core virtual machine service — resizable, "
            "on-demand compute capacity in the cloud.\n\n"
            "### EC2 Instance States:\n"
            "| State | Meaning |\n"
            "| :--- | :--- |\n"
            "| `pending` | Starting — not yet billable |\n"
            "| `running` | Active and billable |\n"
            "| `stopped` | Off — storage preserved, compute not billed |\n"
            "| `terminated` | Permanently deleted — data lost |\n\n"
            "### Key Concepts:\n"
            "- **AMI**: Amazon Machine Image — OS template used to launch the instance\n"
            "- **Instance Type**: CPU/RAM/network capacity (e.g., `t3.micro`, `m5.large`, `c6g.xlarge`)\n"
            "- **Key Pair**: `.pem` file for SSH (Linux) or RDP password decryption (Windows)\n"
            "- **EBS**: Elastic Block Store — persistent disk storage for the instance\n"
            "- **Elastic IP**: Static public IP that persists across stop/start cycles\n\n"
            "### Free Tier:\n"
            "`t2.micro` or `t3.micro` — 750 hours/month free for 12 months."
        )

    # ================================================================
    # AMI
    # ================================================================
    if "ami" in q_lower or "amazon machine image" in q_lower:
        return (
            "An **AMI (Amazon Machine Image)** is a pre-configured template that contains the operating system, "
            "application server, and software configuration needed to launch an EC2 instance.\n\n"
            "### Types of AMIs:\n"
            "- **AWS-provided**: Amazon Linux 2023, Ubuntu 22.04, Windows Server 2022\n"
            "- **AWS Marketplace**: Commercial/community pre-configured images\n"
            "- **Custom AMI**: Snapshot of your own configured EC2 instance for redeployment\n\n"
            "### Key Properties:\n"
            "- AMIs are **region-specific** — copy to other regions for multi-region deployments\n"
            "- AMIs reference **EBS snapshots** for the root volume\n"
            "- Creating a custom AMI preserves your exact software configuration for rapid scaling\n\n"
            "When launching EC2, you select an AMI to define the base operating system and software."
        )

    # ================================================================
    # AWS GENERAL / WHAT IS AWS
    # ================================================================
    if "what is aws" in q_lower or ("aws" in q_lower and "what is" in q_lower and "region" not in q_lower):
        return (
            "**AWS (Amazon Web Services)** is the world's largest cloud computing platform, providing "
            "on-demand infrastructure services over the internet — pay only for what you use.\n\n"
            "### Core AWS Service Categories:\n"
            "- **Compute**: EC2 (virtual machines), Lambda (serverless), ECS/EKS (containers)\n"
            "- **Networking**: VPC, Route 53 (DNS), CloudFront (CDN), Direct Connect\n"
            "- **Storage**: S3 (object), EBS (block), EFS (file)\n"
            "- **Databases**: RDS (relational), DynamoDB (NoSQL), ElastiCache (cache)\n"
            "- **Security**: IAM, Security Groups, WAF, Shield, Inspector\n"
            "- **Monitoring**: CloudWatch (metrics/logs), CloudTrail (API audit)\n"
            "- **Developer**: CodePipeline, CodeBuild, CodeDeploy\n\n"
            "AWS operates in **30+ geographic Regions**, each containing multiple **Availability Zones** — "
            "physically separate data centers for high availability."
        )

    # ================================================================
    # PORT 443 BLOCKED
    # ================================================================
    if ("port 443" in q_lower or "https" in q_lower) and any(k in q_lower for k in ["blocked", "not working", "why", "cannot", "unreachable"]):
        return (
            "**Port 443 (HTTPS) is blocked** — most likely a Security Group issue. Check in order:\n\n"
            "1. **Security Group**: Must have inbound rule: TCP port 443 from `0.0.0.0/0`\n"
            "   - AWS Console → EC2 → Security Groups → Inbound rules → Edit\n"
            "   - Add: Type=HTTPS, Protocol=TCP, Port=443, Source=0.0.0.0/0\n\n"
            "2. **NACL**: Subnet NACL must allow TCP 443 inbound + ephemeral ports (1024-65535) outbound\n\n"
            "3. **Web server SSL configuration**: Ensure your web server has a valid TLS certificate installed\n"
            "   - IIS: Check site bindings for HTTPS on port 443\n"
            "   - Nginx: Verify `ssl_certificate` and `ssl_certificate_key` directives\n\n"
            "4. **Route table**: Public subnet must have `0.0.0.0/0 → igw-xxxxxxxx`\n\n"
            "The **CloudOps AI Troubleshooter** checks Security Group rules automatically and reports `missing_port_443_rule`."
        )

    # ================================================================
    # PORT 80 BLOCKED
    # ================================================================
    if ("port 80" in q_lower or ("http" in q_lower and "https" not in q_lower)) and any(k in q_lower for k in ["blocked", "not working", "why", "cannot"]):
        return (
            "**Port 80 (HTTP) is blocked** — check these in order:\n\n"
            "1. **Security Group inbound rule missing**: Add TCP port 80 from `0.0.0.0/0`\n"
            "   - EC2 Console → Security Groups → Inbound rules → Edit inbound rules\n"
            "   - Add: Type=HTTP, Protocol=TCP, Port=80, Source=Anywhere-IPv4\n\n"
            "2. **NACL blocking**: Add NACL inbound rule for TCP 80 + outbound for ephemeral ports (1024-65535)\n\n"
            "3. **Web server not listening**: Verify IIS/nginx/httpd is running and bound to port 80\n\n"
            "4. **Application redirecting**: Some apps redirect all port 80 traffic to 443 — check if HTTPS is also needed\n\n"
            "Because Security Groups are **stateful**, allowing inbound port 80 automatically permits the return traffic."
        )

    # ================================================================
    # CLOUDOPS PRODUCT
    # ================================================================
    if intent == "PRODUCT" or any(k in q_lower for k in ["cloudops", "what does cloudops", "what is cloudops"]):
        if "automatically" in q_lower or "modify" in q_lower or "change" in q_lower or "auto" in q_lower:
            return (
                "**No — CloudOps does NOT automatically modify AWS resources.**\n\n"
                "CloudOps is strictly **advisory-only**. It performs read-only AWS API queries to diagnose problems "
                "and provides recommendations, but it never:\n"
                "- Opens or closes Security Group rules\n"
                "- Starts, stops, or terminates EC2 instances\n"
                "- Modifies Route Tables, VPCs, or NACLs\n"
                "- Executes any write AWS API operations\n\n"
                "All CloudOps AWS calls are read-only: `ec2:Describe*`, `cloudwatch:GetMetricStatistics`, "
                "`cloudtrail:LookupEvents`, `ssm:SendCommand` (read-only checks only).\n\n"
                "After receiving a diagnosis, **you apply the recommended changes** using the AWS Console, AWS CLI, or Terraform."
            )
        return (
            "**CloudOps** is an AI-powered cloud operations platform for AWS infrastructure monitoring and troubleshooting.\n\n"
            "### Key Features:\n"
            "- **AI Troubleshooter** (`/troubleshoot`): Automated read-only AWS diagnostic pipeline using Qwen2.5-3B + QLoRA. "
            "Analyzes EC2, VPC, Security Groups, CloudWatch metrics, and CloudTrail events. Returns a 6-field structured diagnosis.\n"
            "- **Support Agent** (`/support`): RAG-grounded conversational AI assistant for AWS and CloudOps questions\n"
            "- **Advisory-only**: CloudOps never automatically modifies your AWS infrastructure\n\n"
            "### AI Stack:\n"
            "Qwen2.5-3B-Instruct + QLoRA (4-bit NF4) + ChromaDB (RAG) + `all-MiniLM-L6-v2` embeddings"
        )

    # ================================================================
    # WHAT IS CLOUDOPS TROUBLESHOOTER (how it works)
    # ================================================================
    if "troubleshooter" in q_lower and any(k in q_lower for k in ["how", "work", "what does", "pipeline"]):
        return (
            "The **CloudOps AI Troubleshooter** executes an automated 9-step diagnostic pipeline:\n\n"
            "1. **Request Intake**: Accepts question + optional EC2 Instance ID\n"
            "2. **Parallel Telemetry**: Queries AWS in parallel — EC2 state, VPC, Security Groups, Route Tables, NACLs, CloudWatch, CloudTrail, SSM\n"
            "3. **Signal Extraction**: Converts raw telemetry into discrete signals (`stopped_instance`, `missing_port_80_rule`, `high_cpu_utilization`)\n"
            "4. **RAG Retrieval**: Embeds signals + query → ChromaDB retrieves matching runbook solutions\n"
            "5. **Qwen Reasoning**: Qwen2.5-3B + QLoRA adapter generates structured diagnosis JSON\n"
            "6. **Evidence Validation**: `DiagnosisValidator` verifies claims against live AWS data\n"
            "7. **Confidence Scoring**: 0.0–1.0 based on telemetry proof strength\n"
            "8. **6-Field Output**: Problem Summary, Root Cause, Evidence, Impact, Recommendation, Confidence Score\n\n"
            "**Read-only** — Troubleshooter never modifies AWS resources."
        )

    # ================================================================
    # GENERAL FALLBACK: Use best retrieved chunk
    # ================================================================
    if chunks:
        best_chunk = chunks[0]
        title = best_chunk.get("title", "Technical Support Guidance")
        content = best_chunk.get("content", "").strip()
        if content:
            return f"### {title}\n\n{content}"

    return "Sufficient information is currently unavailable in the Support Knowledge Base for this inquiry. Could you provide more detail about the specific AWS service or issue you're investigating?"
