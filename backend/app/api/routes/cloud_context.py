from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings
from app.schemas.cloud_context import NormalizedCloudContextSchema, SignalSchema
from app.services.aws_collector import collect_infrastructure_data
from app.services.preprocessing import extract_signals, preprocess_cloud_context

router = APIRouter(prefix="/cloud", tags=["Cloud Context & Signals"])


@router.get(
    "/context",
    response_model=NormalizedCloudContextSchema,
    summary="Get Preprocessed CloudOps Context",
    description="Collects read-only AWS data, normalizes it, extracts signals, and returns structured CloudOps context.",
)
async def get_cloudops_context(
    region: Optional[str] = Query(None, description="AWS Region"),
    resource_id: Optional[str] = Query(None, description="Resource ID to filter context for")
):
    try:
        r = region or settings.AWS_REGION
        raw_data = collect_infrastructure_data(r)
        context_data = preprocess_cloud_context(raw_data)
        if resource_id:
            from app.services.context_builder import ContextBuilder
            context_data = ContextBuilder().filter_context_by_resource(context_data, resource_id)
        return NormalizedCloudContextSchema(**context_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate CloudOps context: {str(e)}",
        )


@router.get(
    "/signals",
    response_model=List[SignalSchema],
    summary="Get Extracted Observable Signals",
    description="Collects telemetry and returns list of extracted observable signals.",
)
async def get_cloudops_signals(
    region: Optional[str] = Query(None, description="AWS Region"),
    resource_id: Optional[str] = Query(None, description="Resource ID to filter signals for")
):
    try:
        r = region or settings.AWS_REGION
        raw_data = collect_infrastructure_data(r)
        context_data = preprocess_cloud_context(raw_data)
        if resource_id:
            from app.services.context_builder import ContextBuilder
            context_data = ContextBuilder().filter_context_by_resource(context_data, resource_id)
        signals = context_data.get("signals", [])
        return [SignalSchema(**s) for s in signals]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract signals: {str(e)}",
        )
