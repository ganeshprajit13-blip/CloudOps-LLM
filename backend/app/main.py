import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

if str(BACKEND_DIR) in sys.path:
    sys.path.remove(str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from app.api.routes.analysis import router as analysis_router
from app.api.routes.aws import router as aws_router
from app.api.routes.cloud_context import router as cloud_context_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import logger
from app.schemas.health import RootResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    import os
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")
    if os.getenv("EAGER_MODEL_LOAD", "0") == "1" and os.getenv("DRY_RUN", "0") != "1":
        try:
            from model.model_loader import ModelSingletonManager
            logger.info("Pre-warming ModelSingletonManager during application startup...")
            ModelSingletonManager.get_instance()
        except Exception as warm_err:
            logger.warning(f"Startup model warm-up skipped or encountered non-fatal error: {warm_err}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered cloud infrastructure troubleshooting backend",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include Routers
app.include_router(health_router)
app.include_router(aws_router, prefix=settings.API_PREFIX)
app.include_router(cloud_context_router, prefix=settings.API_PREFIX)
app.include_router(analysis_router, prefix=settings.API_PREFIX)

@app.get(
    "/",
    response_model=RootResponse,
    tags=["Root"],
    summary="Backend Status",
    description="Returns backend running message and version.",
)
async def root() -> RootResponse:
    return RootResponse(
        message="CloudOps LLM backend is running",
        version=settings.APP_VERSION,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Global HTTP exception handler."""
    logger.warning(f"HTTP error {exc.status_code} on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global unhandled exception handler to avoid stack trace exposure in non-debug mode."""
    logger.error(f"Unhandled error on {request.url.path}: {str(exc)}", exc_info=settings.DEBUG)
    detail = str(exc) if settings.DEBUG else "An internal server error occurred."
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
    )
