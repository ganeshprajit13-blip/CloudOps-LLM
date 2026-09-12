from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    question: str = Field(..., min_length=1, max_length=1000, description="User infrastructure question or problem description")
    cloud_context: Optional[Dict[str, Any]] = Field(default=None, description="Optional pre-supplied AWS cloud context")
    resource_id: Optional[str] = Field(default=None, description="Optional target AWS resource ID (e.g. i-0123456789)")
    collect_live_data: bool = Field(default=True, description="Whether to collect live AWS telemetry via Boto3 collectors")


class DiagnosisSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    problem: str = Field(..., description="Summary of the reported issue")
    probable_root_cause: str = Field(..., description="Identified root cause")
    evidence: List[str] = Field(default_factory=list, description="List of supporting evidence items")
    impact: str = Field(..., description="Operational impact statement")
    recommendation: str = Field(..., description="Advisory corrective guidance")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")


class RetrievedKnowledgeItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = Field(..., description="Document source filename")
    title: str = Field(..., description="Document title")
    service: str = Field(..., description="AWS service category")
    score: float = Field(..., description="Normalized similarity score")
    text: str = Field(..., description="Retrieved chunk text content")


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    query: str = Field(..., description="Original user question")
    diagnosis: DiagnosisSchema = Field(..., description="Validated structured diagnosis")
    retrieved_knowledge: List[RetrievedKnowledgeItem] = Field(default_factory=list, description="Ranked RAG knowledge chunks used")
    cloud_signals: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted cloud anomaly signals")
    execution_time_seconds: Optional[float] = Field(default=None, description="Pipeline execution duration in seconds")
    error: Optional[str] = Field(default=None, description="Optional error status flag")
    message: Optional[str] = Field(default=None, description="Optional informational message")
