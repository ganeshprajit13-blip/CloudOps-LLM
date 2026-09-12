import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class RAGConfig:
    def __init__(self):
        self.BASE_DIR: Path = BASE_DIR
        self.EMBEDDING_MODEL: str = os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        
        persist_dir = os.getenv("CHROMA_PERSIST_DIRECTORY", "storage/chroma")
        if not os.path.isabs(persist_dir):
            self.CHROMA_PERSIST_DIRECTORY: str = str(BASE_DIR / persist_dir)
        else:
            self.CHROMA_PERSIST_DIRECTORY: str = persist_dir
            
        self.CHROMA_COLLECTION_NAME: str = os.getenv(
            "CHROMA_COLLECTION_NAME", "cloudops_knowledge"
        )
        self.CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
        self.CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "120"))
        self.TOP_K: int = int(os.getenv("TOP_K", "5"))
        self.RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.0"))

    def __repr__(self) -> str:
        return (
            f"<RAGConfig model={self.EMBEDDING_MODEL} "
            f"persist_dir={self.CHROMA_PERSIST_DIRECTORY} "
            f"collection={self.CHROMA_COLLECTION_NAME} "
            f"chunk_size={self.CHUNK_SIZE} overlap={self.CHUNK_OVERLAP} "
            f"top_k={self.TOP_K} min_score={self.RAG_MIN_SCORE}>"
        )

rag_config = RAGConfig()
