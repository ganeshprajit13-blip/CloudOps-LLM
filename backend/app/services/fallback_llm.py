import os
import json
import logging
import time
from typing import List, Dict, Any, Optional
import requests

from app.core.config import settings

logger = logging.getLogger("cloudops.services.fallback_llm")

FALLBACK_LLM_SYSTEM_PROMPT = (
    "You are the fallback technical assistant for CloudOps.\n\n"
    "Provide the most useful technically accurate answer you can.\n\n"
    "You can answer questions about:\n"
    "- AWS\n"
    "- EC2\n"
    "- VPC\n"
    "- Security Groups\n"
    "- NACL\n"
    "- IAM\n"
    "- S3\n"
    "- CloudWatch\n"
    "- CloudTrail\n"
    "- Route Tables\n"
    "- Internet Gateway\n"
    "- NAT Gateway\n"
    "- Load Balancers\n"
    "- DNS\n"
    "- networking\n"
    "- Linux\n"
    "- Windows Server\n"
    "- Docker\n"
    "- Kubernetes\n"
    "- Terraform\n"
    "- CI/CD\n"
    "- DevOps\n"
    "- APIs\n"
    "- databases\n"
    "- networking\n"
    "- CloudOps architecture\n"
    "- LLMs\n"
    "- RAG\n"
    "- QLoRA\n"
    "- Transformers\n\n"
    "Use supplied CloudOps RAG context when relevant.\n\n"
    "Do not invent internal CloudOps implementation details.\n\n"
    "When the question is general technical knowledge, answer using your general technical knowledge.\n\n"
    "When troubleshooting, explain likely causes, evidence to check, and recommended next steps.\n\n"
    "Never claim that you executed an AWS operation.\n\n"
    "Never claim that you modified infrastructure.\n\n"
    "Never claim that you changed a Security Group, EC2 instance, VPC, IAM policy, route, or other cloud resource.\n\n"
    "CloudOps is advisory-only.\n\n"
    "If information is uncertain, clearly identify the uncertainty rather than inventing facts.\n\n"
    "Give a direct answer first, followed by useful explanation or steps."
)


def is_fallback_llm_available() -> bool:
    """Checks whether Fallback LLM is configured and enabled."""
    if not getattr(settings, "FALLBACK_LLM_ENABLED", True):
        return False
    key = (
        getattr(settings, "FALLBACK_LLM_API_KEY", "")
        or getattr(settings, "GROQ_API_KEY", "")
        or os.getenv("FALLBACK_LLM_API_KEY", "")
        or os.getenv("GROQ_API_KEY", "")
    ).strip()
    return bool(key and key != "placeholder" and not key.startswith("<"))


def call_fallback_llm(
    question: str,
    rag_context: Optional[str] = "",
    history: Optional[List[Dict[str, str]]] = None,
    local_model_answer: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    max_tokens: int = 800,
    temperature: float = 0.3,
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Invokes Fallback LLM API as a fallback provider when the local Support QLoRA model
    cannot produce a sufficiently grounded, confident, or complete answer.

    Never logs or exposes secret keys or credentials.
    Iterates through candidate models if the configured model is deprecated or unavailable.
    """
    if not is_fallback_llm_available():
        logger.warning("Fallback LLM invoked but Fallback LLM service is not configured or disabled.")
        return {
            "success": False,
            "answer": None,
            "provider": "local_fallback_failure",
            "fallback_used": True,
            "error": "Fallback LLM provider is unconfigured or disabled."
        }

    api_key = (
        getattr(settings, "FALLBACK_LLM_API_KEY", "")
        or getattr(settings, "GROQ_API_KEY", "")
        or os.getenv("FALLBACK_LLM_API_KEY", "")
        or os.getenv("GROQ_API_KEY", "")
    ).strip()
    primary_model = (
        getattr(settings, "FALLBACK_LLM_MODEL", "")
        or getattr(settings, "GROQ_MODEL", "")
        or "groq/compound"
    ).strip() or "groq/compound"
    
    base_url = (
        getattr(settings, "FALLBACK_LLM_BASE_URL", "")
        or getattr(settings, "GROQ_BASE_URL", "")
        or "https://api.groq.com/openai/v1"
    ).strip().rstrip("/")
    endpoint = f"{base_url}/chat/completions"

    # Candidates list (deduplicated)
    candidates = []
    for m in [primary_model, "groq/compound", "qwen/qwen3.6-27b", "openai/gpt-oss-20b", "groq/compound-mini"]:
        if m and m not in candidates:
            candidates.append(m)

    # Build contextual system prompt
    context_section = ""
    if rag_context and rag_context.strip():
        context_section = f"\n\nSUPPLIED SUPPORT KNOWLEDGE BASE CONTEXT:\n{rag_context.strip()}"

    system_content = f"{FALLBACK_LLM_SYSTEM_PROMPT}{context_section}"
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

    # Append bounded conversation history (max 6 messages)
    if history:
        for msg in history[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ["user", "assistant"] and content:
                if role == "user" and content.strip().lower() == question.strip().lower():
                    continue
                messages.append({"role": role, "content": content})

    # Prepare user query with fallback diagnostic metadata if provided
    user_prompt = f"USER QUESTION:\n{question}"
    if local_model_answer and fallback_reason and "empty" not in fallback_reason.lower():
        user_prompt += f"\n\n(Note: Prior local attempt reason: {fallback_reason}. Please provide a comprehensive, direct technical response.)"

    messages.append({"role": "user", "content": user_prompt})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    for model_name in candidates:
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            logger.info(f"Invoking Fallback LLM (model: {model_name})...")
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)

            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content and content.strip():
                        reply_text = content.strip()
                        logger.info(f"Fallback LLM succeeded with model '{model_name}' ({len(reply_text)} chars).")
                        return {
                            "success": True,
                            "answer": reply_text,
                            "provider": "fallback_llm",
                            "model_used": model_name,
                            "fallback_used": True,
                            "error": None
                        }

            # If model error (404/422), log warning and continue to next candidate model
            if response.status_code in [404, 422]:
                logger.warning(f"Fallback LLM model '{model_name}' unavailable (HTTP {response.status_code}). Trying next candidate...")
                continue

            # Handle rate-limit or 5xx server errors
            if response.status_code in [429, 500, 502, 503, 504]:
                logger.warning(f"Fallback LLM API returned HTTP {response.status_code} for model '{model_name}'. Trying next candidate...")
                time.sleep(0.5)
                continue

            logger.warning(f"Fallback LLM API returned HTTP {response.status_code} for model '{model_name}': {response.text[:200]}")

        except requests.exceptions.Timeout:
            logger.warning(f"Fallback LLM request timed out after {timeout}s for model '{model_name}'.")
        except requests.exceptions.RequestException as req_err:
            logger.warning(f"Fallback LLM request error for model '{model_name}': {req_err.__class__.__name__}")
        except Exception as exc:
            logger.error(f"Unexpected error during Fallback LLM for model '{model_name}': {exc.__class__.__name__}")

    return {
        "success": False,
        "answer": None,
        "provider": "local_fallback_failure",
        "fallback_used": True,
        "error": "Fallback LLM service was unable to generate a response from any candidate model."
    }
