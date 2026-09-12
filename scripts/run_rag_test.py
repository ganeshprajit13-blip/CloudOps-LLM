#!/usr/bin/env python3
"""
Test script for verifying RAG retrieval quality across core CloudOps failure scenarios.
"""

import sys
import logging
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from rag.pipeline import query_knowledge_base
from rag.config import rag_config

logging.basicConfig(level=logging.WARNING)

TEST_QUERIES = [
    {
        "query": "Why is HTTPS traffic blocked?",
        "expected_topic": "Security Group / TCP 443"
    },
    {
        "query": "Why is my ALB target unhealthy?",
        "expected_topic": "ALB / Target Group / Health Checks"
    },
    {
        "query": "Why can't my private subnet reach the internet?",
        "expected_topic": "NAT Gateway / VPC Route Table"
    },
    {
        "query": "Who changed my AWS security configuration?",
        "expected_topic": "CloudTrail Audit Events"
    }
]

def format_preview(text: str, max_length: int = 150) -> str:
    """Format a clean, truncated text snippet."""
    single_line = " ".join(text.split())
    if len(single_line) > max_length:
        return single_line[:max_length] + "..."
    return single_line

def main():
    print("=" * 70)
    print("CloudOps RAG Knowledge Base - Retrieval Verification Test")
    print("=" * 70)
    print(f"Embedding Model: {rag_config.EMBEDDING_MODEL}")
    print(f"Collection:      {rag_config.CHROMA_COLLECTION_NAME}")
    print("=" * 70)

    for idx, item in enumerate(TEST_QUERIES, 1):
        query_text = item["query"]
        expected_topic = item["expected_topic"]

        print(f"\n[Test Case {idx}]")
        print(f"Query:          \"{query_text}\"")
        print(f"Expected Topic: {expected_topic}")
        print("-" * 70)

        response = query_knowledge_base(query=query_text, top_k=3)

        if not response.results:
            print("  [!] No matching results returned or threshold not met.")
            if response.message:
                print(f"      Message: {response.message}")
            continue

        print(f"Top {len(response.results)} Retrieved Knowledge Chunks:")
        for rank, res in enumerate(response.results, 1):
            meta = res.metadata
            source = meta.get("source", "unknown")
            title = meta.get("title", "Untitled")
            service = meta.get("service", "general")
            score = res.score
            preview = format_preview(res.text)

            print(f"  {rank}. Source:  {source}")
            print(f"     Title:   {title}")
            print(f"     Service: {service}")
            print(f"     Score:   {score:.4f} (Distance: {res.distance})")
            print(f"     Preview: \"{preview}\"")
            print()

    print("=" * 70)
    print("RAG Retrieval Test Execution Complete.")
    print("=" * 70)

if __name__ == "__main__":
    main()
