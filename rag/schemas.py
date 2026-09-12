from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = Field(..., description="Filename or identifier of the source document")
    title: str = Field(..., description="Document title")
    category: str = Field(default="cloudops", description="High-level category, e.g. aws, runbook, incident")
    service: str = Field(default="general", description="AWS service, e.g. ec2, vpc, alb, cloudwatch, cloudtrail, iam")
    document_type: str = Field(default="documentation", description="Type: documentation, runbook, incident, postmortem, troubleshooting")
    version: Optional[str] = Field(default="1.0", description="Document version")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last updated timestamp")
    chunk_index: Optional[int] = Field(default=None, description="Index of chunk within parent document")


class Document(BaseModel):
    text: str = Field(..., description="Raw or normalized text content of the document")
    metadata: DocumentMetadata = Field(..., description="Structured metadata associated with document")


class DocumentChunk(BaseModel):
    chunk_id: str = Field(..., description="Deterministic unique identifier for the chunk")
    text: str = Field(..., description="Text content of the chunk")
    metadata: Dict[str, Any] = Field(..., description="Metadata dict including chunk_index and parent metadata")


class RetrievalResult(BaseModel):
    text: str = Field(..., description="Retrieved chunk text")
    score: float = Field(..., description="Normalized similarity score (higher is more relevant, range 0.0 to 1.0)")
    distance: Optional[float] = Field(default=None, description="Raw distance score from vector database")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata associated with the retrieved chunk")


class RetrievalResponse(BaseModel):
    query: str = Field(..., description="Original user query")
    results: List[RetrievalResult] = Field(default_factory=list, description="Ranked list of relevant knowledge chunks")
    message: Optional[str] = Field(default=None, description="Informational message or empty result notification")


class IngestionStats(BaseModel):
    documents_discovered: int = 0
    documents_processed: int = 0
    chunks_created: int = 0
    chunks_skipped: int = 0
    chunks_updated: int = 0
    chunks_stored: int = 0
