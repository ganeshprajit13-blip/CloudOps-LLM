#!/usr/bin/env python3
"""
Script to discover, load, chunk, embed, and ingest knowledge documents into ChromaDB.
Safe to run repeatedly.
"""

import sys
import logging
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from rag.pipeline import ingest_documents
from rag.vector_store import ChromaVectorStore
from rag.config import rag_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("ingest_knowledge")

def main():
    print("=" * 60)
    print("CloudOps RAG Knowledge Base - Ingestion Script")
    print("=" * 60)
    print(f"Embedding Model:         {rag_config.EMBEDDING_MODEL}")
    print(f"ChromaDB Storage Path:   {rag_config.CHROMA_PERSIST_DIRECTORY}")
    print(f"Collection Name:         {rag_config.CHROMA_COLLECTION_NAME}")
    print(f"Chunk Size / Overlap:    {rag_config.CHUNK_SIZE} / {rag_config.CHUNK_OVERLAP}")
    print("-" * 60)

    try:
        stats = ingest_documents("data/knowledge")
        vector_store = ChromaVectorStore()
        total_stored = vector_store.count()

        print("\nIngestion Summary Statistics:")
        print(f"  - Documents Discovered:  {stats.documents_discovered}")
        print(f"  - Documents Processed:   {stats.documents_processed}")
        print(f"  - Chunks Created:        {stats.chunks_created}")
        print(f"  - Chunks Stored/Upserted:{stats.chunks_stored}")
        print(f"  - Chunks Skipped:        {stats.chunks_skipped}")
        print(f"  - Total Vectors in Store:{total_stored}")
        print("=" * 60)
        print("Knowledge base ingestion complete!")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
