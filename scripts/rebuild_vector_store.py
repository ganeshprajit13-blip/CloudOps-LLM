#!/usr/bin/env python3
"""
Script to reset existing ChromaDB collection and re-ingest all knowledge documents from scratch.
Must be explicitly invoked.
"""

import sys
import logging
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from rag.vector_store import ChromaVectorStore
from rag.pipeline import ingest_documents
from rag.config import rag_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("rebuild_vector_store")

def main():
    print("=" * 60)
    print("CloudOps RAG Knowledge Base - Rebuild Vector Store")
    print("=" * 60)
    print(f"Target Collection: {rag_config.CHROMA_COLLECTION_NAME}")
    print(f"Storage Directory: {rag_config.CHROMA_PERSIST_DIRECTORY}")
    print("-" * 60)

    vector_store = ChromaVectorStore()
    
    initial_count = vector_store.count()
    print(f"Current vectors in collection: {initial_count}")
    print("Resetting ChromaDB collection...")

    reset_success = vector_store.reset_collection()
    if not reset_success:
        print("Failed to reset vector collection.")
        sys.exit(1)

    print("Collection reset complete. Re-ingesting all knowledge documents...")
    stats = ingest_documents("data/knowledge")

    final_count = vector_store.count()
    print("\nRebuild Completed Successfully:")
    print(f"  - Documents Ingested:    {stats.documents_processed}")
    print(f"  - Total Chunks Created:  {stats.chunks_created}")
    print(f"  - Final Vector Count:    {final_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()
