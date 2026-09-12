from fastapi import APIRouter
from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns operational status of the CloudOps LLM backend service.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="cloudops-backend",
        version=settings.APP_VERSION,
    )
