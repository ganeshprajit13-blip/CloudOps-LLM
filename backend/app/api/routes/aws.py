from typing import Optional
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, PartialCredentialsError
from fastapi import APIRouter, HTTPException, Query, status

from app.aws.cloudtrail import get_cloudtrail_events
from app.aws.cloudwatch import get_cloudwatch_metrics
from app.aws.ec2 import get_ec2_instances
from app.aws.load_balancer import get_load_balancers
from app.aws.security_groups import get_security_groups
from app.aws.ssm import get_windows_host_telemetry
from app.aws.vpc import get_vpc_resources
from app.core.config import settings
from app.schemas.aws import (
    CloudTrailResponseSchema,
    CloudWatchResponseSchema,
    EC2ResponseSchema,
    HostTelemetryResponseSchema,
    InfrastructureDataResponseSchema,
    LoadBalancerResponseSchema,
    SecurityGroupResponseSchema,
    VpcResponseSchema,
)
import os
from app.aws.sts import get_sts_identity
from app.services.aws_collector import collect_infrastructure_data


router = APIRouter(prefix="/aws", tags=["AWS Infrastructure"])


def _handle_aws_exception(e: Exception, service_name: str):
    """Formats AWS exception cleanly without exposing sensitive system internal details or secrets."""
    err_str = str(e).lower()
    if isinstance(e, (NoCredentialsError, PartialCredentialsError)) or any(
        term in err_str for term in ["credentials", "authfailure", "invalidclienttokenid", "unrecognizedclientexception"]
    ):
        missing = []
        if not settings.AWS_ACCESS_KEY_ID and not os.environ.get("AWS_ACCESS_KEY_ID"):
            missing.append("AWS_ACCESS_KEY_ID")
        if not settings.AWS_SECRET_ACCESS_KEY and not os.environ.get("AWS_SECRET_ACCESS_KEY"):
            missing.append("AWS_SECRET_ACCESS_KEY")

        if missing:
            detail_msg = f"AWS credentials are missing or incomplete. Configuration variable(s) missing: {', '.join(missing)} in backend/.env or environment variables."
        else:
            detail_msg = "AWS authentication failed. Provided credentials are invalid or expired."

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail_msg,
        )

    if any(term in err_str for term in ["unauthorizedoperation", "accessdenied", "accessdeniedexception", "not authorized to perform"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"AWS authorization failed for {service_name}: The IAM identity lacks required read permissions (e.g. ReadOnlyAccess policy in AWS IAM). Details: {str(e)}",
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{service_name} telemetry collection failed: {str(e)}",
    )


@router.get(
    "/sts",
    summary="Get AWS STS Caller Identity Diagnostic",
    description="Returns safe AWS authentication status, Account ID, and ARN without exposing secrets.",
)
async def read_sts_identity(region: Optional[str] = Query(None, description="AWS Region")):
    try:
        r = region or settings.AWS_REGION
        identity_data = get_sts_identity(r)
        return identity_data
    except Exception as e:
        _handle_aws_exception(e, "STS")


@router.get(
    "/ec2",
    response_model=EC2ResponseSchema,
    summary="Get EC2 Instances Telemetry",
    description="Returns read-only EC2 instance state, IPs, types, subnets, and tags.",
)
async def read_ec2_instances(region: Optional[str] = Query(None, description="AWS Region")):
    try:
        r = region or settings.AWS_REGION
        instances = get_ec2_instances(r)
        return EC2ResponseSchema(region=r, instances=instances)
    except Exception as e:
        _handle_aws_exception(e, "EC2")


@router.get(
    "/cloudwatch",
    response_model=CloudWatchResponseSchema,
    summary="Get CloudWatch Metrics",
    description="Returns read-only metrics (CPUUtilization, NetworkIn/Out, Disk ops).",
)
async def read_cloudwatch_metrics(
    resource_id: Optional[str] = Query(None, description="EC2 Instance ID"),
    minutes: int = Query(15, ge=1, le=1440, description="Time window in minutes"),
    region: Optional[str] = Query(None, description="AWS Region"),
):
    try:
        r = region or settings.AWS_REGION
        metrics = get_cloudwatch_metrics(resource_id=resource_id, minutes=minutes, region=r)
        return CloudWatchResponseSchema(region=r, metrics=metrics)
    except Exception as e:
        _handle_aws_exception(e, "CloudWatch")


@router.get(
    "/cloudtrail",
    response_model=CloudTrailResponseSchema,
    summary="Get Recent CloudTrail Management Events",
    description="Returns recent read-only CloudTrail management events.",
)
async def read_cloudtrail_events(
    hours: int = Query(1, ge=1, le=24, description="Lookback window in hours"),
    region: Optional[str] = Query(None, description="AWS Region"),
):
    try:
        r = region or settings.AWS_REGION
        events = get_cloudtrail_events(hours=hours, region=r)
        return CloudTrailResponseSchema(region=r, events=events)
    except Exception as e:
        _handle_aws_exception(e, "CloudTrail")


@router.get(
    "/vpc",
    response_model=VpcResponseSchema,
    summary="Get VPC Infrastructure",
    description="Returns read-only VPCs, Subnets, Route Tables, IGWs, and NAT Gateways.",
)
async def read_vpc_infrastructure(region: Optional[str] = Query(None, description="AWS Region")):
    try:
        r = region or settings.AWS_REGION
        vpc_data = get_vpc_resources(r)
        return VpcResponseSchema(region=r, vpc=vpc_data)
    except Exception as e:
        _handle_aws_exception(e, "VPC")


@router.get(
    "/security-groups",
    response_model=SecurityGroupResponseSchema,
    summary="Get Security Groups & Rules",
    description="Returns read-only Security Groups and inbound/outbound permission rules.",
)
async def read_security_groups(region: Optional[str] = Query(None, description="AWS Region")):
    try:
        r = region or settings.AWS_REGION
        groups = get_security_groups(r)
        return SecurityGroupResponseSchema(region=r, security_groups=groups)
    except Exception as e:
        _handle_aws_exception(e, "Security Groups")


@router.get(
    "/load-balancers",
    response_model=LoadBalancerResponseSchema,
    summary="Get Application Load Balancers",
    description="Returns read-only ALBs, Target Groups, and Target Health states.",
)
async def read_load_balancers(region: Optional[str] = Query(None, description="AWS Region")):
    try:
        r = region or settings.AWS_REGION
        lbs = get_load_balancers(r)
        return LoadBalancerResponseSchema(region=r, load_balancers=lbs)
    except Exception as e:
        _handle_aws_exception(e, "Load Balancers")


@router.get(
    "/host-telemetry",
    response_model=HostTelemetryResponseSchema,
    summary="Get Windows EC2 Host-Level Telemetry",
    description="Returns read-only Windows services status, listening ports, and host health via SSM.",
)
async def read_host_telemetry(
    instance_id: Optional[str] = Query(None, description="EC2 Instance ID"),
    region: Optional[str] = Query(None, description="AWS Region"),
):
    try:
        r = region or settings.AWS_REGION
        instance_ids = [instance_id] if instance_id else None
        telemetry = get_windows_host_telemetry(instance_ids=instance_ids, region=r)
        return HostTelemetryResponseSchema(region=r, host_telemetry=telemetry)
    except Exception as e:
        _handle_aws_exception(e, "Host Telemetry")


@router.get(
    "/infrastructure",
    response_model=InfrastructureDataResponseSchema,
    summary="Get Aggregated Infrastructure Telemetry",
    description="Returns consolidated read-only telemetry across all AWS services.",
)
async def read_aggregated_infrastructure(region: Optional[str] = Query(None, description="AWS Region")):
    try:
        r = region or settings.AWS_REGION
        data = collect_infrastructure_data(r)
        return InfrastructureDataResponseSchema(**data)
    except Exception as e:
        _handle_aws_exception(e, "Infrastructure")


