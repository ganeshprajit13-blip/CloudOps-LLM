#!/usr/bin/env python3
"""
Test User Prompt Queries A through J for CloudOps Support Agent.
"""

import sys
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.support_agent import ask_support_agent

def main():
    print("=" * 90)
    print("TESTING USER PROMPT SPECIFIED QUERIES A THROUGH J")
    print("=" * 90)

    # We will simulate conversation history where appropriate
    history_c = []

    tests = [
        {"id": "A", "query": "hi", "history": []},
        {"id": "B", "query": "whai nacl in subnet", "history": []},
        {"id": "C", "query": "What is NACL?", "history": []},
        # D follows C
        {"id": "D", "query": "Why do we need it?", "history": [
            {"role": "user", "content": "What is NACL?"},
            {"role": "assistant", "content": "NACL (Network Access Control List) is an optional layer of security for your VPC that acts as a firewall for controlling traffic in and out of one or more subnets."}
        ]},
        {"id": "E", "query": "NACL vs Security Group", "history": []},
        {"id": "F", "query": "What is NAT Gateway?", "history": []},
        {"id": "G", "query": "What is CloudTrail?", "history": []},
        {"id": "H", "query": "How does our CloudOps Troubleshooter work?", "history": []},
        {"id": "I", "query": "What is QLoRA?", "history": []},
        {"id": "J", "query": "What is the capital of France?", "history": []},
    ]

    results = []

    for test in tests:
        t_id = test["id"]
        q = test["query"]
        hist = test["history"]

        print(f"\n--- [TEST {t_id}]: '{q}' ---")
        res = ask_support_agent(q, hist)
        answer = res.get("answer") or res.get("reply", "")
        sources = res.get("sources", [])

        print(f"ANSWER:\n{answer}")
        print(f"SOURCES ({len(sources)}):")
        for s in sources:
            print(f"  - {s.get('title')} ({round(s.get('relevance', 1.0)*100)}%)")

        results.append({
            "id": t_id,
            "query": q,
            "answer": answer,
            "sources": sources
        })

    with open("scratch/test_results_a_j.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nResults saved to scratch/test_results_a_j.json")

if __name__ == "__main__":
    main()
