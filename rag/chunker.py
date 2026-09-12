import hashlib
import logging
from typing import List, Dict, Any
from rag.config import rag_config
from rag.schemas import Document, DocumentChunk

logger = logging.getLogger("cloudops.rag.chunker")

class DocumentChunker:
    """
    Splits documents into overlapping text chunks while respecting paragraph and section boundaries.
    Generates deterministic IDs for each chunk.
    """

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or rag_config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or rag_config.CHUNK_OVERLAP

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"CHUNK_OVERLAP ({self.chunk_overlap}) must be smaller than CHUNK_SIZE ({self.chunk_size})."
            )

    @staticmethod
    def generate_chunk_id(source: str, chunk_index: int, text_content: str) -> str:
        """
        Generate a deterministic chunk ID based on source filename, chunk index, and content hash.
        """
        content_hash = hashlib.sha256(text_content.encode("utf-8")).hexdigest()[:16]
        raw_str = f"{source}::chunk_{chunk_index}::{content_hash}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def _split_text(self, text: str) -> List[str]:
        """
        Splits text into chunks prioritizing double newlines (paragraphs), single newlines, and space boundaries.
        """
        if len(text) <= self.chunk_size:
            return [text]

        # Primary separators in priority order
        separators = ["\n\n", "\n# ", "\n## ", "\n### ", "\n", ". ", " "]
        
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size

            if end >= text_length:
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            # Find best split point near end boundary
            split_pos = -1
            candidate_text = text[start:end]

            for sep in separators:
                pos = candidate_text.rfind(sep)
                if pos != -1 and pos > self.chunk_size // 4:  # Ensure chunk isn't tiny
                    split_pos = start + pos + len(sep)
                    break

            if split_pos == -1 or split_pos <= start:
                split_pos = end  # Hard split if no separator found

            chunk = text[start:split_pos].strip()
            if chunk:
                chunks.append(chunk)

            # Advance start by split_pos minus overlap
            start = max(start + 1, split_pos - self.chunk_overlap)

        return chunks

    def chunk_document(self, document: Document) -> List[DocumentChunk]:
        """
        Convert a Document into a list of DocumentChunk objects with metadata and deterministic IDs.
        """
        if not document.text or not document.text.strip():
            return []

        raw_chunks = self._split_text(document.text.strip())
        doc_meta_dict = document.metadata.model_dump()
        chunks = []

        for idx, chunk_text in enumerate(raw_chunks):
            chunk_id = self.generate_chunk_id(
                source=document.metadata.source,
                chunk_index=idx,
                text_content=chunk_text
            )

            chunk_meta = dict(doc_meta_dict)
            chunk_meta["chunk_index"] = idx
            chunk_meta["total_chunks"] = len(raw_chunks)

            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    metadata=chunk_meta
                )
            )

        logger.debug(
            f"Chunked document '{document.metadata.source}' into {len(chunks)} chunks "
            f"(chunk_size={self.chunk_size}, overlap={self.chunk_overlap})."
        )
        return chunks

    def chunk_documents(self, documents: List[Document]) -> List[DocumentChunk]:
        """
        Chunk a list of Document objects.
        """
        all_chunks = []
        for doc in documents:
            all_chunks.extend(self.chunk_document(doc))
        logger.info(f"Chunked {len(documents)} documents into {len(all_chunks)} total chunks.")
        return all_chunks
