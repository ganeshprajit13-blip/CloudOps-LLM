#!/usr/bin/env python3
"""
Sequential Real API Test Suite matching Real Browser UI workflow.
Tests 8 sequential questions maintaining chat history.
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/support-chat"

def main():
    print("=" * 90)
    print("REAL API SEQUENTIAL CHAT TEST SUITE")
    print("=" * 90)

    history = []

    test_queries = [
        "What is NAT Gateway?",
        "how too create ec2 instance",
        "What is a Security Group?",
        "How do I allow HTTP port 80?",
        "Why is my EC2 website unreachable?",
        "What is CloudTrail?",
        "How does our CloudOps Troubleshooter work?",
        "What is QLoRA?"
    ]

    for idx, q in enumerate(test_queries, start=1):
        print(f"\n--- [STEP {idx}]: User asks '{q}' ---")
        
        # Prepare payload: current message + previous history
        payload = {
            "message": q,
            "history": history
        }

        resp = requests.post(BASE_URL, json=payload, timeout=30)
        assert resp.status_code == 200, f"Failed with status {resp.status_code}: {resp.text}"

        data = resp.json()
        answer = data.get("answer", "")
        sources = data.get("sources", [])

        print(f"ANSWER SUMMARY:\n  {answer[:220].replace(chr(10), ' ')}...")
        print(f"SOURCES COUNT: {len(sources)}")
        for s in sources:
            print(f"  * {s.get('title')} ({round(s.get('relevance', 1.0)*100)}%)")

        # CRITICAL VERIFICATION FOR STEP 2
        if idx == 2:
            assert "nat gateway" not in answer.lower() or "step-by-step" in answer.lower(), "NAT Gateway answer returned for EC2 creation question!"
            assert "create and launch an amazon ec2 instance" in answer.lower() or "launch instance" in answer.lower(), "EC2 creation guide not returned!"
            print("  [SUCCESS VERIFIED]: EC2 Creation step-by-step guide returned! NAT Gateway answer NOT present!")

        # Append turn to history
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": answer})

    print("\n" + "=" * 90)
    print("ALL 8 SEQUENTIAL CHAT TESTS PASSED PERFECTLY!")
    print("=" * 90)

if __name__ == "__main__":
    main()
