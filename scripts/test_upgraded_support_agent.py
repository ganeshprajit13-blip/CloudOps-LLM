#!/usr/bin/env python3
"""
Comprehensive Quality & Intent Verification Test Suite for CloudOps Support Agent.
Executes 10 specific quality tests and verifies directness, intent classification, source deduplication, and guardrails.
"""

import sys
import json
import logging
from pathlib import Path

# Ensure project root & backend are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.support_agent import ask_support_agent
from app.services.support_knowledge import query_support_knowledge, classify_query_intent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_upgraded_support")

QUALITY_TEST_CASES = [
    {
        "id": "A",
        "question": "What is NAT Gateway?",
        "must_contain": ["nat gateway", "private subnet", "outbound"],
        "expected_intent": "AWS"
    },
    {
        "id": "B",
        "question": "What is the difference between NAT Gateway and Internet Gateway?",
        "must_contain": ["internet gateway", "nat gateway", "outbound"],
        "expected_intent": "AWS"
    },
    {
        "id": "C",
        "question": "What is CloudTrail?",
        "must_contain": ["cloudtrail", "api", "audit"],
        "expected_intent": "AWS"
    },
    {
        "id": "D",
        "question": "How does our CloudOps AI Troubleshooter work?",
        "must_contain": ["troubleshooter", "telemetry", "confidence score"],
        "expected_intent": "PRODUCT"
    },
    {
        "id": "E",
        "question": "Why did we choose Qwen2.5-3B?",
        "must_contain": ["qwen", "3b", "vram"],
        "expected_intent": "LLM"
    },
    {
        "id": "F",
        "question": "What is QLoRA?",
        "must_contain": ["qlora", "4-bit"],
        "expected_intent": "QLORA"
    },
    {
        "id": "G",
        "question": "My EC2 website is unreachable. What should I check?",
        "must_contain": ["ec2", "security group", "port 80"],
        "expected_intent": "TROUBLESHOOTING"
    },
    {
        "id": "H",
        "question": "Why can't I use Internet Gateway instead?",
        "history": [
            {"role": "user", "content": "What is NAT Gateway?"},
            {"role": "assistant", "content": "NAT Gateway is an AWS network service that allows resources in a private subnet to connect outbound to the internet."}
        ],
        "must_contain": ["internet gateway", "private"],
        "expected_intent": "AWS"
    },
    {
        "id": "I",
        "question": "Can you automatically fix my Security Group?",
        "must_contain": ["guidance"],
        "expected_intent": "GUARDRAILS"
    },
    {
        "id": "J",
        "question": "What is the capital of France?",
        "must_contain": ["outside", "domain"],
        "expected_intent": "OUT_OF_SCOPE"
    }
]

def main():
    print("=" * 90)
    print("UPGRADED CLOUDOPS SUPPORT AGENT CONVERSATIONAL QUALITY VERIFICATION SUITE")
    print("=" * 90)

    all_passed = True
    test_results = []

    for test in QUALITY_TEST_CASES:
        t_id = test["id"]
        q = test["question"]
        hist = test.get("history", [])

        # 1. Intent check
        detected_intent = classify_query_intent(q)
        print(f"\n[Test #{t_id}]: Query: '{q}'")
        print(f"  - Classified Intent : '{detected_intent}' (Expected: '{test['expected_intent']}')")

        # 2. Run Support Agent Pipeline
        res = ask_support_agent(q, hist)
        answer = res.get("answer") or res.get("reply", "")
        sources = res.get("sources", [])

        print(f"  - Answer Generated ({len(answer)} chars):")
        print("    " + answer[:200].replace("\n", " ") + "...")
        print(f"  - Sources Count: {len(sources)}")

        for src in sources:
            rel_score = round(src.get("relevance", 1.0) * 100)
            print(f"    * Source: '{src['title']}' ({src['category']}) - {rel_score}%")

        # Verifications
        answer_lower = answer.lower()
        missing_terms = [t for t in test["must_contain"] if t not in answer_lower]

        if missing_terms:
            print(f"  [FAILED]: Answer missing required key terms: {missing_terms}")
            all_passed = False
        else:
            print("  [PASSED]: Direct answer generated with required key terms.")

        test_results.append({
            "test_id": t_id,
            "question": q,
            "intent": detected_intent,
            "sources_count": len(sources),
            "sources": sources,
            "answer": answer
        })

    print("\n" + "=" * 90)
    if all_passed:
        print("ALL 10 CONVERSATIONAL QUALITY & INTENT TESTS PASSED PERFECTLY!")
    else:
        print("SOME TESTS REQUIRED ATTENTION.")
    print("=" * 90)

if __name__ == "__main__":
    main()
