# CloudOps RAG Knowledge Base Architecture & Manual

Welcome to Phase 6 of the **CloudOps LLM Project**: The Standalone RAG Knowledge Base System.

---

## 1. What is RAG?
**RAG** stands for **Retrieval-Augmented Generation**. It is a technique used in modern AI systems to enhance Large Language Models (LLMs) by retrieving relevant background facts, runbooks, documentation, and historical incident postmortems from an external vector database before producing a final answer.

---

## 2. Why CloudOps Uses RAG
Cloud infrastructure management involves huge volumes of domain knowledge (AWS service limits, VPC routing mechanics, security group statefulness, ALB health check logic, system logs, and internal operational runbooks).

Instead of forcing the LLM to memorize every static configuration or private operational runbook inside its neural network weights, CloudOps uses RAG to:
- Dynamically ground diagnoses in verified, authoritative documentation.
- Eliminate hallucinations regarding command flags, architectural best practices, and security rules.
- Instantly update troubleshooting knowledge without retraining or fine-tuning the LLM.

---

## 3. Key Concepts & Differences

| Technology / Component | Role in CloudOps Architecture |
| :--- | :--- |
| **Qwen2.5-3B-Instruct (Transformer)** | **Reasoning & Synthesis Engine**: Analyzes context and generates final diagnostic explanations and recommendations. |
| **LoRA / QLoRA** | **Domain Adaptation**: Fine-tunes Qwen's tone, reasoning style, and structural output format for cloud troubleshooting. |
| **Sentence Transformers** | **Vector Embedding Generator**: Encodes text chunks and queries into dense numerical vector representations. |
| **ChromaDB** | **Persistent Vector Database**: Stores embeddings and chunk metadata, performing fast similarity search. |
| **RAG System** | **Knowledge Retrieval Pipeline**: Fetches top-k relevant knowledge chunks to supply to the LLM. |

---

## 4. Architectural Pipeline

```
   User Query / Incident
            │
            ▼
   EmbeddingService (SentenceTransformers)
            │  (Generates Query Vector)
            ▼
   ChromaVectorStore (ChromaDB Persistent Client)
            │  (Cosine Similarity Search + Metadata Filtering)
            ▼
   Top-K Relevant Chunks (Ranked & Score-Normalized)
            │
            ▼
   RAGRetriever -> Phase 7 Integration
```

---

## 5. Module Structure

```
rag/
├── __init__.py          # Package exports
├── config.py            # Environment-driven RAG configuration
├── schemas.py           # Pydantic data models (Document, Chunk, RetrievalResult, etc.)
├── embeddings.py        # Sentence Transformers singleton embedding service
├── document_loader.py   # Loader for .txt, .md, .json, .jsonl files with security filters
├── chunker.py           # Paragraph-aware document splitter with deterministic IDs
├── vector_store.py      # ChromaDB client wrapper for persistent storage
├── retriever.py         # Query execution, distance-to-score normalization, filtering
├── pipeline.py          # Ingestion workflow & public query_knowledge_base interface
└── README.md            # Comprehensive documentation
```

---

## 6. How Ingestion & Chunking Work

### Document Loading (`rag/document_loader.py`)
- Discovers `.txt`, `.md`, `.json`, and `.jsonl` files in `data/knowledge/`.
- Excludes sensitive files (`.env`, secrets, `.git`, `credentials`, private keys).
- Extracts metadata (`source`, `category`, `title`, `service`, `document_type`, timestamps).

### Chunking (`rag/chunker.py`)
- Splits long documents into manageable text chunks using configurable parameters:
  - `CHUNK_SIZE` (Default: `800` characters)
  - `CHUNK_OVERLAP` (Default: `120` characters)
- Generates **deterministic chunk IDs** via SHA-256 hashing (`hashlib.sha256(source + chunk_index + content_hash)`).
- Deterministic IDs ensure duplicate documents are skipped or safely updated on repeated ingestion runs without creating duplicate database records.

---

## 7. Vector Search & Similarity Score

ChromaDB uses `hnsw:space = cosine` (Cosine Distance).
- **Cosine Distance ($d$)** range: $0.0 \le d \le 2.0$.
- **Normalized Similarity Score ($S$)**: $S = 1.0 - d$.
  - $S = 1.0$: Identical vector / perfect match.
  - $S = 0.5$: Moderate semantic similarity.
  - $S = 0.0$: Unrelated content.

---

## 8. Metadata Filtering & Relevance Thresholds

- **Service Filtering**: Filter knowledge chunks by AWS service (e.g. `ec2`, `vpc`, `alb`, `security_group`, `cloudwatch`, `cloudtrail`, `iam`).
- **Document Type Filtering**: Restrict retrieval by category (`documentation`, `runbook`, `incident`, `postmortem`, `troubleshooting`).
- **Relevance Threshold (`RAG_MIN_SCORE`)**: If no retrieved chunk achieves $S \ge \text{RAG\_MIN\_SCORE}$, the retriever returns an empty result set instead of cluttering output with irrelevant documents.

---

## 9. Operation & Management Commands

### Ingest Knowledge Base
Ingest or update documents from `data/knowledge/`:
```bash
python scripts/ingest_knowledge.py
```

### Rebuild Vector Database
Reset ChromaDB collection and re-ingest all documents:
```bash
python scripts/rebuild_vector_store.py
```

### Test Retrieval Quality
Verify top-k retrieval for core CloudOps failure scenarios:
```bash
python scripts/test_rag.py
```

---

## 10. How Phase 7 Integrates RAG

In Phase 7, the query function is imported as:
```python
from rag.pipeline import query_knowledge_base

response = query_knowledge_base(
    query="Why is my ALB returning 502 Bad Gateway?",
    top_k=5,
    service="alb"
)
```

The retrieved context chunks will then be formatted into Qwen2.5-3B-Instruct's prompt template alongside real-time AWS Boto3 telemetry.

---

## 11. System Limitations
1. **Static Knowledge Snapshot**: Knowledge base must be updated and re-ingested when operational procedures change.
2. **Context Window Allocation**: Top-k chunks must fit within the LLM's prompt context limit.
3. **No Direct AWS API Execution**: Phase 6 RAG retrieves static knowledge documents, not live AWS state (live telemetry is handled by Phase 2/3 and integrated in Phase 7).
