from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    message: str = Field(
        default="CloudOps LLM backend is running",
        description="Welcome or status message",
    )
    version: str = Field(
        default="0.1.0",
        description="Backend API version",
    )


class HealthResponse(BaseModel):
    status: str = Field(
        default="healthy",
        description="Current health status of the service",
    )
    service: str = Field(
        default="cloudops-backend",
        description="Service name identifier",
    )
    version: str = Field(
        default="0.1.0",
        description="Service version",
    )
