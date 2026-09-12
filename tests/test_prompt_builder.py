import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.schemas.analysis import RetrievedKnowledgeItem
from app.services.prompt_builder import PromptBuilder

def test_prompt_builder_structure():
    builder = PromptBuilder()

    question = "Why is port 443 blocked?"
    formatted_context = "=== CURRENT CLOUD STATE ===\nEC2 running with SG sg-12345."
    knowledge_items = [
        RetrievedKnowledgeItem(
            source="security_group_troubleshooting.md",
            title="SG Guide",
            service="security_group",
            score=0.85,
            text="Verify inbound TCP 443 rule exists."
        )
    ]

    prompt = builder.build_prompt(question, formatted_context, knowledge_items)

    assert "You are CloudOps LLM" in prompt
    assert "Why is port 443 blocked?" in prompt
    assert "=== CURRENT CLOUD STATE ===" in prompt
    assert "RETRIEVED KNOWLEDGE" in prompt
    assert "security_group_troubleshooting.md" in prompt
    assert "Verify inbound TCP 443 rule exists." in prompt
    assert "Required Output JSON Schema" in prompt


def test_prompt_builder_empty_knowledge():
    builder = PromptBuilder()
    prompt = builder.build_prompt("Why is EC2 CPU high?", "Context", [])
    assert "No additional operational knowledge retrieved" in prompt
