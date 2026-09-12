from typing import Any, Dict, List
from botocore.exceptions import ClientError
from app.aws.client import get_ec2_client
from app.core.logging import logger


def get_vpc_resources(region: str | None = None) -> Dict[str, List[Dict[str, Any]]]:
    """Collects read-only VPC, Subnet, Route Table, IGW, and NAT Gateway information."""
    logger.info("Starting read-only VPC infrastructure collection")
    client = get_ec2_client(region)

    result: Dict[str, List[Dict[str, Any]]] = {
        "vpcs": [],
        "subnets": [],
        "route_tables": [],
        "internet_gateways": [],
        "nat_gateways": [],
    }

    try:
        # 1. VPCs
        vpcs_resp = client.describe_vpcs()
        for vpc in vpcs_resp.get("Vpcs", []):
            tags = {t.get("Key"): t.get("Value") for t in vpc.get("Tags", []) if t.get("Key")}
            result["vpcs"].append({
                "vpc_id": vpc.get("VpcId"),
                "cidr_block": vpc.get("CidrBlock"),
                "is_default": vpc.get("IsDefault", False),
                "state": vpc.get("State"),
                "tags": tags,
            })

        # 2. Subnets
        subnets_resp = client.describe_subnets()
        for s in subnets_resp.get("Subnets", []):
            tags = {t.get("Key"): t.get("Value") for t in s.get("Tags", []) if t.get("Key")}
            result["subnets"].append({
                "subnet_id": s.get("SubnetId"),
                "vpc_id": s.get("VpcId"),
                "cidr_block": s.get("CidrBlock"),
                "availability_zone": s.get("AvailabilityZone"),
                "available_ip_address_count": s.get("AvailableIpAddressCount"),
                "map_public_ip_on_launch": s.get("MapPublicIpOnLaunch", False),
                "tags": tags,
            })

        # 3. Route Tables
        rt_resp = client.describe_route_tables()
        for rt in rt_resp.get("RouteTables", []):
            routes = [
                {
                    "destination_cidr_block": r.get("DestinationCidrBlock"),
                    "gateway_id": r.get("GatewayId"),
                    "instance_id": r.get("InstanceId"),
                    "nat_gateway_id": r.get("NatGatewayId"),
                    "state": r.get("State"),
                }
                for r in rt.get("Routes", [])
            ]
            associations = [
                {
                    "subnet_id": a.get("SubnetId"),
                    "main": a.get("Main", False),
                }
                for a in rt.get("Associations", [])
            ]
            result["route_tables"].append({
                "route_table_id": rt.get("RouteTableId"),
                "vpc_id": rt.get("VpcId"),
                "routes": routes,
                "associations": associations,
            })

        # 4. Internet Gateways
        igw_resp = client.describe_internet_gateways()
        for igw in igw_resp.get("InternetGateways", []):
            attachments = [
                {
                    "vpc_id": a.get("VpcId"),
                    "state": a.get("State"),
                }
                for a in igw.get("Attachments", [])
            ]
            result["internet_gateways"].append({
                "internet_gateway_id": igw.get("InternetGatewayId"),
                "attachments": attachments,
            })

        # 5. NAT Gateways
        nat_resp = client.describe_nat_gateways()
        for nat in nat_resp.get("NatGateways", []):
            result["nat_gateways"].append({
                "nat_gateway_id": nat.get("NatGatewayId"),
                "vpc_id": nat.get("VpcId"),
                "subnet_id": nat.get("SubnetId"),
                "state": nat.get("State"),
            })

        logger.info(f"VPC infrastructure collection completed: {len(result['vpcs'])} VPCs found")
        return result

    except ClientError as e:
        logger.error(f"AWS ClientError during VPC collection: {e}")
        raise RuntimeError(f"VPC API call failed: {e.response.get('Error', {}).get('Message', str(e))}") from e
