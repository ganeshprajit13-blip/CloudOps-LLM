import logging
from fastapi import APIRouter, HTTPException, status
from app.schemas.support import SupportChatRequest, SupportChatResponse
from app.services.support_agent import ask_support_agent

logger = logging.getLogger("cloudops.api.routes.support")

router = APIRouter(tags=["Support Agent"])

@router.post(
    "/support-chat",
    response_model=SupportChatResponse,
    status_code=status.HTTP_200_OK,
    summary="CloudOps Support Agent Chatbot Endpoint",
    description="RAG-grounded technical assistance for CloudOps product usage, AWS cloud infrastructure, and AI/LLM architecture."
)
@router.post(
    "/support/chat",
    response_model=SupportChatResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False
)
async def chat_with_support_agent(request: SupportChatRequest) -> SupportChatResponse:
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_REQUEST", "message": "Message field cannot be empty."}
        )

    try:
        history_list = [msg.model_dump() for msg in request.history] if request.history else []
        result = ask_support_agent(request.message, history_list, rca_context=request.rca_context)
        return SupportChatResponse(
            answer=result.get("answer") or result.get("reply", "An error occurred generating the support response."),
            reply=result.get("reply") or result.get("answer", "An error occurred generating the support response."),
            sources=result.get("sources", []),
            provider=result.get("provider", "local_qlora"),
            fallback_used=result.get("fallback_used", False)
        )
    except Exception as exc:
        logger.error(f"Support Agent chat endpoint error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SUPPORT_CHAT_FAILED", "message": "The Support Agent encountered an error processing your request."}
        )
