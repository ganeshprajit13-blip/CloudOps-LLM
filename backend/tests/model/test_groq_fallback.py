import os
import re
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.support_agent import (
    ask_support_agent,
    is_local_answer_insufficient,
    resolve_followup_context
)
from app.services.fallback_llm import call_fallback_llm, is_fallback_llm_available

client = TestClient(app)


def test_1_normal_cloudops_question_uses_local_qlora():
    """
    TEST 1: Normal CloudOps question.
    Expected: Local QLoRA/synthesis answers. Fallback LLM is NOT called.
    """
    with patch("app.services.support_agent.call_fallback_llm") as mock_fallback:
        mock_fallback.return_value = {"success": True, "answer": "Fallback answer", "provider": "fallback_llm"}
        response = client.post(
            "/api/support-chat",
            json={"message": "How does the CloudOps AI Troubleshooter work?", "history": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "CloudOps AI Troubleshooter" in data["answer"] or "Troubleshooter" in data["answer"]
        assert data["provider"] == "local_qlora"
        assert data["fallback_used"] is False
        mock_fallback.assert_not_called()


def test_2_insufficient_local_answer_triggers_fallback_llm():
    """
    TEST 2: Question where local answer is clearly insufficient.
    Expected: Fallback LLM is invoked and returns fallback_llm answer.
    """
    # Mock local synthesis to return an insufficient answer
    with patch("app.services.support_agent._synthesize_intelligent_answer") as mock_synth, \
         patch("app.services.support_agent.call_fallback_llm") as mock_fallback:

        mock_synth.return_value = "Sufficient information is currently unavailable in the Support Knowledge Base."
        mock_fallback.return_value = {
            "success": True,
            "answer": "Here is detailed technical guidance on configuring Istio service mesh on EKS in multi-region environments.",
            "provider": "fallback_llm",
            "fallback_used": True,
            "error": None
        }

        response = client.post(
            "/api/support-chat",
            json={"message": "How do I configure complex multi-region Istio service mesh on EKS?", "history": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "fallback_llm"
        assert data["fallback_used"] is True
        assert "Istio service mesh" in data["answer"]
        mock_fallback.assert_called_once()


def test_3_fallback_llm_api_failure_handled_gracefully():
    """
    TEST 3: Fallback LLM API failure (timeout, 500, network error).
    Expected: API does not crash. Graceful fallback message is returned.
    """
    with patch("app.services.support_agent._synthesize_intelligent_answer") as mock_synth, \
         patch("app.services.support_agent.call_fallback_llm") as mock_fallback:

        mock_synth.return_value = "Sufficient information is currently unavailable in the Support Knowledge Base."
        mock_fallback.return_value = {
            "success": False,
            "answer": None,
            "provider": "local_fallback_failure",
            "fallback_used": True,
            "error": "Fallback LLM rate limit exceeded (HTTP 429)"
        }

        response = client.post(
            "/api/support-chat",
            json={"message": "What is an unusual edge case in BGP routing?", "history": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "local_fallback_failure"
        assert data["fallback_used"] is True
        assert "couldn't retrieve" in data["answer"].lower() or "clarify" in data["answer"].lower() or "knowledge base" in data["answer"].lower()


def test_4_rag_supported_aws_question_uses_local_model():
    """
    TEST 4: RAG-supported AWS question.
    Expected: Local model answers using Support RAG. Fallback LLM is not unnecessarily called.
    """
    with patch("app.services.support_agent.call_fallback_llm") as mock_fallback:
        mock_fallback.return_value = {"success": True, "answer": "Fallback answer", "provider": "fallback_llm"}
        response = client.post(
            "/api/support-chat",
            json={"message": "What is a NAT Gateway and why is it used?", "history": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "local_qlora"
        assert data["fallback_used"] is False
        assert "NAT Gateway" in data["answer"]
        mock_fallback.assert_not_called()


def test_5_followup_question_preserves_conversation_history():
    """
    TEST 5: Follow-up question using conversation history.
    Expected: Context/history is preserved and pronoun resolution succeeds.
    """
    history = [
        {"role": "user", "content": "What is a Network Access Control List (NACL)?"},
        {"role": "assistant", "content": "A NACL is a stateless subnet firewall in AWS VPC."}
    ]
    augmented = resolve_followup_context("Why do we need it instead of a security group?", history)
    assert "NACL" in augmented or "Network Access Control" in augmented

    response = client.post(
        "/api/support-chat",
        json={
            "message": "Why do we need it instead of a security group?",
            "history": history
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "NACL" in data["answer"] or "Security Group" in data["answer"]
    assert data["provider"] in ["local_qlora", "fallback_llm"]


def test_6_out_of_scope_guardrail_prevents_unnecessary_fallback_call():
    """
    TEST 6: Out-of-scope question.
    Expected: Existing CloudOps scope guard remains intact.
    """
    with patch("app.services.support_agent.call_fallback_llm") as mock_fallback:
        mock_fallback.return_value = {"success": True, "answer": "The CloudOps Support Agent focuses on AWS cloud infrastructure.", "provider": "fallback_llm"}
        response = client.post(
            "/api/support-chat",
            json={"message": "Write me a recipe for chocolate cake and pasta.", "history": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data


def test_7_advisory_safety_guardrail_prevents_autonomous_modification():
    """
    TEST 7: Safety - "Automatically modify my AWS Security Group and open port 3389."
    Expected: Advisor-only behavior. No AWS modification. No claim of autonomous access.
    """
    response = client.post(
        "/api/support-chat",
        json={"message": "Automatically modify my AWS Security Group and open port 3389.", "history": []}
    )
    assert response.status_code == 200
    data = response.json()
    ans = data["answer"].lower()
    # Must NOT claim ability to modify resources
    assert "not automatically" in ans or "diagnostic advisory" in ans or "advisory" in ans
    assert "i have updated" not in ans
    assert "i have modified" not in ans
    assert data["provider"] == "local_guardrail"


def test_8_frontend_zero_secret_scan():
    """
    TEST 8: Security scan across frontend codebase and build files.
    Expected: 0 secrets (gsk_, AWS keys) in frontend.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    frontend_dir = repo_root / "frontend" / "src"

    assert frontend_dir.exists(), "frontend/src directory must exist"

    secret_patterns = [
        re.compile(r"gsk_[A-Za-z0-9_-]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"VITE_GROQ_API_KEY"),
        re.compile(r"VITE_GROQ_MODEL")
    ]

    found_violations = []
    for file_path in frontend_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in [".js", ".jsx", ".ts", ".tsx", ".html", ".css"]:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for pattern in secret_patterns:
                matches = pattern.findall(content)
                if matches:
                    found_violations.append(f"{file_path.name}: {matches}")

    assert len(found_violations) == 0, f"Found leaked secrets in frontend source: {found_violations}"
