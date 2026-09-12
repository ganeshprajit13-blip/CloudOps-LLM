import json
import logging
from typing import List, Dict, Any, Optional
from app.schemas.analysis import RetrievedKnowledgeItem

logger = logging.getLogger("cloudops.services.prompt_builder")

SYSTEM_INSTRUCTIONS = """You are CloudOps LLM, an expert AWS cloud infrastructure troubleshooting advisor.
Your role is to analyze the supplied live cloud context, anomaly signals, recent audit events, and retrieved operational knowledge to determine the most probable root cause of the reported infrastructure issue.

Strict Factual Grounding & Protocol Guidelines:
1. Live AWS context is your PRIMARY source of truth. Prefer the supplied resource_id and its directly associated resources.
2. Differentiate HTTP (port 80) from HTTPS (port 443). Match user question keywords ("http", "website", "web server", "port 80" vs "https", "ssl", "tls", "port 443") to the relevant port. Standard website access defaults to HTTP (port 80) unless HTTPS is explicitly specified.
3. If an HTTP website issue is reported and Security Group lacks inbound TCP port 80, diagnose missing TCP port 80 as the probable root cause. Do NOT default to diagnosing port 443 for HTTP requests.
4. If protocol is unspecified and both ports 80 and 443 are absent in Security Group, note both HTTP (port 80) and HTTPS (port 443) in probable_root_cause. If both ports are allowed, do NOT attribute failure to Security Groups; attribute to potential web server process failure or set low confidence (<=0.50).
5. If the target EC2 instance is stopped, EC2 instance state is the primary cause over Security Group rules.
6. NEVER claim an AWS resource exists (e.g. Application Load Balancer, Target Group, NAT Gateway) unless it appears explicitly in the supplied live cloud context.
7. If no Load Balancer (ALB/NLB) exists in the live context, NEVER diagnose a load balancer or target group issue.
8. Do NOT invent metrics, IP addresses, ports, security group rules, logs, or events that are absent from the context. Do not repeat raw telemetry unnecessarily.
9. Every statement in "evidence" MUST be directly traceable to facts present in the supplied live cloud data. Provide maximum 3 to 5 concise evidence items.
10. If evidence is insufficient or ambiguous to prove a root cause, explicitly state that in probable_root_cause and set confidence <= 0.50.
11. Recommendations must be strictly advisory. Never claim that you executed actions or modified AWS infrastructure.
12. CURRENT CONFIGURATION PRECEDENCE: Current active resource configurations (Security Group inbound rules, EC2 running state, host telemetry services) ALWAYS take strict precedence over historical CloudTrail events. If a historical CloudTrail event shows a past mutation (e.g. RevokeSecurityGroupIngress) but the current active Security Group allows the port or service is running, the historical mutation is NOT the current cause of failure. Never diagnose that a port is removed/blocked or service is stopped when the active configuration confirms it is allowed or running.
13. Output format constraints:
    - Output raw JSON ONLY. Do NOT use markdown code fences (no ```json or ```).
    - Be concise and compact to ensure complete output within 512 tokens.
    - "problem": 1 short sentence.
    - "probable_root_cause": 1 short sentence.
    - "evidence": array of maximum 3 to 5 concise items directly grounded in input.
    - "impact": 1 short sentence.
    - "recommendation": 1 short advisory sentence.
    - "confidence": numeric float between 0.00 and 1.00.
    - Always complete and close the JSON object with a closing brace.

Required Output JSON Schema:
{
  "problem": "<short sentence describing issue>",
  "probable_root_cause": "<short sentence explaining probable root cause>",
  "evidence": ["<concise factual evidence 1>", "<concise factual evidence 2>", "<concise factual evidence 3>"],
  "impact": "<short sentence on operational consequence>",
  "recommendation": "<short advisory sentence>",
  "confidence": 0.85
}
"""

class PromptBuilder:
    """
    Assembles the final prompt combining System Instructions, User Question,
    Formatted Cloud Context, Detected Signals, Recent Events, and RAG Knowledge.
    """

    def format_rag_knowledge(
        self,
        retrieved_knowledge: List[RetrievedKnowledgeItem]
    ) -> str:
        """
        Format retrieved RAG knowledge items into a clean text block,
        preserving source attribution, title, service category, score, and text.
        """
        if not retrieved_knowledge:
            return "RETRIEVED KNOWLEDGE:\nNo additional operational knowledge retrieved."

        lines = ["=== RETRIEVED KNOWLEDGE ==="]
        for idx, item in enumerate(retrieved_knowledge, 1):
            source = getattr(item, "source", None) or item.get("source", "unknown") if isinstance(item, dict) else item.source
            title = getattr(item, "title", None) or item.get("title", "Untitled") if isinstance(item, dict) else item.title
            service = getattr(item, "service", None) or item.get("service", "general") if isinstance(item, dict) else item.service
            score = getattr(item, "score", None) or item.get("score", 0.0) if isinstance(item, dict) else item.score
            text = getattr(item, "text", None) or item.get("text", "") if isinstance(item, dict) else item.text

            lines.append(f"\n[Knowledge Chunk {idx}]")
            lines.append(f"Source: {source} | Title: {title} | Service: {service} | Score: {score:.4f}")
            chunk_text = text.strip()
            if len(chunk_text) > 350:
                chunk_text = chunk_text[:350] + "..."
            lines.append(f"Content:\n{chunk_text}")

        return "\n".join(lines)

    def build_prompt(
        self,
        question: str,
        formatted_context: str,
        retrieved_knowledge: List[RetrievedKnowledgeItem]
    ) -> str:
        """
        Construct the final full prompt text for the LLM.
        """
        formatted_rag = self.format_rag_knowledge(retrieved_knowledge)

        prompt_parts = [
            f"<|im_start|>system\n{SYSTEM_INSTRUCTIONS}\n<|im_end|>",
            f"<|im_start|>user\nUser Question:\n{question.strip()}\n\n{formatted_context}\n\n{formatted_rag}\n\nPlease analyze the evidence above and provide the structured JSON diagnosis.\n<|im_end|>",
            "<|im_start|>assistant\n"
        ]

        return "\n".join(prompt_parts)
