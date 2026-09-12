from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from botocore.exceptions import ClientError
from app.aws.client import get_cloudwatch_client
from app.core.logging import logger


DEFAULT_METRICS = [
    "CPUUtilization",
    "NetworkIn",
    "NetworkOut",
    "DiskReadOps",
    "DiskWriteOps",
]


def get_cloudwatch_metrics(
    resource_id: str | None = None,
    instance_ids: List[str] | None = None,
    metric_names: List[str] | None = None,
    minutes: int = 30,
    period: int = 300,
    region: str | None = None,
) -> List[Dict[str, Any]]:
    """Collects read-only CloudWatch metric statistics for specified or default metrics."""
    logger.info(f"Starting CloudWatch metrics collection for window: {minutes} minutes")
    client = get_cloudwatch_client(region)
    metrics_to_fetch = metric_names or DEFAULT_METRICS
    results: List[Dict[str, Any]] = []

    target_instances: List[str] = []
    if instance_ids:
        target_instances.extend([str(i) for i in instance_ids if i])
    elif resource_id:
        target_instances.append(str(resource_id))

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=minutes)

    instances_to_query = target_instances if target_instances else [None]

    for target_inst in instances_to_query:
        for metric_name in metrics_to_fetch:
            dimensions = []
            if target_inst:
                dimensions.append({"Name": "InstanceId", "Value": target_inst})

            try:
                response = client.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName=metric_name,
                    Dimensions=dimensions,
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=["Average", "Maximum"],
                )

                datapoints = response.get("Datapoints", [])
                for dp in datapoints:
                    ts = dp.get("Timestamp")
                    ts_str = ts.isoformat() if ts else None
                    results.append({
                        "metric_name": metric_name,
                        "resource_id": target_inst or "all",
                        "timestamp": ts_str,
                        "average": dp.get("Average"),
                        "maximum": dp.get("Maximum"),
                        "unit": dp.get("Unit"),
                    })
            except ClientError as e:
                logger.warning(f"Failed to fetch metric {metric_name} for resource {target_inst}: {e}")

    logger.info(f"CloudWatch metrics collection completed: {len(results)} datapoints gathered")
    return results
