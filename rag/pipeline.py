import logging
from pathlib import Path
from typing import Optional
from rag.config import rag_config
from rag.schemas import IngestionStats, RetrievalResponse
from rag.document_loader import DocumentLoader
from rag.chunker import DocumentChunker
from rag.embeddings import EmbeddingService
from rag.vector_store import ChromaVectorStore
from rag.retriever import RAGRetriever

logger = logging.getLogger("cloudops.rag.pipeline")

def ingest_documents(data_dir: str = "data/knowledge") -> IngestionStats:
    """
    Complete document ingestion workflow:
    Discover -> Load -> Normalize -> Chunk -> Embed -> Persistent ChromaDB Storage.
    
    Uses deterministic chunk IDs to avoid creating duplicates on repeated runs.
    """
    target_path = Path(data_dir)
    if not target_path.is_absolute():
        target_path = rag_config.BASE_DIR / target_path

    logger.info(f"Starting knowledge base ingestion from directory: {target_path}")

    stats = IngestionStats()

    # 1. Document Discovery & Loading
    loader = DocumentLoader()
    documents = loader.load_directory(target_path)
    stats.documents_discovered = len(documents)
    stats.documents_processed = len(documents)

    if not documents:
        logger.warning(f"No valid knowledge documents found in '{target_path}'. Ingestion completed with 0 items.")
        return stats

    # 2. Document Chunking
    chunker = DocumentChunker()
    chunks = chunker.chunk_documents(documents)
    stats.chunks_created = len(chunks)

    if not chunks:
        logger.warning("Document chunking produced 0 chunks.")
        return stats

    # 3. Generate Embeddings
    embedding_service = EmbeddingService()
    chunk_texts = [chunk.text for chunk in chunks]
    logger.info(f"Generating embeddings for {len(chunk_texts)} chunks...")
    embeddings = embedding_service.embed_documents(chunk_texts)

    # 4. Upsert into Vector Store (ChromaDB handles duplicates deterministically via chunk_id)
    vector_store = ChromaVectorStore()
    vector_store.create_collection()
    
    res = vector_store.add_documents(chunks, embeddings)
    stats.chunks_stored = res.get("added", len(chunks))
    stats.chunks_skipped = res.get("skipped", 0)

    logger.info(
        f"Ingestion completed successfully! "
        f"Processed {stats.documents_processed} documents into {stats.chunks_stored} stored chunks "
        f"(total vectors in collection: {vector_store.count()})."
    )
    return stats


def query_knowledge_base(
    query: str,
    top_k: int = None,
    service: Optional[str] = None,
    document_type: Optional[str] = None,
    min_score: Optional[float] = None
) -> RetrievalResponse:
    """
    Public entrypoint for querying the CloudOps RAG knowledge base.
    This function will be imported and called by Phase 7.
    """
    retriever = RAGRetriever()
    return retriever.retrieve(
        query=query,
        top_k=top_k,
        service=service,
        document_type=document_type,
        min_score=min_score
    )
