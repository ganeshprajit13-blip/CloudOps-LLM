from typing import Any, Dict, List
from botocore.exceptions import ClientError
from app.aws.client import get_ec2_client
from app.core.logging import logger


def _parse_ip_permissions(permissions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Helper to format Inbound / Outbound security group rules."""
    parsed_rules: List[Dict[str, Any]] = []
    for perm in permissions:
        protocol = perm.get("IpProtocol")
        from_port = perm.get("FromPort")
        to_port = perm.get("ToPort")

        sources: List[str] = []
        for ip_range in perm.get("IpRanges", []):
            if ip_range.get("CidrIp"):
                sources.append(ip_range["CidrIp"])

        for ipv6_range in perm.get("Ipv6Ranges", []):
            if ipv6_range.get("CidrIpv6"):
                sources.append(ipv6_range["CidrIpv6"])

        for group_pair in perm.get("UserIdGroupPairs", []):
            if group_pair.get("GroupId"):
                sources.append(group_pair["GroupId"])

        parsed_rules.append({
            "protocol": protocol,
            "from_port": from_port,
            "to_port": to_port,
            "sources": sources,
        })
    return parsed_rules


def get_security_groups(region: str | None = None) -> List[Dict[str, Any]]:
    """Collects read-only Security Groups and their inbound/outbound rules."""
    logger.info("Starting read-only Security Groups collection")
    client = get_ec2_client(region)
    security_groups: List[Dict[str, Any]] = []

    try:
        paginator = client.get_paginator("describe_security_groups")
        for page in paginator.paginate():
            for sg in page.get("SecurityGroups", []):
                inbound_rules = _parse_ip_permissions(sg.get("IpPermissions", []))
                outbound_rules = _parse_ip_permissions(sg.get("IpPermissionsEgress", []))

                security_groups.append({
                    "group_id": sg.get("GroupId"),
                    "name": sg.get("GroupName"),
                    "description": sg.get("Description"),
                    "vpc_id": sg.get("VpcId"),
                    "inbound_rules": inbound_rules,
                    "outbound_rules": outbound_rules,
                })

        logger.info(f"Security Groups collection completed: {len(security_groups)} groups found")
        return security_groups
    except ClientError as e:
        logger.error(f"AWS ClientError during Security Groups collection: {e}")
        raise RuntimeError(f"Security Groups API call failed: {e.response.get('Error', {}).get('Message', str(e))}") from e
