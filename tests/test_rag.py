import os
import sys
import shutil
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest

from rag.config import RAGConfig, rag_config
from rag.schemas import Document, DocumentMetadata, DocumentChunk
from rag.document_loader import DocumentLoader
from rag.chunker import DocumentChunker
from rag.embeddings import EmbeddingService
from rag.vector_store import ChromaVectorStore
from rag.retriever import RAGRetriever
from rag.pipeline import ingest_documents, query_knowledge_base

@pytest.fixture
def temp_dir():
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


def test_rag_config():
    config = RAGConfig()
    assert config.EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"
    assert config.CHROMA_COLLECTION_NAME == "cloudops_knowledge"
    assert config.CHUNK_SIZE == 800
    assert config.CHUNK_OVERLAP == 120
    assert config.TOP_K == 5


def test_document_loader(temp_dir):
    loader = DocumentLoader()

    # Create dummy markdown file
    md_file = temp_dir / "ec2_test.md"
    md_file.write_text("# EC2 Troubleshooting\n\nCheck security groups on port 22.", encoding="utf-8")

    # Create dummy json file
    json_file = temp_dir / "alb_test.json"
    json_file.write_text('{"title": "ALB Issue", "text": "HTTP 502 error", "service": "alb"}', encoding="utf-8")

    # Create dummy sensitive file to ignore
    env_file = temp_dir / ".env"
    env_file.write_text("SECRET_KEY=12345", encoding="utf-8")

    docs = loader.load_directory(temp_dir)
    assert len(docs) == 2

    services = {doc.metadata.service for doc in docs}
    assert "ec2" in services
    assert "alb" in services


def test_chunker_deterministic_id():
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    
    meta = DocumentMetadata(
        source="test.md",
        title="Test Doc",
        category="test",
        service="ec2",
        document_type="documentation"
    )
    doc = Document(text="This is a test document to verify chunking and deterministic ID generation.", metadata=meta)
    
    chunks1 = chunker.chunk_document(doc)
    chunks2 = chunker.chunk_document(doc)

    assert len(chunks1) > 0
    assert len(chunks1) == len(chunks2)
    assert chunks1[0].chunk_id == chunks2[0].chunk_id


def test_embedding_service():
    embedder = EmbeddingService()
    
    # Batch embedding
    embeddings = embedder.embed_documents(["EC2 security group rule", "VPC NAT Gateway route"])
    assert len(embeddings) == 2
    assert len(embeddings[0]) > 0

    # Query embedding
    q_embed = embedder.embed_query("Why is port 443 blocked?")
    assert len(q_embed) == len(embeddings[0])

    # Empty query exception
    with pytest.raises(ValueError):
        embedder.embed_query("   ")


def test_vector_store_and_retriever(temp_dir):
    persist_path = str(temp_dir / "chroma_test")
    v_store = ChromaVectorStore(persist_directory=persist_path, collection_name="test_collection")
    v_store.reset_collection()

    chunker = DocumentChunker(chunk_size=200, chunk_overlap=20)
    meta = DocumentMetadata(
        source="alb_guide.md",
        title="ALB Health Check",
        category="aws",
        service="alb",
        document_type="documentation"
    )
    doc = Document(
        text="Application Load Balancer (ALB) HTTP 502 Bad Gateway occurs when target group health checks fail.",
        metadata=meta
    )
    chunks = chunker.chunk_document(doc)

    embedder = EmbeddingService()
    texts = [c.text for c in chunks]
    embeddings = embedder.embed_documents(texts)

    v_store.add_documents(chunks, embeddings)
    assert v_store.count() == len(chunks)

    retriever = RAGRetriever(embedding_service=embedder, vector_store=v_store)
    response = retriever.retrieve(query="Why am I getting 502 error on ALB?", top_k=2)

    assert len(response.results) > 0
    assert response.results[0].metadata["service"] == "alb"
    assert response.results[0].score >= 0.0


def test_retriever_filtering_and_threshold(temp_dir):
    persist_path = str(temp_dir / "chroma_filter_test")
    v_store = ChromaVectorStore(persist_directory=persist_path, collection_name="filter_collection")
    v_store.reset_collection()

    embedder = EmbeddingService()

    doc1 = Document(
        text="Security groups filter incoming traffic on port 443.",
        metadata=DocumentMetadata(source="sg.md", title="SG", category="aws", service="security_group")
    )
    doc2 = Document(
        text="NAT gateway enables outbound internet access for private subnets.",
        metadata=DocumentMetadata(source="nat.md", title="NAT", category="aws", service="vpc")
    )

    chunker = DocumentChunker()
    chunks = chunker.chunk_documents([doc1, doc2])
    embeddings = embedder.embed_documents([c.text for c in chunks])

    v_store.add_documents(chunks, embeddings)

    retriever = RAGRetriever(embedding_service=embedder, vector_store=v_store)

    # Test service filter for security_group
    res_sg = retriever.retrieve(query="internet access", service="security_group")
    assert len(res_sg.results) == 1
    assert res_sg.results[0].metadata["service"] == "security_group"

    # Test high min_score threshold
    res_high_thresh = retriever.retrieve(query="completely unrelated random query xkwz99", min_score=0.99)
    assert len(res_high_thresh.results) == 0
