import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from rag.schemas import Document, DocumentMetadata

logger = logging.getLogger("cloudops.rag.document_loader")

# Exclude security-sensitive and internal file patterns
EXCLUDED_PATTERNS = {
    ".env", ".env.local", ".env.example", ".git", "__pycache__",
    "credentials", "id_rsa", "id_ed25519", "secret", "private_key",
    "storage", "processed"
}

KNOWN_SERVICES = {
    "ec2": ["ec2", "instance"],
    "vpc": ["vpc", "subnet", "route", "nat", "igw", "internet_gateway"],
    "security_group": ["security_group", "sg", "firewall", "port"],
    "alb": ["alb", "load_balancer", "target_group", "health_check"],
    "cloudwatch": ["cloudwatch", "metric", "alarm", "log"],
    "cloudtrail": ["cloudtrail", "audit", "event"],
    "iam": ["iam", "role", "policy", "permission", "access"],
    "nat_gateway": ["nat_gateway", "nat"],
    "route_table": ["route_table", "routes"]
}

class DocumentLoader:
    """
    Loads and normalizes knowledge documents from files (.txt, .md, .json, .jsonl).
    Safely ignores sensitive files, binaries, and invalid content.
    """

    def is_excluded(self, path: Path) -> bool:
        """Check if file or directory should be ignored."""
        parts = path.parts
        for part in parts:
            if part in EXCLUDED_PATTERNS or part.startswith("."):
                return True
            for pattern in EXCLUDED_PATTERNS:
                if pattern in part.lower() and not part.endswith((".md", ".txt", ".json", ".jsonl")):
                    return True
        return False

    def infer_service(self, filename: str, content: str = "") -> str:
        """Infer AWS service from filename or text content."""
        lower_name = filename.lower()
        lower_content = content.lower()[:500]

        for service, keywords in KNOWN_SERVICES.items():
            for kw in keywords:
                if kw in lower_name or kw in lower_content:
                    return service
        return "general"

    def infer_document_type(self, path: Path) -> str:
        """Infer document type based on path or directory structure."""
        parent = path.parent.name.lower()
        if "runbook" in parent:
            return "runbook"
        elif "incident" in parent:
            return "incident"
        elif "postmortem" in parent:
            return "postmortem"
        elif "aws" in parent or "doc" in parent:
            return "documentation"
        return "troubleshooting"

    def load_file(self, file_path: Path) -> List[Document]:
        """Load a single file and return normalized Document objects."""
        if self.is_excluded(file_path):
            logger.debug(f"Skipping excluded file: {file_path}")
            return []

        suffix = file_path.suffix.lower()
        if suffix not in [".txt", ".md", ".json", ".jsonl"]:
            logger.debug(f"Unsupported file format '{suffix}': {file_path}")
            return []

        try:
            stat = file_path.stat()
            modified_time = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception:
            modified_time = datetime.utcnow().isoformat()

        category = file_path.parent.name.lower()
        document_type = self.infer_document_type(file_path)

        if suffix in [".txt", ".md"]:
            return self._load_text_or_markdown(file_path, category, document_type, modified_time)
        elif suffix == ".json":
            return self._load_json(file_path, category, document_type, modified_time)
        elif suffix == ".jsonl":
            return self._load_jsonl(file_path, category, document_type, modified_time)

        return []

    def _load_text_or_markdown(
        self, path: Path, category: str, document_type: str, modified_time: str
    ) -> List[Document]:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().strip()
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return []

        if not content:
            logger.warning(f"File {path} is empty, skipping.")
            return []

        # Extract title from markdown header (# Title) if present
        title = path.stem.replace("_", " ").replace("-", " ").title()
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("# "):
                title = line_str[2:].strip()
                break

        service = self.infer_service(path.name, content)

        meta = DocumentMetadata(
            source=path.name,
            title=title,
            category=category,
            service=service,
            document_type=document_type,
            version="1.0",
            created_at=modified_time,
            updated_at=modified_time
        )
        return [Document(text=content, metadata=meta)]

    def _load_json(
        self, path: Path, category: str, document_type: str, modified_time: str
    ) -> List[Document]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error parsing JSON file {path}: {e}")
            return []

        documents = []
        items = data if isinstance(data, list) else [data]

        for idx, item in enumerate(items):
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("description") or json.dumps(item, indent=2)
                title = item.get("title") or item.get("name") or f"{path.stem}_{idx+1}"
                service = item.get("service") or self.infer_service(path.name, text)
                doc_type = item.get("document_type") or document_type
                cat = item.get("category") or category
            else:
                text = str(item)
                title = f"{path.stem}_{idx+1}"
                service = self.infer_service(path.name, text)
                doc_type = document_type
                cat = category

            if text and text.strip():
                meta = DocumentMetadata(
                    source=path.name,
                    title=title,
                    category=cat,
                    service=service,
                    document_type=doc_type,
                    version="1.0",
                    created_at=modified_time,
                    updated_at=modified_time
                )
                documents.append(Document(text=text.strip(), metadata=meta))

        return documents

    def _load_jsonl(
        self, path: Path, category: str, document_type: str, modified_time: str
    ) -> List[Document]:
        documents = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        item = json.loads(line_str)
                        if isinstance(item, dict):
                            text = item.get("text") or item.get("content") or item.get("description") or json.dumps(item)
                            title = item.get("title") or f"{path.stem}_line_{idx+1}"
                            service = item.get("service") or self.infer_service(path.name, text)
                            doc_type = item.get("document_type") or document_type
                            cat = item.get("category") or category
                        else:
                            text = str(item)
                            title = f"{path.stem}_line_{idx+1}"
                            service = self.infer_service(path.name, text)
                            doc_type = document_type
                            cat = category

                        if text and text.strip():
                            meta = DocumentMetadata(
                                source=path.name,
                                title=title,
                                category=cat,
                                service=service,
                                document_type=doc_type,
                                version="1.0",
                                created_at=modified_time,
                                updated_at=modified_time
                            )
                            documents.append(Document(text=text.strip(), metadata=meta))
                    except json.JSONDecodeError as err:
                        logger.warning(f"Invalid JSON line {idx+1} in {path}: {err}")
        except Exception as e:
            logger.error(f"Error reading JSONL file {path}: {e}")

        return documents

    def load_directory(self, directory_path: Path) -> List[Document]:
        """Recursively discover and load all supported documents in directory."""
        if not directory_path.exists() or not directory_path.is_dir():
            logger.error(f"Knowledge directory does not exist or is not a directory: {directory_path}")
            return []

        all_documents = []
        for root, dirs, files in os.walk(directory_path):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if not self.is_excluded(Path(root) / d)]
            
            for file in files:
                file_path = Path(root) / file
                docs = self.load_file(file_path)
                all_documents.extend(docs)

        logger.info(f"Loaded {len(all_documents)} documents from directory: {directory_path}")
        return all_documents
