from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings
from app.schemas.cloud_context import NormalizedCloudContextSchema, SignalSchema
from app.services.aws_collector import collect_infrastructure_data
from app.services.preprocessing import extract_signals, preprocess_cloud_context

router = APIRouter(prefix="/cloud", tags=["Cloud Context & Signals"])


@router.get(
    "/resources",
    summary="Get Available Cloud Resources for Selection",
    description="Returns available EC2 instances and cloud resources to populate resource selectors.",
)
async def get_cloud_resources(
    region: Optional[str] = Query(None, description="AWS Region")
) -> Dict[str, Any]:
    try:
        r = region or settings.AWS_REGION
        from app.aws.ec2 import get_ec2_instances
        instances = get_ec2_instances(r)
        resource_items = []
        for inst in instances:
            inst_id = inst.get("instance_id")
            inst_name = inst.get("tags", {}).get("Name") or inst_id
            resource_items.append({
                "resource_id": inst_id,
                "name": inst_name,
                "type": "ec2",
                "status": inst.get("state", "unknown"),
                "instance_type": inst.get("instance_type", "t3.micro"),
                "vpc_id": inst.get("vpc_id"),
                "subnet_id": inst.get("subnet_id"),
                "display_label": f"{inst_name} — {inst_id}"
            })
        return {
            "region": r,
            "resources": resource_items,
            "ec2": instances
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cloud resources: {str(e)}",
        )


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
        raw_data = collect_infrastructure_data(r, resource_id=resource_id)
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
        raw_data = collect_infrastructure_data(r, resource_id=resource_id)
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

