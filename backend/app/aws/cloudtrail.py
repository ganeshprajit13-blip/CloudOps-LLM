from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from botocore.exceptions import ClientError
from app.aws.client import get_cloudtrail_client
from app.core.logging import logger


def get_cloudtrail_events(
    hours: int = 1,
    max_results: int = 50,
    region: str | None = None,
) -> List[Dict[str, Any]]:
    """Collects recent read-only CloudTrail management events using lookup_events."""
    logger.info(f"Starting CloudTrail event collection for last {hours} hour(s)")
    client = get_cloudtrail_client(region)
    events: List[Dict[str, Any]] = []

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    try:
        paginator = client.get_paginator("lookup_events")
        page_iterator = paginator.paginate(
            StartTime=start_time,
            EndTime=end_time,
            PaginationConfig={"MaxItems": max_results},
        )

        for page in page_iterator:
            for event in page.get("Events", []):
                resources = [
                    {
                        "resource_type": r.get("ResourceType"),
                        "resource_name": r.get("ResourceName"),
                    }
                    for r in event.get("Resources", [])
                ]

                event_time = event.get("EventTime")
                event_time_str = event_time.isoformat() if event_time else None

                events.append({
                    "event_id": event.get("EventId"),
                    "event_time": event_time_str,
                    "event_name": event.get("EventName"),
                    "event_source": event.get("EventSource"),
                    "username": event.get("Username"),
                    "resources": resources,
                    "aws_region": region or client.meta.region_name,
                    "access_key_id": event.get("AccessKeyId"),
                })

        logger.info(f"CloudTrail event collection completed: {len(events)} events found")
        return events
    except ClientError as e:
        logger.error(f"AWS ClientError during CloudTrail collection: {e}")
        raise RuntimeError(f"CloudTrail API call failed: {e.response.get('Error', {}).get('Message', str(e))}") from e
