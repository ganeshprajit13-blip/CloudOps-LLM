import logging
from functools import lru_cache
from fastapi import APIRouter, HTTPException, status, Depends

from app.schemas.analysis import AnalysisRequest, DiagnosisSchema
from app.services.cloudops_analyzer import CloudOpsAnalyzer

logger = logging.getLogger("cloudops.api.routes.analysis")

router = APIRouter(tags=["Analysis"])

@lru_cache(maxsize=1)
def get_analyzer_service() -> CloudOpsAnalyzer:
    """Dependency provider for singleton CloudOpsAnalyzer service."""
    return CloudOpsAnalyzer()

@router.post(
    "/analyze",
    response_model=DiagnosisSchema,
    status_code=status.HTTP_200_OK,
    summary="CloudOps LLM Infrastructure Diagnosis",
    description=(
        "Analyzes a cloud infrastructure troubleshooting question by integrating live read-only AWS context, "
        "ChromaDB RAG knowledge retrieval, and adapted Qwen2.5-3B-Instruct reasoning into a validated diagnosis."
    ),
    responses={
        200: {
            "description": "Successful CloudOps diagnosis",
            "content": {
                "application/json": {
                    "example": {
                        "problem": "Website is unreachable over HTTPS.",
                        "probable_root_cause": "Inbound TCP port 443 rule missing from Security Group sg-012345.",
                        "evidence": [
                            "EC2 instance state is running.",
                            "CPU utilization is normal (35%).",
                            "Security Group sg-012345 lacks TCP 443 inbound rule."
                        ],
                        "impact": "External HTTPS client connections time out.",
                        "recommendation": "Review Security Group sg-012345 rules and authorize inbound TCP port 443.",
                        "confidence": 0.91
                    }
                }
            }
        },
        400: {"description": "Invalid request (e.g. empty question)"},
        422: {"description": "Pydantic validation error"},
        503: {"description": "CloudOps LLM model service unavailable"},
        500: {"description": "Internal server error"}
    }
)
async def analyze_infrastructure(
    request: AnalysisRequest,
    analyzer: CloudOpsAnalyzer = Depends(get_analyzer_service)
) -> DiagnosisSchema:
    """
    POST /api/analyze endpoint executing the CloudOps Intelligence Engine.
    """
    logger.info(f"Received POST /api/analyze request. Question length: {len(request.question)}")

    if not request.question or not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_REQUEST", "message": "The 'question' field cannot be empty or whitespace."}
        )

    try:
        import anyio
        response = await anyio.to_thread.run_sync(
            analyzer.analyze,
            request.question,
            request.cloud_context,
            request.resource_id,
            request.collect_live_data
        )

        if response.error == "EMPTY_QUERY":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_REQUEST", "message": "Question string cannot be empty."}
            )

        return response.diagnosis

    except RuntimeError as rerr:
        logger.error(f"AI Model Service unavailable during analysis: {rerr}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "MODEL_UNAVAILABLE", "message": f"CloudOps LLM inference is currently unavailable: {str(rerr)}"}
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error during /api/analyze execution: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ANALYSIS_FAILED", "message": "Unable to complete cloud analysis due to an internal server error."}
        )
