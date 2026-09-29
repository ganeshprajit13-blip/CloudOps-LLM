#!/usr/bin/env python3
"""
Support Knowledge Base Ingestion Script for CloudOps Support Agent.
Reads support documentation from data/support_knowledge/, chunks text,
generates dense vector embeddings using SentenceTransformers,
and upserts vector chunks into the dedicated 'cloudops_support' ChromaDB collection.

Idempotent: Safe to run repeatedly.
"""

import os
import sys
import glob
import re
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("ingest_support_knowledge")

CHROMA_PERSIST_DIR = str(PROJECT_ROOT / "storage" / "chroma_support")
COLLECTION_NAME = "cloudops_support"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
SUPPORT_DATA_DIR = str(PROJECT_ROOT / "data" / "support_knowledge")

def extract_category_and_title(filepath: str, content: str) -> tuple:
    """Extract category and title from document content or filename."""
    filename = os.path.basename(filepath)
    category = "general"
    if "architecture" in filename or "overview" in filename:
        category = "product"
    elif "troubleshooter" in filename or "workflow" in filename:
        category = "troubleshooter"
    elif "aws" in filename or "infrastructure" in filename:
        category = "aws"
    elif "llm" in filename or "qlora" in filename or "rag" in filename:
        category = "ai_llm"
    elif "faq" in filename:
        category = "faqs"

    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filename.replace(".md", "").replace("_", " ").title()
    return category, title

def chunk_markdown(content: str, max_chunk_size: int = 600, overlap: int = 100) -> List[str]:
    """Split markdown text into logical chunks by sections or character windows."""
    sections = re.split(r"\n(?=##\s+)", content)
    chunks = []
    
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        if len(sec) <= max_chunk_size:
            chunks.append(sec)
        else:
            # Sliding window for long sections
            start = 0
            while start < len(sec):
                end = min(start + max_chunk_size, len(sec))
                chunk_str = sec[start:end].strip()
                if chunk_str:
                    chunks.append(chunk_str)
                if end == len(sec):
                    break
                start += (max_chunk_size - overlap)
    return chunks

def main():
    print("=" * 70)
    print("CloudOps Dedicated Support Knowledge Base - Ingestion Script")
    print("=" * 70)
    print(f"  - Target Collection : '{COLLECTION_NAME}'")
    print(f"  - ChromaDB Storage   : {CHROMA_PERSIST_DIR}")
    print(f"  - Embedding Model    : {EMBEDDING_MODEL_NAME}")
    print(f"  - Data Directory     : {SUPPORT_DATA_DIR}")
    print("-" * 70)

    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
    
    md_files = sorted(glob.glob(os.path.join(SUPPORT_DATA_DIR, "*.md")))
    if not md_files:
        logger.error(f"No markdown documents found in {SUPPORT_DATA_DIR}")
        sys.exit(1)

    logger.info(f"Found {len(md_files)} support documentation files.")

    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer

    # 1. Initialize ChromaDB client & dedicated collection
    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(allow_reset=True, anonymized_telemetry=False)
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # 2. Load Embedding Model
    logger.info(f"Loading embedding model '{EMBEDDING_MODEL_NAME}'...")
    try:
        embedder = SentenceTransformer(EMBEDDING_MODEL_NAME, local_files_only=True)
    except Exception:
        embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # 3. Process documents & create chunks
    all_ids = []
    all_documents = []
    all_metadatas = []
    total_chunks = 0

    for filepath in md_files:
        rel_filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        category, doc_title = extract_category_and_title(filepath, content)
        chunks = chunk_markdown(content, max_chunk_size=700, overlap=100)
        
        logger.info(f"Processing '{rel_filename}' -> Category: '{category}', Title: '{doc_title}', Chunks: {len(chunks)}")
        
        for idx, chunk_text in enumerate(chunks):
            # Deterministic chunk ID to ensure idempotency
            chunk_hash = hashlib.sha256(f"{rel_filename}_{idx}_{chunk_text[:50]}".encode()).hexdigest()[:12]
            chunk_id = f"supp_{rel_filename.replace('.md', '')}_{idx}_{chunk_hash}"
            
            meta = {
                "source": rel_filename,
                "category": category,
                "document_title": doc_title,
                "chunk_index": idx
            }
            
            all_ids.append(chunk_id)
            all_documents.append(f"{doc_title}\n\n{chunk_text}")
            all_metadatas.append(meta)
            total_chunks += 1

    # 4. Generate Embeddings
    logger.info(f"Generating dense embeddings for {total_chunks} support chunks...")
    embeddings = embedder.encode(all_documents, convert_to_numpy=True, normalize_embeddings=True).tolist()

    # 5. Upsert into ChromaDB
    logger.info(f"Upserting {total_chunks} vector chunks into ChromaDB collection '{COLLECTION_NAME}'...")
    collection.upsert(
        ids=all_ids,
        documents=all_documents,
        embeddings=embeddings,
        metadatas=all_metadatas
    )

    final_count = collection.count()
    print("=" * 70)
    print("INGESTION COMPLETE")
    print(f"  - Files Ingested      : {len(md_files)}")
    print(f"  - Total Chunks Upserted: {total_chunks}")
    print(f"  - Final Vector Count  : {final_count} in collection '{COLLECTION_NAME}'")
    print("=" * 70)

if __name__ == "__main__":
    main()
