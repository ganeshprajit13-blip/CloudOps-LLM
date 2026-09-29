import time
import concurrent.futures
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


def collect_infrastructure_data(region: str | None = None, resource_id: str | None = None) -> Dict[str, Any]:
    """Central AWS collector service orchestrating read-only telemetry in parallel across all services."""
    target_region = region or settings.AWS_REGION
    timestamp_str = datetime.now(timezone.utc).isoformat()
    t_start = time.time()
    logger.info(f"Starting parallel read-only AWS infrastructure collection for region: {target_region} (resource_id={resource_id})")

    # 1. EC2 Collection
    t_ec2_start = time.time()
    try:
        ec2_data = get_ec2_instances(target_region)
    except Exception as e:
        logger.error(f"EC2 collection failed: {e}")
        ec2_data = []
    t_ec2 = time.time() - t_ec2_start
    logger.info(f"[PERF] EC2 collection: {t_ec2:.2f} sec")

    # Determine target instance IDs for scoped collectors
    if resource_id and isinstance(resource_id, str) and resource_id.startswith("i-"):
        target_instance_ids = [resource_id]
    else:
        target_instance_ids = [inst.get("instance_id") for inst in ec2_data if isinstance(inst, dict) and inst.get("instance_id")]

    # 2. Parallel Collection of independent AWS telemetry calls
    t_ssm, t_cw, t_ct, t_vpc, t_sg, t_alb = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    host_telemetry_data = []
    cloudwatch_data = []
    cloudtrail_data = []
    vpc_data = {
        "vpcs": [],
        "subnets": [],
        "route_tables": [],
        "internet_gateways": [],
        "nat_gateways": [],
    }
    sg_data = []
    alb_data = []

    def fetch_ssm():
        nonlocal t_ssm
        t0 = time.time()
        try:
            res = get_windows_host_telemetry(instance_ids=target_instance_ids, region=target_region)
        except Exception as err:
            logger.error(f"Host SSM telemetry collection failed: {err}")
            res = []
        t_ssm = time.time() - t0
        return res

    def fetch_cw():
        nonlocal t_cw
        t0 = time.time()
        try:
            res = get_cloudwatch_metrics(instance_ids=target_instance_ids, region=target_region)
        except Exception as err:
            logger.error(f"CloudWatch collection failed: {err}")
            res = []
        t_cw = time.time() - t0
        return res

    def fetch_ct():
        nonlocal t_ct
        t0 = time.time()
        try:
            res = get_cloudtrail_events(region=target_region)
        except Exception as err:
            logger.error(f"CloudTrail collection failed: {err}")
            res = []
        t_ct = time.time() - t0
        return res

    def fetch_vpc():
        nonlocal t_vpc
        t0 = time.time()
        try:
            res = get_vpc_resources(target_region)
        except Exception as err:
            logger.error(f"VPC collection failed: {err}")
            res = {
                "vpcs": [],
                "subnets": [],
                "route_tables": [],
                "internet_gateways": [],
                "nat_gateways": [],
            }
        t_vpc = time.time() - t0
        return res

    def fetch_sg():
        nonlocal t_sg
        t0 = time.time()
        try:
            res = get_security_groups(target_region)
        except Exception as err:
            logger.error(f"Security Groups collection failed: {err}")
            res = []
        t_sg = time.time() - t0
        return res

    def fetch_alb():
        nonlocal t_alb
        t0 = time.time()
        try:
            res = get_load_balancers(target_region)
        except Exception as err:
            logger.error(f"Load Balancer collection failed: {err}")
            res = []
        t_alb = time.time() - t0
        return res

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        f_ssm = executor.submit(fetch_ssm)
        f_cw = executor.submit(fetch_cw)
        f_ct = executor.submit(fetch_ct)
        f_vpc = executor.submit(fetch_vpc)
        f_sg = executor.submit(fetch_sg)
        f_alb = executor.submit(fetch_alb)

        host_telemetry_data = f_ssm.result()
        cloudwatch_data = f_cw.result()
        cloudtrail_data = f_ct.result()
        vpc_data = f_vpc.result()
        sg_data = f_sg.result()
        alb_data = f_alb.result()

    t_aws_total = time.time() - t_start
    logger.info(
        f"[PERF] Parallel AWS Collection Completed in {t_aws_total:.2f} sec:\n"
        f"  - EC2: {t_ec2:.2f}s | SSM: {t_ssm:.2f}s | CloudWatch: {t_cw:.2f}s\n"
        f"  - CloudTrail: {t_ct:.2f}s | VPC: {t_vpc:.2f}s | SG: {t_sg:.2f}s | ALB: {t_alb:.2f}s"
    )

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
        "_perf_timings": {
            "ec2": t_ec2,
            "ssm": t_ssm,
            "cloudwatch": t_cw,
            "cloudtrail": t_ct,
            "vpc": t_vpc,
            "sg": t_sg,
            "alb": t_alb,
            "aws_total": t_aws_total
        }
    }


