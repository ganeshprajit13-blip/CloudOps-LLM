"""
Data source adapters for the Deep Research RCA Agent.

Available data sources:
- LogFileDataSource: Local log files (for demos and testing)
- CloudWatchLogsDataSource: AWS CloudWatch Logs Insights (production)
- S3AthenaDataSource: AWS S3 + Athena (production, historical logs)
- OpenSearchDataSource: AWS OpenSearch / OpenSearch Serverless (production, full-text)

All data sources implement the BaseDataSource interface with mandatory time windowing.

Example usage:
    from data_sources import create_log_source

    # For local testing
    source = create_log_source("/path/to/logs")

    # Search with required time window
    results = source.search(
        query="timeout",
        time_start=datetime(2024, 3, 15, 14, 0),
        time_end=datetime(2024, 3, 15, 14, 30),
        filters={"service": "pricing-service"}
    )
"""

from .base import BaseDataSource, SearchResponse, SearchResult, TimeWindow

from .log_files import LogFileDataSource, create_log_source


def create_cloudwatch_source(*args, **kwargs):
    """Create CloudWatch Logs Insights data source."""
    from .cloudwatch_logs import CloudWatchLogsDataSource

    return CloudWatchLogsDataSource(*args, **kwargs)


def create_opensearch_source(*args, **kwargs):
    """Create OpenSearch data source."""
    from .opensearch import OpenSearchDataSource

    return OpenSearchDataSource(*args, **kwargs)


__all__ = [
    "BaseDataSource",
    "SearchResponse",
    "SearchResult",
    "TimeWindow",
    "LogFileDataSource",
    "create_log_source",
    "create_cloudwatch_source",
    "create_opensearch_source",
]
