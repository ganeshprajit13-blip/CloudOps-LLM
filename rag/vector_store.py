import os
import logging
from typing import List, Dict, Any, Optional
from rag.config import rag_config
from rag.schemas import DocumentChunk

logger = logging.getLogger("cloudops.rag.vector_store")

class ChromaVectorStore:
    """
    Persistent ChromaDB vector database manager for CloudOps RAG knowledge base.
    """

    def __init__(
        self,
        persist_directory: str = None,
        collection_name: str = None
    ):
        self.persist_directory = persist_directory or rag_config.CHROMA_PERSIST_DIRECTORY
        self.collection_name = collection_name or rag_config.CHROMA_COLLECTION_NAME
        self._client = None
        self._collection = None

        os.makedirs(self.persist_directory, exist_ok=True)

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings

                logger.info(f"Initializing ChromaDB PersistentClient at: {self.persist_directory}")
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(allow_reset=True, anonymized_telemetry=False)
                )
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB PersistentClient: {e}")
                raise RuntimeError(f"Could not initialize ChromaDB: {e}") from e
        return self._client

    def create_collection(self):
        """Get or create the ChromaDB collection with cosine similarity distance metric."""
        client = self._get_client()
        try:
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(
                f"Collection '{self.collection_name}' ready. "
                f"Existing items: {self._collection.count()}"
            )
            return self._collection
        except Exception as e:
            logger.error(f"Failed to get/create ChromaDB collection '{self.collection_name}': {e}")
            raise RuntimeError(f"ChromaDB collection error: {e}") from e

    def get_collection(self):
        if self._collection is None:
            return self.create_collection()
        return self._collection

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all metadata values are primitive types (str, int, float, bool) supported by ChromaDB."""
        sanitized = {}
        for key, val in metadata.items():
            if val is None:
                sanitized[key] = ""
            elif isinstance(val, (str, int, float, bool)):
                sanitized[key] = val
            else:
                sanitized[key] = str(val)
        return sanitized

    def add_documents(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]]
    ) -> Dict[str, int]:
        """
        Add document chunks and their embeddings to ChromaDB.
        Uses deterministic chunk_id to upsert/update content.
        """
        if not chunks:
            return {"added": 0, "skipped": 0}

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch between number of chunks ({len(chunks)}) and embeddings ({len(embeddings)})."
            )

        collection = self.get_collection()

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [self._sanitize_metadata(chunk.metadata) for chunk in chunks]

        try:
            # ChromaDB upsert updates existing IDs or inserts new ones deterministically
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Successfully upserted {len(chunks)} chunks into ChromaDB collection '{self.collection_name}'.")
            return {"added": len(chunks), "skipped": 0}
        except Exception as e:
            logger.error(f"Error adding documents to ChromaDB: {e}")
            raise RuntimeError(f"ChromaDB upsert failed: {e}") from e

    def delete_documents(self, ids: List[str]) -> bool:
        """Delete documents by chunk IDs."""
        if not ids:
            return True
        collection = self.get_collection()
        try:
            collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} document chunks from collection '{self.collection_name}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document chunks from ChromaDB: {e}")
            return False

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query ChromaDB by embedding vector with optional metadata filtering.
        """
        collection = self.get_collection()
        top_k = max(1, top_k)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"]
        }

        if where_filter:
            kwargs["where"] = where_filter

        try:
            results = collection.query(**kwargs)
            return results
        except Exception as e:
            logger.error(f"ChromaDB query error: {e}")
            raise RuntimeError(f"Failed to query ChromaDB: {e}") from e

    def count(self) -> int:
        """Return total count of stored vector chunks."""
        collection = self.get_collection()
        return collection.count()

    def reset_collection(self) -> bool:
        """Clear and delete the collection entirely."""
        client = self._get_client()
        try:
            client.delete_collection(name=self.collection_name)
            self._collection = None
            logger.info(f"Successfully reset and deleted collection '{self.collection_name}'.")
            self.create_collection()
            return True
        except Exception as e:
            logger.warning(f"Could not delete collection '{self.collection_name}' (it may not exist): {e}")
            self.create_collection()
            return True
