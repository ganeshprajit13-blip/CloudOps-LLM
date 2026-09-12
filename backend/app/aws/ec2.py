from typing import Any, Dict, List
from botocore.exceptions import ClientError
from app.aws.client import get_ec2_client
from app.core.logging import logger


def get_ec2_instances(region: str | None = None) -> List[Dict[str, Any]]:
    """Collects read-only EC2 instance telemetry using pagination."""
    logger.info("Starting read-only EC2 instance collection")
    client = get_ec2_client(region)
    instances: List[Dict[str, Any]] = []

    try:
        paginator = client.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    # Extract security groups
                    sg_ids = [sg.get("GroupId") for sg in instance.get("SecurityGroups", []) if sg.get("GroupId")]

                    # Extract tags into key-value map
                    tags = {t.get("Key"): t.get("Value") for t in instance.get("Tags", []) if t.get("Key")}

                    launch_time = instance.get("LaunchTime")
                    launch_time_str = launch_time.isoformat() if launch_time else None

                    instance_data = {
                        "instance_id": instance.get("InstanceId"),
                        "state": instance.get("State", {}).get("Name"),
                        "instance_type": instance.get("InstanceType"),
                        "private_ip": instance.get("PrivateIpAddress"),
                        "public_ip": instance.get("PublicIpAddress"),
                        "availability_zone": instance.get("Placement", {}).get("AvailabilityZone"),
                        "subnet_id": instance.get("SubnetId"),
                        "vpc_id": instance.get("VpcId"),
                        "security_group_ids": sg_ids,
                        "ami_id": instance.get("ImageId"),
                        "launch_time": launch_time_str,
                        "tags": tags,
                    }
                    instances.append(instance_data)

        logger.info(f"EC2 collection completed: {len(instances)} instances found")
        return instances
    except ClientError as e:
        logger.error(f"AWS ClientError during EC2 collection: {e}")
        raise RuntimeError(f"EC2 API call failed: {e.response.get('Error', {}).get('Message', str(e))}") from e
