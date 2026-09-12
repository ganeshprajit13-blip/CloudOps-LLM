from typing import Any, Dict, List
from botocore.exceptions import ClientError
from app.aws.client import get_elbv2_client
from app.core.logging import logger


def get_load_balancers(region: str | None = None) -> List[Dict[str, Any]]:
    """Collects read-only Application Load Balancers, Target Groups, and Target Health."""
    logger.info("Starting read-only ELBv2 Load Balancers collection")
    client = get_elbv2_client(region)
    load_balancers: List[Dict[str, Any]] = []

    try:
        lb_paginator = client.get_paginator("describe_load_balancers")
        for lb_page in lb_paginator.paginate():
            for lb in lb_page.get("LoadBalancers", []):
                lb_arn = lb.get("LoadBalancerArn")
                lb_name = lb.get("LoadBalancerName")

                # Fetch target groups for this load balancer
                target_groups: List[Dict[str, Any]] = []
                try:
                    tg_paginator = client.get_paginator("describe_target_groups")
                    for tg_page in tg_paginator.paginate(LoadBalancerArn=lb_arn):
                        for tg in tg_page.get("TargetGroups", []):
                            tg_arn = tg.get("TargetGroupArn")

                            # Fetch target health for each target group
                            target_health_list: List[Dict[str, Any]] = []
                            if tg_arn:
                                try:
                                    health_resp = client.describe_target_health(TargetGroupArn=tg_arn)
                                    for th in health_resp.get("TargetHealthDescriptions", []):
                                        target = th.get("Target", {})
                                        health = th.get("TargetHealth", {})
                                        target_health_list.append({
                                            "target_id": target.get("Id"),
                                            "port": target.get("Port"),
                                            "health_state": health.get("State"),
                                            "reason": health.get("Reason"),
                                            "description": health.get("Description"),
                                        })
                                except ClientError as he:
                                    logger.warning(f"Could not fetch target health for {tg_arn}: {he}")

                            target_groups.append({
                                "target_group_arn": tg_arn,
                                "target_group_name": tg.get("TargetGroupName"),
                                "protocol": tg.get("Protocol"),
                                "port": tg.get("Port"),
                                "vpc_id": tg.get("VpcId"),
                                "health_check_protocol": tg.get("HealthCheckProtocol"),
                                "health_check_port": tg.get("HealthCheckPort"),
                                "health_check_path": tg.get("HealthCheckPath"),
                                "target_health": target_health_list,
                            })
                except ClientError as tge:
                    logger.warning(f"Could not fetch target groups for load balancer {lb_name}: {tge}")

                azs = [az.get("ZoneName") for az in lb.get("AvailabilityZones", []) if az.get("ZoneName")]

                load_balancers.append({
                    "load_balancer_arn": lb_arn,
                    "name": lb_name,
                    "type": lb.get("Type"),
                    "state": lb.get("State", {}).get("Code"),
                    "dns_name": lb.get("DNSName"),
                    "vpc_id": lb.get("VpcId"),
                    "availability_zones": azs,
                    "target_groups": target_groups,
                })

        logger.info(f"Load Balancer collection completed: {len(load_balancers)} load balancers found")
        return load_balancers
    except ClientError as e:
        logger.error(f"AWS ClientError during ELBv2 collection: {e}")
        raise RuntimeError(f"Load Balancer API call failed: {e.response.get('Error', {}).get('Message', str(e))}") from e
