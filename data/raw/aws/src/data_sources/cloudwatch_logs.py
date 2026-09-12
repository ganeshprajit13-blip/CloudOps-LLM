"""
CloudWatch Logs Insights data source for log search with time windowing.

This provides an alternative to OpenSearch for users who prefer CloudWatch.
Requires AWS credentials and the boto3 library.

Example:
    from cloudwatch_logs import CloudWatchLogsDataSource

    source = CloudWatchLogsDataSource(
        log_group_names=["/aws/lambda/my-function", "/ecs/my-service"],
        region="us-east-1"
    )
    results = source.search(
        query="timeout",
        time_start=datetime(2024, 3, 15, 14, 0),
        time_end=datetime(2024, 3, 15, 14, 30),
        filters={"service": "pricing-service"}
    )
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional

from botocore.exceptions import ClientError

from .base import BaseDataSource, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

# Retry configuration for rate limiting
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 10.0  # seconds


class CloudWatchLogsDataSource(BaseDataSource):
    """
    Data source for CloudWatch Logs Insights.

    Uses CloudWatch Logs Insights queries for searching across log groups.
    Supports time-windowed search for production-realistic investigation.
    """

    def __init__(
        self,
        log_group_names: Optional[list[str]] = None,
        log_group_prefix: Optional[str] = None,
        region: Optional[str] = None,
        query_timeout: int = 30,
    ):
        """
        Initialize CloudWatch Logs client.

        Args:
            log_group_names: List of log group names to search
            log_group_prefix: Prefix to find log groups (e.g., "/aws/lambda/")
            region: AWS region (or AWS_REGION env var, default: us-east-1)
            query_timeout: Max seconds to wait for query results (default: 30)
        """
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.query_timeout = query_timeout

        self._client = None
        self._log_group_names = log_group_names
        self._log_group_prefix = log_group_prefix

    @property
    def client(self):
        """Lazy-initialize CloudWatch Logs client."""
        if self._client is None:
            try:
                import boto3
            except ImportError:
                raise ImportError("Install required package: pip install boto3")

            self._client = boto3.client("logs", region_name=self.region)

        return self._client

    @property
    def log_group_names(self) -> list[str]:
        """Get log group names, discovering from prefix if needed."""
        if self._log_group_names:
            return self._log_group_names

        if self._log_group_prefix:
            # Discover log groups by prefix
            groups = []
            paginator = self.client.get_paginator("describe_log_groups")
            for page in paginator.paginate(logGroupNamePrefix=self._log_group_prefix):
                groups.extend([g["logGroupName"] for g in page["logGroups"]])
            return groups

        raise ValueError("Must provide either log_group_names or log_group_prefix")

    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        filters: Optional[dict] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Search CloudWatch Logs within a time window using filter-log-events.

        Args:
            query: Search term to look for in log messages
            time_start: Start of time window (REQUIRED)
            time_end: End of time window (REQUIRED)
            filters: Optional filters:
                - service: Filter by log stream name containing service name
                - level: Filter by log level pattern
            limit: Maximum results to return

        Returns:
            SearchResponse with matching logs and quality score
        """
        results = []
        total_matched = 0

        # Build filter pattern for CloudWatch
        filter_pattern = query
        if filters and "level" in filters:
            level = filters["level"].upper()
            filter_pattern = f"{query} {level}"

        # Search across all log groups with retry logic
        for log_group in self.log_group_names:
            retries = 0
            backoff = INITIAL_BACKOFF

            while retries <= MAX_RETRIES:
                try:
                    # Use filter_log_events for reliable real-time search
                    paginator = self.client.get_paginator("filter_log_events")

                    kwargs = {
                        "logGroupName": log_group,
                        "startTime": int(time_start.timestamp() * 1000),  # milliseconds
                        "endTime": int(time_end.timestamp() * 1000),  # milliseconds
                        "filterPattern": filter_pattern,
                        "limit": limit,
                    }

                    # Filter by service (log stream name) if specified
                    if filters and "service" in filters:
                        kwargs["logStreamNamePrefix"] = filters["service"]

                    for page in paginator.paginate(**kwargs):
                        for event in page.get("events", []):
                            if len(results) >= limit:
                                break

                            # Parse timestamp
                            ts = None
                            if "timestamp" in event:
                                try:
                                    ts = datetime.fromtimestamp(
                                        event["timestamp"] / 1000
                                    )
                                except (ValueError, TypeError):
                                    pass

                            results.append(
                                SearchResult(
                                    source=event.get("logStreamName", "unknown"),
                                    content=event.get("message", ""),
                                    timestamp=ts,
                                    metadata={"log_group": log_group},
                                )
                            )
                            total_matched += 1

                        if len(results) >= limit:
                            break

                    # Success - break retry loop
                    break

                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code in (
                        "ThrottlingException",
                        "LimitExceededException",
                        "ServiceUnavailableException",
                    ):
                        retries += 1
                        if retries <= MAX_RETRIES:
                            logger.warning(
                                f"Rate limited on {log_group}, retry {retries}/{MAX_RETRIES} after {backoff}s"
                            )
                            time.sleep(backoff)
                            backoff = min(backoff * 2, MAX_BACKOFF)
                            continue
                    logger.warning(f"Error querying log group {log_group}: {e}")
                    break

                except Exception as e:
                    logger.warning(f"Error querying log group {log_group}: {e}")
                    break

            if len(results) >= limit:
                break

        return SearchResponse(
            results=results[:limit],
            total_matches=total_matched,
            query=query,
            truncated=total_matched > limit,
            time_start=time_start,
            time_end=time_end,
        )

    def list_sources(self) -> list[str]:
        """Return available log group names."""
        try:
            return self.log_group_names
        except (ValueError, Exception):
            return []

    def health_check(self) -> dict:
        """Check CloudWatch connectivity by describing log groups."""
        try:
            if self._log_group_names:
                # Verify at least the first log group exists
                resp = self.client.describe_log_groups(
                    logGroupNamePrefix=self._log_group_names[0], limit=1
                )
                found = len(resp.get("logGroups", []))
                return {
                    "status": "ok" if found > 0 else "error",
                    "message": None if found > 0 else "No matching log groups found",
                    "details": {
                        "log_group_count": len(self._log_group_names),
                        "region": self.region,
                    },
                }
            elif self._log_group_prefix:
                resp = self.client.describe_log_groups(
                    logGroupNamePrefix=self._log_group_prefix, limit=1
                )
                found = len(resp.get("logGroups", []))
                return {
                    "status": "ok" if found > 0 else "error",
                    "message": None
                    if found > 0
                    else f"No log groups matching prefix: {self._log_group_prefix}",
                    "details": {
                        "prefix": self._log_group_prefix,
                        "region": self.region,
                    },
                }
            else:
                return {
                    "status": "error",
                    "message": "No log groups or prefix configured",
                    "details": {"region": self.region},
                }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "details": {"region": self.region},
            }

    def list_log_groups(self, prefix: Optional[str] = None) -> list[str]:
        """List available log groups."""
        groups = []
        paginator = self.client.get_paginator("describe_log_groups")
        kwargs = {}
        if prefix:
            kwargs["logGroupNamePrefix"] = prefix
        for page in paginator.paginate(**kwargs):
            groups.extend([g["logGroupName"] for g in page["logGroups"]])
        return groups


def create_cloudwatch_source(
    log_group_names: Optional[list[str]] = None,
    log_group_prefix: Optional[str] = None,
    region: Optional[str] = None,
) -> CloudWatchLogsDataSource:
    """Convenience function to create CloudWatch Logs data source."""
    return CloudWatchLogsDataSource(
        log_group_names=log_group_names,
        log_group_prefix=log_group_prefix,
        region=region,
    )
