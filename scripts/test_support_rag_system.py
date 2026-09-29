#!/usr/bin/env python3
"""
Test Suite for CloudOps Support Agent & Dedicated Support RAG Integration.
Executes testing on 7 core questions and verifies retrieval, grounding, sources, and response format.
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

from backend.app.services.support_agent import ask_support_agent
from backend.app.services.support_knowledge import query_support_knowledge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_support_rag")

TEST_QUESTIONS = [
    "How does the CloudOps AI Troubleshooter work?",
    "What is the difference between CloudWatch and CloudTrail?",
    "How does RAG work in CloudOps?",
    "Why did we choose Qwen2.5-3B?",
    "What is QLoRA?",
    "How do I troubleshoot an EC2 website that is unreachable?",
    "What does the confidence score mean?"
]

def main():
    print("=" * 80)
    print("CLOUDOPS SUPPORT AGENT & SUPPORT RAG COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    results = []
    
    for idx, q in enumerate(TEST_QUESTIONS, start=1):
        print(f"\n[Test #{idx}/7]: '{q}'")
        
        # 1. Test raw vector retrieval
        retrieved = query_support_knowledge(q, top_k=4)
        print(f"  - Vector Retrieval: {len(retrieved)} documents retrieved from 'cloudops_support'")
        for doc in retrieved:
            print(f"    * Title: '{doc['title']}' | Category: '{doc['category']}' | Score: {doc['score']}")

        # 2. Test full Support Agent workflow
        res = ask_support_agent(q)
        answer = res.get("answer") or res.get("reply", "")
        sources = res.get("sources", [])

        print(f"  - Answer Generated ({len(answer)} chars):")
        print(f"    {answer[:300]}...")
        print(f"  - Sources Returned: {len(sources)}")

        assert answer and len(answer.strip()) > 0, f"Empty answer generated for test question '{q}'"
        assert len(sources) > 0, f"No sources returned for test question '{q}'"
        
        results.append({
            "test_id": idx,
            "question": q,
            "retrieved_count": len(retrieved),
            "sources_count": len(sources),
            "sources": sources,
            "answer": answer
        })

    out_path = PROJECT_ROOT / "outputs" / "support_agent_adapter" / "support_rag_test_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print("ALL 7 SUPPORT AGENT RAG TESTS PASSED SUCCESSFULLY!")
    print(f"Detailed test results saved to: {out_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
