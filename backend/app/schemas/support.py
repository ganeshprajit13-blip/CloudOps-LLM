from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of speaker: 'user' or 'assistant'")
    content: str = Field(..., description="Message text content")

class SupportChatRequest(BaseModel):
    message: str = Field(..., description="User support inquiry or question")
    history: Optional[List[ChatMessage]] = Field(default=[], description="Recent conversation message history")
    rca_context: Optional[Dict[str, Any]] = Field(default=None, description="Optional RCA diagnosis context payload")

class KnowledgeSource(BaseModel):
    title: str = Field(..., description="Document or knowledge section title")
    category: str = Field(..., description="Knowledge domain category")
    relevance: float = Field(..., description="Normalized vector similarity score [0.0 - 1.0]")
    score: Optional[float] = Field(default=None, description="Alias for relevance score")

    def __init__(self, **data):
        if "score" in data and "relevance" not in data:
            data["relevance"] = data["score"]
        elif "relevance" in data and "score" not in data:
            data["score"] = data["relevance"]
        super().__init__(**data)

class SupportChatResponse(BaseModel):
    answer: str = Field(..., description="Grounded technical support response")
    reply: Optional[str] = Field(default=None, description="Alias for answer text")
    sources: List[KnowledgeSource] = Field(default=[], description="Retrieved support knowledge sources")
    provider: str = Field(default="local_qlora", description="Inference provider used: 'local_qlora', 'groq_fallback', 'local_guardrail', or 'local_fallback_failure'")
    fallback_used: bool = Field(default=False, description="Whether the fallback provider was invoked")

    def __init__(self, **data):
        if "reply" in data and "answer" not in data:
            data["answer"] = data["reply"]
        elif "answer" in data and "reply" not in data:
            data["reply"] = data["answer"]
        super().__init__(**data)
