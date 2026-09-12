"""
OpenSearch data source for log search with time windowing.

Queries logs stored in an OpenSearch domain (or OpenSearch Serverless collection).
Supports both OpenSearch Service and OpenSearch Serverless with IAM (SigV4) or
basic (username/password) authentication.

Features:
- Full-text search with time windowing (mandatory)
- Service filtering with word-based matching (consistent with Athena/CloudWatch)
- IAM (SigV4) auth for AWS-managed domains, or basic auth for self-managed
- Lazy client initialization (opensearch-py only imported on first use)

Usage:
    source = OpenSearchDataSource(
        endpoint="https://my-domain.us-east-1.es.amazonaws.com",
        index="rca-logs",
        auth_mode="iam",
        region="us-east-1"
    )
    results = source.search(
        query="timeout",
        time_start=datetime(2024, 3, 15, 14, 0),
        time_end=datetime(2024, 3, 15, 14, 30),
        filters={"service": "pricing-service"}
    )

Required index mapping (recommended):
    PUT /rca-logs
    {
      "mappings": {
        "properties": {
          "timestamp": { "type": "date" },
          "service":   { "type": "keyword" },
          "level":     { "type": "keyword" },
          "message":   { "type": "text" },
          "source_file": { "type": "keyword" }
        }
      }
    }
"""

import json as _json
import logging
import os
from datetime import datetime
from functools import lru_cache
from typing import Optional

from .base import BaseDataSource, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _resolve_secret(secret_arn: str, region: str) -> tuple:
    """Fetch OpenSearch credentials from Secrets Manager.

    Returns (username, password). Cached for the process lifetime.
    The secret JSON must have 'username' and 'password' keys.
    On credential rotation, restart the container to clear the cache.
    """
    import boto3

    client = boto3.client("secretsmanager", region_name=region)
    resp = client.get_secret_value(SecretId=secret_arn)
    secret = _json.loads(resp["SecretString"])
    return secret["username"], secret["password"]


class OpenSearchDataSource(BaseDataSource):
    """
    Data source for querying logs in OpenSearch.

    Supports:
    - Full-text search with time windowing
    - Service filtering (word-based matching)
    - IAM (SigV4) authentication for AWS-managed domains
    - Basic (username/password) authentication for self-managed clusters
    - OpenSearch Serverless collections
    """

    def __init__(
        self,
        endpoint: str,
        index: str,
        auth_mode: str = "iam",
        region: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_certs: bool = True,
        timestamp_field: str = "timestamp",
        service_field: str = "service",
        message_field: str = "message",
        level_field: str = "level",
        serverless: bool = False,
    ):
        """
        Initialize OpenSearch data source.

        Args:
            endpoint: OpenSearch domain endpoint (e.g., https://my-domain.us-east-1.es.amazonaws.com)
            index: Index name or pattern (e.g., "rca-logs" or "rca-logs-*")
            auth_mode: Authentication mode - "iam" for SigV4 or "basic" for username/password
            region: AWS region (for IAM auth; defaults to AWS_REGION env var)
            username: Username for basic auth
            password: Password for basic auth
            verify_certs: Whether to verify SSL certificates (default: True)
            timestamp_field: Field name for timestamp (default: "timestamp")
            service_field: Field name for service (default: "service")
            message_field: Field name for log message (default: "message")
            level_field: Field name for log level (default: "level")
            serverless: Set True for OpenSearch Serverless collections (uses aoss service for SigV4)
        """
        self.endpoint = endpoint.rstrip("/")
        self.index = index
        self.auth_mode = auth_mode.lower()
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.username = username
        self.password = password
        self.verify_certs = verify_certs
        self.timestamp_field = timestamp_field
        self.service_field = service_field
        self.message_field = message_field
        self.level_field = level_field
        self.serverless = serverless
        self._client = None

    @property
    def client(self):
        """Lazy-initialize OpenSearch client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self):
        """Create OpenSearch client with the configured auth mode."""
        try:
            from opensearchpy import OpenSearch
        except ImportError:
            raise ImportError(
                "Install required packages: pip install opensearch-py\n"
                "For IAM auth also install: pip install requests-aws4auth boto3"
            )

        if self.auth_mode == "iam":
            return self._create_iam_client(OpenSearch)
        elif self.auth_mode == "basic":
            return self._create_basic_client(OpenSearch)
        else:
            raise ValueError(
                f"Unknown auth_mode: {self.auth_mode!r}. Use 'iam' or 'basic'."
            )

    def _create_iam_client(self, OpenSearch):
        """Create client with IAM SigV4 authentication."""
        try:
            import boto3
            from requests_aws4auth import AWS4Auth
        except ImportError:
            raise ImportError(
                "Install required packages for IAM auth: pip install boto3 requests-aws4auth"
            )

        credentials = boto3.Session().get_credentials()
        service = "aoss" if self.serverless else "es"
        auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.region,
            service,
            session_token=credentials.token,
        )

        # Serverless needs explicit host/port dict for reliable connectivity
        host = self.endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        return OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=self.verify_certs,
            connection_class=self._get_connection_class(),
        )

    def _create_basic_client(self, OpenSearch):
        """Create client with basic username/password authentication."""
        if not self.username or not self.password:
            raise ValueError("username and password required for basic auth_mode")

        return OpenSearch(
            hosts=[self.endpoint],
            http_auth=(self.username, self.password),
            use_ssl=self.endpoint.startswith("https"),
            verify_certs=self.verify_certs,
        )

    def _get_connection_class(self):
        """Get the appropriate connection class for requests-based auth."""
        from opensearchpy import RequestsHttpConnection

        return RequestsHttpConnection

    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        filters: Optional[dict] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Search logs in OpenSearch within a time window.

        Args:
            query: Search term to look for in log messages
            time_start: Start of time window (REQUIRED)
            time_end: End of time window (REQUIRED)
            filters: Optional filters:
                - service: Filter by service name (word-based matching)
                - level: Filter by log level (ERROR, WARN, INFO)
            limit: Maximum results to return

        Returns:
            SearchResponse with matching logs and quality score
        """
        body = self._build_query(query, time_start, time_end, filters, limit)

        logger.info(
            f"Searching OpenSearch index '{self.index}' for '{query}' "
            f"({time_start.isoformat()} to {time_end.isoformat()})"
        )

        try:
            response = self.client.search(index=self.index, body=body)
            return self._parse_response(response, query, time_start, time_end, limit)
        except Exception as e:
            logger.error(f"OpenSearch query failed: {e}")
            return SearchResponse(
                results=[],
                total_matches=0,
                query=query,
                truncated=False,
                time_start=time_start,
                time_end=time_end,
                error=f"OpenSearch query failed ({type(e).__name__}). Check server logs for details.",
            )

    def _build_query(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        filters: Optional[dict],
        limit: int,
    ) -> dict:
        """Build OpenSearch query DSL."""
        must_clauses = [
            # Time range filter
            {
                "range": {
                    self.timestamp_field: {
                        "gte": time_start.strftime("%Y-%m-%dT%H:%M:%S"),
                        "lte": time_end.strftime("%Y-%m-%dT%H:%M:%S"),
                        "format": "strict_date_optional_time||epoch_millis",
                    }
                }
            },
            # Full-text search on message field
            {
                "match": {
                    self.message_field: {
                        "query": query,
                        "operator": "and",
                    }
                }
            },
        ]

        if filters:
            if "service" in filters:
                # Word-based matching consistent with Athena/local-file adapters
                from parsing_utils import parse_service_words

                service_words = list(parse_service_words(filters["service"]))
                if service_words:
                    should_clauses = [
                        {
                            "wildcard": {
                                self.service_field: f"*{self._escape_wildcard(word)}*"
                            }
                        }
                        for word in service_words
                    ]
                    must_clauses.append(
                        {"bool": {"should": should_clauses, "minimum_should_match": 1}}
                    )

            if "level" in filters:
                must_clauses.append(
                    {"term": {self.level_field: filters["level"].upper()}}
                )

        # Request extra results so total_matches reflects broader count
        return {
            "query": {"bool": {"must": must_clauses}},
            "sort": [{self.timestamp_field: {"order": "asc"}}],
            "size": limit + 100,
            "track_total_hits": True,
        }

    def _parse_response(
        self,
        response: dict,
        query: str,
        time_start: datetime,
        time_end: datetime,
        limit: int,
    ) -> SearchResponse:
        """Parse OpenSearch response into SearchResponse."""
        hits = response.get("hits", {})
        total_value = hits.get("total", {})
        if isinstance(total_value, dict):
            total_matches = total_value.get("value", 0)
        else:
            total_matches = total_value

        results = []
        for hit in hits.get("hits", []):
            if len(results) >= limit:
                break

            source = hit.get("_source", {})
            ts = self._parse_timestamp(source.get(self.timestamp_field))
            service_name = source.get(self.service_field, "unknown")
            message = source.get(self.message_field, "")

            results.append(
                SearchResult(
                    source=service_name,
                    content=message,
                    timestamp=ts,
                    metadata={"index": hit.get("_index"), "id": hit.get("_id")},
                )
            )

        return SearchResponse(
            results=results,
            total_matches=total_matches,
            query=query,
            truncated=total_matches > limit,
            time_start=time_start,
            time_end=time_end,
        )

    @staticmethod
    def _escape_wildcard(value: str) -> str:
        """Escape OpenSearch wildcard special characters (* and ?)."""
        return value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")

    def _parse_timestamp(self, ts_value) -> Optional[datetime]:
        """Parse various timestamp formats from OpenSearch."""
        from parsing_utils import parse_timestamp

        return parse_timestamp(ts_value)

    def health_check(self) -> dict:
        """Check OpenSearch connectivity and index existence."""
        try:
            self.client.info()
            index_exists = self.client.indices.exists(index=self.index)
            return {
                "status": "ok" if index_exists else "error",
                "message": None
                if index_exists
                else f"Index '{self.index}' does not exist",
                "details": {
                    "endpoint": self.endpoint,
                    "index": self.index,
                    "index_exists": bool(index_exists),
                    "serverless": self.serverless,
                    "auth_mode": self.auth_mode,
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "details": {
                    "endpoint": self.endpoint,
                    "index": self.index,
                    "serverless": self.serverless,
                },
            }


def create_opensearch_source(
    endpoint: str = None,
    index: str = None,
    auth_mode: str = None,
    region: str = None,
) -> OpenSearchDataSource:
    """
    Create OpenSearch data source from environment variables.

    Environment variables:
        OPENSEARCH_ENDPOINT: Domain endpoint URL
        OPENSEARCH_INDEX: Index name or pattern
        OPENSEARCH_AUTH_MODE: "iam" or "basic" (default: iam)
        OPENSEARCH_USERNAME: Username for basic auth (or use OPENSEARCH_SECRET_ARN)
        OPENSEARCH_PASSWORD: Password for basic auth (or use OPENSEARCH_SECRET_ARN)
        OPENSEARCH_SECRET_ARN: Secrets Manager ARN for credentials (preferred over env vars)
        OPENSEARCH_SERVERLESS: "true" for OpenSearch Serverless
        AWS_REGION: AWS region (for IAM auth)
    """
    username = os.environ.get("OPENSEARCH_USERNAME")
    password = os.environ.get("OPENSEARCH_PASSWORD")

    secret_arn = os.environ.get("OPENSEARCH_SECRET_ARN")
    if secret_arn:
        region_val = region or os.environ.get("AWS_REGION", "us-east-1")
        username, password = _resolve_secret(secret_arn, region_val)

    return OpenSearchDataSource(
        endpoint=endpoint or os.environ.get("OPENSEARCH_ENDPOINT", ""),
        index=index or os.environ.get("OPENSEARCH_INDEX", "rca-logs"),
        auth_mode=auth_mode or os.environ.get("OPENSEARCH_AUTH_MODE", "iam"),
        region=region or os.environ.get("AWS_REGION", "us-east-1"),
        username=username,
        password=password,
        serverless=os.environ.get("OPENSEARCH_SERVERLESS", "").lower() == "true",
    )
