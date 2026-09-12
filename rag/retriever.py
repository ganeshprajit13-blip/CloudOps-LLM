import logging
from typing import List, Optional, Dict, Any
from rag.config import rag_config
from rag.schemas import RetrievalResult, RetrievalResponse
from rag.embeddings import EmbeddingService
from rag.vector_store import ChromaVectorStore

logger = logging.getLogger("cloudops.rag.retriever")

class RAGRetriever:
    """
    Handles knowledge retrieval for CloudOps queries.
    Converts text queries into embeddings, queries ChromaDB, converts distances
    to similarity scores, applies filters, and enforces relevance thresholds.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService = None,
        vector_store: ChromaVectorStore = None
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or ChromaVectorStore()

    @staticmethod
    def distance_to_score(distance: float) -> float:
        """
        Convert ChromaDB cosine distance to a normalized similarity score in range [0.0, 1.0].
        
        For Cosine Distance (hnsw:space = cosine):
            distance = 1.0 - cosine_similarity
            similarity_score = 1.0 - distance
            
        - Distance 0.0 -> Score 1.0 (identical vector / maximum similarity)
        - Distance 0.5 -> Score 0.5 (moderate similarity)
        - Distance 1.0+ -> Score 0.0 (unrelated or opposite vector)
        """
        score = max(0.0, min(1.0, 1.0 - float(distance)))
        return round(score, 4)

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        service: Optional[str] = None,
        document_type: Optional[str] = None,
        min_score: Optional[float] = None
    ) -> RetrievalResponse:
        """
        Retrieve ranked relevant knowledge chunks for a query string.
        """
        if not query or not query.strip():
            logger.warning("Received empty or blank query string.")
            return RetrievalResponse(
                query=query or "",
                results=[],
                message="Query string was empty or blank."
            )

        top_k = top_k if top_k is not None else rag_config.TOP_K
        min_score = min_score if min_score is not None else rag_config.RAG_MIN_SCORE

        # Construct ChromaDB metadata filter if specified
        where_filter = {}
        if service and service.lower() != "all":
            where_filter["service"] = service.lower()
        if document_type and document_type.lower() != "all":
            where_filter["document_type"] = document_type.lower()

        if not where_filter:
            where_filter = None

        logger.info(
            f"Retrieving top_{top_k} results for query: '{query}' "
            f"(filters={where_filter}, min_score={min_score})"
        )

        try:
            query_embedding = self.embedding_service.embed_query(query)
            raw_results = self.vector_store.query(
                query_embedding=query_embedding,
                top_k=top_k,
                where_filter=where_filter
            )
        except Exception as e:
            logger.error(f"Error executing vector retrieval: {e}")
            return RetrievalResponse(
                query=query,
                results=[],
                message=f"Retrieval error: {str(e)}"
            )

        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]

        if not documents:
            logger.info("No matching vector results returned from ChromaDB.")
            return RetrievalResponse(
                query=query,
                results=[],
                message="No sufficiently relevant knowledge was found in the knowledge base."
            )

        retrieved_results: List[RetrievalResult] = []
        for text, meta, dist in zip(documents, metadatas, distances):
            score = self.distance_to_score(dist)
            
            # Apply relevance threshold filter
            if score >= min_score:
                retrieved_results.append(
                    RetrievalResult(
                        text=text,
                        score=score,
                        distance=round(float(dist), 4),
                        metadata=meta or {}
                    )
                )

        if not retrieved_results:
            logger.info(f"Retrieved {len(documents)} raw candidates, but none met min_score threshold ({min_score}).")
            return RetrievalResponse(
                query=query,
                results=[],
                message=f"No knowledge met the relevance threshold ({min_score})."
            )

        logger.info(f"Successfully retrieved {len(retrieved_results)} relevant knowledge chunks.")
        return RetrievalResponse(
            query=query,
            results=retrieved_results,
            message=None
        )
