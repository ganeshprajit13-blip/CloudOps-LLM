"""
S3 + Athena data source for log search.

Query logs stored in S3 using Athena SQL queries. This approach:
- Has NO timestamp restrictions (unlike CloudWatch's 14-day limit)
- Costs ~$5 per TB scanned
- Query latency is 2-10 seconds (not real-time)
- Works well for historical analysis and HITL scenarios

Usage:
    source = S3AthenaDataSource(
        database="rca_logs",
        table="logs",
        output_location="s3://my-bucket/athena-results/"
    )
    results = source.search(
        query="timeout",
        time_start=datetime(2024, 3, 15, 14, 0),
        time_end=datetime(2024, 3, 15, 14, 30),
        filters={"service": "pricing-service"}
    )

Required Athena table schema:
    CREATE EXTERNAL TABLE logs (
        timestamp string,
        service string,
        level string,
        message string,
        source_file string
    )
    PARTITIONED BY (year string, month string, day string)
    ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.RegexSerDe'
    WITH SERDEPROPERTIES (
        'input.regex' = '^(\\S+)\\s+(\\S+)\\s+\\[(\\S+)\\]\\s+(.*)$'
    )
    LOCATION 's3://my-bucket/logs/';
"""

import os
import re
import time
import logging
from datetime import datetime
from typing import Optional

from .base import BaseDataSource, SearchResponse, SearchResult

# Pattern for valid SQL identifiers (alphanumeric + underscores, must start with letter/underscore)
_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(value: str, name: str) -> str:
    """Validate that a value is a safe SQL identifier."""
    if not _VALID_IDENTIFIER.match(value):
        raise ValueError(
            f"Invalid {name}: {value!r}. Must match [a-zA-Z_][a-zA-Z0-9_]*"
        )
    return value


def _escape_like_wildcards(value: str) -> str:
    """Escape LIKE pattern metacharacters so they match literally.

    This does NOT prevent SQL injection (that's handled by ExecutionParameters).
    It only ensures that % and _ in user input are treated as literal characters
    rather than LIKE wildcards.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


logger = logging.getLogger(__name__)


class S3AthenaDataSource(BaseDataSource):
    """
    Data source for querying logs in S3 via Athena.

    Supports:
    - SQL-based log queries with time windowing
    - Service filtering
    - Partitioned queries for cost optimization
    """

    def __init__(
        self,
        database: str,
        table: str,
        output_location: str,
        region: Optional[str] = None,
        workgroup: str = "primary",
        query_timeout: int = 60,
        timestamp_column: str = "timestamp",
        service_column: str = "service",
        message_column: str = "message",
    ):
        """
        Initialize Athena data source.

        Args:
            database: Athena database name
            table: Athena table name
            output_location: S3 location for query results (e.g., s3://bucket/results/)
            region: AWS region (defaults to AWS_REGION env var)
            workgroup: Athena workgroup (default: primary)
            query_timeout: Max seconds to wait for query (default: 60)
            timestamp_column: Column name for timestamp (default: timestamp)
            service_column: Column name for service (default: service)
            message_column: Column name for log message (default: message)
        """
        self.database = _validate_identifier(database, "database")
        self.table = _validate_identifier(table, "table")
        self.output_location = output_location
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.workgroup = workgroup
        self.query_timeout = query_timeout
        self.timestamp_column = _validate_identifier(
            timestamp_column, "timestamp_column"
        )
        self.service_column = _validate_identifier(service_column, "service_column")
        self.message_column = _validate_identifier(message_column, "message_column")
        self._client = None

    @property
    def client(self):
        """Lazy-initialize Athena client."""
        if self._client is None:
            try:
                import boto3
            except ImportError:
                raise ImportError("Install required package: pip install boto3")
            self._client = boto3.client("athena", region_name=self.region)
        return self._client

    def _build_query(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        filters: Optional[dict] = None,
        limit: int = 10,
    ) -> tuple:
        """Build parameterized SQL query and parameter list.

        Returns:
            (sql, params) where sql contains ? placeholders for user-provided
            values and params is the corresponding list of string values.
            Partition/timestamp values are embedded directly (from datetime objects,
            not user input) for Athena partition elimination.
        """
        where_clauses = []
        params: list[str] = []

        # --- Partition filters (from datetime objects, safe to embed) ---
        if time_start.date() == time_end.date():
            where_clauses.append(f"year = '{time_start.year}'")
            where_clauses.append(f"month = '{time_start.month:02d}'")
            where_clauses.append(f"day = '{time_start.day:02d}'")
        else:
            where_clauses.append(f"year = '{time_start.year}'")
            where_clauses.append(
                f"(month > '{time_start.month:02d}' OR "
                f"(month = '{time_start.month:02d}' AND day >= '{time_start.day:02d}'))"
            )
            where_clauses.append(
                f"(month < '{time_end.month:02d}' OR "
                f"(month = '{time_end.month:02d}' AND day <= '{time_end.day:02d}'))"
            )

        # --- Timestamp filters (from datetime.strftime, safe to embed) ---
        where_clauses.append(
            f"{self.timestamp_column} >= '{time_start.strftime('%Y-%m-%dT%H:%M:%S')}'"
        )
        where_clauses.append(
            f"{self.timestamp_column} <= '{time_end.strftime('%Y-%m-%dT%H:%M:%S')}'"
        )

        # --- Message content filter (user input → parameterized) ---
        where_clauses.append(f"LOWER({self.message_column}) LIKE ?")
        params.append("%" + _escape_like_wildcards(query.lower()) + "%")

        # --- Optional filters (user input → parameterized) ---
        if filters:
            if "service" in filters:
                from parsing_utils import parse_service_words

                service_words = list(parse_service_words(filters["service"]))
                if service_words:
                    word_conditions = []
                    for w in service_words:
                        word_conditions.append(f"LOWER({self.service_column}) LIKE ?")
                        params.append("%" + _escape_like_wildcards(w) + "%")
                    where_clauses.append(f"({' OR '.join(word_conditions)})")
            if "level" in filters:
                where_clauses.append("LOWER(level) = ?")
                params.append(filters["level"].lower())

        # Assemble final SQL. Identifier references (database, table, column names)
        # are validated in __init__ via _validate_identifier() regex
        # ^[a-zA-Z_][a-zA-Z0-9_]*$. User-provided values use ? placeholders
        # passed via ExecutionParameters (parameterized queries).
        sql = (
            f"SELECT {self.timestamp_column}, {self.service_column},"  # nosec B608
            f" {self.message_column}"
            f' FROM "{self.database}"."{self.table}"'
            f" WHERE {' AND '.join(where_clauses)}"
            f" ORDER BY {self.timestamp_column}"
            f" LIMIT {limit + 100}"
        )

        return sql, params

    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        filters: Optional[dict] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Search logs in S3 via Athena within a time window.

        Args:
            query: Search term to look for in log messages (substring match)
            time_start: Start of time window (REQUIRED)
            time_end: End of time window (REQUIRED)
            filters: Optional filters:
                - service: Filter by service name
                - level: Filter by log level (ERROR, WARN, INFO)
            limit: Maximum results to return

        Returns:
            SearchResponse with matching logs
        """
        sql, params = self._build_query(query, time_start, time_end, filters, limit)

        logger.info(f"Executing Athena query ({len(params)} params): {sql[:200]}...")

        try:
            response = self.client.start_query_execution(
                QueryString=sql,
                QueryExecutionContext={"Database": self.database},
                ResultConfiguration={"OutputLocation": self.output_location},
                WorkGroup=self.workgroup,
                ExecutionParameters=params,
            )
            query_execution_id = response["QueryExecutionId"]

            results = self._wait_for_results(query_execution_id)

            search_results = []
            total_matches = 0

            if results and "ResultSet" in results:
                rows = results["ResultSet"].get("Rows", [])
                for row in rows[1:]:
                    total_matches += 1
                    if len(search_results) < limit:
                        data = row.get("Data", [])
                        if len(data) >= 3:
                            ts_str = data[0].get("VarCharValue", "")
                            service = data[1].get("VarCharValue", "unknown")
                            message = data[2].get("VarCharValue", "")

                            ts = self._parse_timestamp(ts_str)

                            search_results.append(
                                SearchResult(
                                    source=service,
                                    content=message,
                                    timestamp=ts,
                                    metadata={"query_id": query_execution_id},
                                )
                            )

            return SearchResponse(
                results=search_results,
                total_matches=total_matches,
                query=query,
                truncated=total_matches > limit,
                time_start=time_start,
                time_end=time_end,
            )

        except Exception as e:
            logger.error(f"Athena query failed: {e}")
            return SearchResponse(
                results=[],
                total_matches=0,
                query=query,
                truncated=False,
                time_start=time_start,
                time_end=time_end,
                error=f"Athena query failed ({type(e).__name__}). Check server logs for details.",
            )

    def _wait_for_results(self, query_execution_id: str) -> dict:
        """Wait for Athena query to complete and return results."""
        start_time = time.time()

        while time.time() - start_time < self.query_timeout:
            response = self.client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            state = response["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                # Get results
                return self.client.get_query_results(
                    QueryExecutionId=query_execution_id
                )
            elif state in ("FAILED", "CANCELLED"):
                reason = response["QueryExecution"]["Status"].get(
                    "StateChangeReason", "Unknown"
                )
                raise RuntimeError(f"Query {state}: {reason}")

            time.sleep(1)

        raise TimeoutError(f"Query timed out after {self.query_timeout} seconds")

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        """Parse various timestamp formats."""
        from parsing_utils import parse_timestamp

        return parse_timestamp(ts_str)

    def health_check(self) -> dict:
        """Check Athena table exists via Glue metadata (free, no query cost)."""
        try:
            import boto3

            glue = boto3.client("glue", region_name=self.region)
            glue.get_table(DatabaseName=self.database, Name=self.table)
            return {
                "status": "ok",
                "details": {
                    "database": self.database,
                    "table": self.table,
                    "region": self.region,
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "details": {
                    "database": self.database,
                    "table": self.table,
                    "region": self.region,
                },
            }


def create_athena_source(
    database: str = None,
    table: str = None,
    output_location: str = None,
    region: str = None,
) -> S3AthenaDataSource:
    """
    Create S3+Athena data source from environment variables.

    Environment variables:
        ATHENA_DATABASE: Athena database name
        ATHENA_TABLE: Athena table name
        ATHENA_OUTPUT_LOCATION: S3 location for query results
        AWS_REGION: AWS region
    """
    return S3AthenaDataSource(
        database=database or os.environ.get("ATHENA_DATABASE", "rca_logs"),
        table=table or os.environ.get("ATHENA_TABLE", "logs"),
        output_location=output_location
        or os.environ.get(
            "ATHENA_OUTPUT_LOCATION", "s3://rca-agent-athena-results/query-results/"
        ),
        region=region or os.environ.get("AWS_REGION", "us-east-1"),
    )
