from datetime import datetime, timezone
from typing import Any, Dict
from app.aws.cloudtrail import get_cloudtrail_events
from app.aws.cloudwatch import get_cloudwatch_metrics
from app.aws.ec2 import get_ec2_instances
from app.aws.load_balancer import get_load_balancers
from app.aws.security_groups import get_security_groups
from app.aws.ssm import get_windows_host_telemetry
from app.aws.vpc import get_vpc_resources
from app.core.config import settings
from app.core.logging import logger


def collect_infrastructure_data(region: str | None = None) -> Dict[str, Any]:
    """Central AWS collector service orchestrating read-only telemetry across all services."""
    target_region = region or settings.AWS_REGION
    timestamp_str = datetime.now(timezone.utc).isoformat()
    logger.info(f"Starting full read-only AWS infrastructure collection for region: {target_region}")

    # EC2 Collection
    try:
        ec2_data = get_ec2_instances(target_region)
    except Exception as e:
        logger.error(f"EC2 collection failed: {e}")
        ec2_data = []

    # Windows / Host-Level SSM Telemetry Collection
    try:
        instance_ids = [inst.get("instance_id") for inst in ec2_data if isinstance(inst, dict) and inst.get("instance_id")]
        host_telemetry_data = get_windows_host_telemetry(instance_ids=instance_ids, region=target_region)
    except Exception as e:
        logger.error(f"Host SSM telemetry collection failed: {e}")
        host_telemetry_data = []

    # CloudWatch Collection
    try:
        cloudwatch_data = get_cloudwatch_metrics(instance_ids=instance_ids, region=target_region)
    except Exception as e:
        logger.error(f"CloudWatch collection failed: {e}")
        cloudwatch_data = []

    # CloudTrail Collection
    try:
        cloudtrail_data = get_cloudtrail_events(region=target_region)
    except Exception as e:
        logger.error(f"CloudTrail collection failed: {e}")
        cloudtrail_data = []

    # VPC Collection
    try:
        vpc_data = get_vpc_resources(target_region)
    except Exception as e:
        logger.error(f"VPC collection failed: {e}")
        vpc_data = {
            "vpcs": [],
            "subnets": [],
            "route_tables": [],
            "internet_gateways": [],
            "nat_gateways": [],
        }

    # Security Groups Collection
    try:
        sg_data = get_security_groups(target_region)
    except Exception as e:
        logger.error(f"Security Groups collection failed: {e}")
        sg_data = []

    # Load Balancers Collection
    try:
        alb_data = get_load_balancers(target_region)
    except Exception as e:
        logger.error(f"Load Balancer collection failed: {e}")
        alb_data = []

    logger.info("Full AWS infrastructure data collection completed")

    return {
        "region": target_region,
        "timestamp": timestamp_str,
        "ec2": ec2_data,
        "host_telemetry": host_telemetry_data,
        "cloudwatch": cloudwatch_data,
        "cloudtrail": cloudtrail_data,
        "vpc": vpc_data,
        "security_groups": sg_data,
        "load_balancers": alb_data,
    }

