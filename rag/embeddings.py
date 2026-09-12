import logging
from typing import List, Union
from rag.config import rag_config

logger = logging.getLogger("cloudops.rag.embeddings")

class EmbeddingService:
    """
    Singleton service for generating embeddings using Sentence Transformers.
    Loads the model once and reuses it for all document batch and query embeddings.
    """
    _instance = None
    _model = None

    def __new__(cls, model_name: str = None):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = None):
        self.model_name = model_name or rag_config.EMBEDDING_MODEL

    def _get_model(self):
        if self._model is None:
            logger.info(f"Loading Sentence Transformer model: {self.model_name}")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Successfully loaded embedding model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model '{self.model_name}': {e}")
                raise RuntimeError(
                    f"Could not load Sentence Transformers model '{self.model_name}'. "
                    f"Ensure 'sentence-transformers' is installed. Original error: {e}"
                ) from e
        return self._model

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Embed a list of document chunks using batch processing.
        """
        if not texts:
            return []

        # Filter out empty or whitespace-only texts while maintaining valid structure or replacing with placeholder
        cleaned_texts = [text if (text and text.strip()) else " " for text in texts]

        model = self._get_model()
        try:
            embeddings = model.encode(
                cleaned_texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error during batch document embedding generation: {e}")
            raise RuntimeError(f"Failed to generate document embeddings: {e}") from e

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single search query string.
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for an empty or blank query string.")

        model = self._get_model()
        try:
            embedding = model.encode(
                text.strip(),
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error during query embedding generation for text '{text[:30]}...': {e}")
            raise RuntimeError(f"Failed to generate query embedding: {e}") from e

    def get_embedding_dimension(self) -> int:
        """
        Return vector dimension of current embedding model.
        """
        model = self._get_model()
        return model.get_sentence_embedding_dimension()
