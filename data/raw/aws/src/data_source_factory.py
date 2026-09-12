"""
Factory for creating data sources.

Supports two modes:
- LOCAL: File-based logs from scenario directories, Bedrock KB for context
- PRODUCTION: CloudWatch Logs, S3+Athena, or OpenSearch for logs; Bedrock KB for context

Context retrieval uses Bedrock Knowledge Base when BEDROCK_KB_ID is set.
In LOCAL mode without a KB, falls back to keyword search over scenario context files.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from config import get_config, DataSourceMode, LogSearchBackend
from data_sources.base import SearchResponse

logger = logging.getLogger(__name__)


def format_search_results(
    result: SearchResponse, available_sources: list[str] | None = None
) -> str:
    """Format search results for display. Shared across all log search sources.

    Args:
        result: The SearchResponse from a data source search.
        available_sources: Optional list of available log source names.
            When provided and the search returns zero matches, these are
            appended to help the agent retry with a valid service filter.
    """
    if result.error:
        return f"SEARCH ERROR: {result.error}"
    if not result.results:
        msg = f"No logs found matching '{result.query}' in time window {result.time_start} to {result.time_end}"
        if available_sources:
            msg += (
                "\n\nAvailable log sources: "
                + ", ".join(available_sources)
                + "\nHint: Your service filter may not match any source. "
                "Try a different service name from the list above, or omit "
                "the service filter to search all sources."
            )
        return msg

    lines = [
        f"Found {result.total_matches} logs matching '{result.query}'",
        f"Time window: {result.time_start} to {result.time_end}",
        "",
    ]

    for r in result.results:
        ts = r.timestamp.isoformat() if r.timestamp else "unknown"
        lines.append(f"[{ts}] {r.source}: {r.content}")

    if result.truncated:
        lines.append(
            f"\n... and {result.total_matches - len(result.results)} more results"
        )

    return "\n".join(lines)


# =============================================================================
# LOCAL MODE: File-based log search (kept for local dev of log evidence)
# =============================================================================


class LocalLogSearchSource:
    """Log search using local log files from scenario's evidence/ directory."""

    def __init__(self, scenarios_dir: Path):
        self.scenarios_dir = scenarios_dir
        self._current_scenario: Optional[str] = None
        self._data_source = None

    def set_scenario(self, scenario_name: str):
        """Set the current scenario for log search."""
        from data_sources.log_files import LogFileDataSource

        evidence_dir = self.scenarios_dir / scenario_name / "evidence"
        if not evidence_dir.exists():
            raise ValueError(f"Evidence directory not found: {evidence_dir}")

        self._current_scenario = scenario_name
        self._data_source = LogFileDataSource(evidence_dir)

    def list_sources(self) -> list[str]:
        """Return available log source names for the current scenario."""
        if self._data_source is None:
            return []
        return self._data_source.list_sources()

    def health_check(self) -> dict:
        """Check that the scenarios directory exists and has evidence files."""
        try:
            if not self.scenarios_dir.exists():
                return {
                    "status": "error",
                    "message": f"Directory not found: {self.scenarios_dir}",
                    "details": {"directory": str(self.scenarios_dir)},
                }
            evidence_dirs = [
                d.name
                for d in self.scenarios_dir.iterdir()
                if d.is_dir() and (d / "evidence").is_dir()
            ]
            return {
                "status": "ok",
                "details": {
                    "directory": str(self.scenarios_dir),
                    "scenarios_with_evidence": len(evidence_dirs),
                },
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "details": {}}

    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        service: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Search local log files."""
        if self._data_source is None:
            return "ERROR: No scenario set. Call set_scenario() first."

        filters = {}
        if service:
            filters["service"] = service

        result = self._data_source.search(
            query=query,
            time_start=time_start,
            time_end=time_end,
            filters=filters if filters else None,
            limit=limit,
        )
        return format_search_results(result, self.list_sources())


# =============================================================================
# PRODUCTION/ATHENA MODE: AWS-based sources
# =============================================================================


class AthenaLogSearchSource:
    """Log search using S3 + Athena for historical log queries."""

    def __init__(
        self, database: str, table: str, output_location: str, region: str = "us-east-1"
    ):
        from data_sources.s3_athena import S3AthenaDataSource

        self.data_source = S3AthenaDataSource(
            database=database,
            table=table,
            output_location=output_location,
            region=region,
        )

    def set_scenario(self, scenario_name: str):
        """No-op for Athena - all scenarios share the same table."""
        pass

    def list_sources(self) -> list[str]:
        """Return available log sources (Athena cannot enumerate without query)."""
        return self.data_source.list_sources()

    def health_check(self) -> dict:
        """Delegate health check to the underlying Athena data source."""
        return self.data_source.health_check()

    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        service: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Search logs in S3 via Athena."""
        filters = {}
        if service:
            filters["service"] = service

        result = self.data_source.search(
            query=query,
            time_start=time_start,
            time_end=time_end,
            filters=filters if filters else None,
            limit=limit,
        )
        return format_search_results(result, self.list_sources())


class BedrockContextSource:
    """Context source for runbooks and past incidents using Bedrock KB."""

    def __init__(self, kb_id: str, region: str = "us-east-1"):
        self.kb_id = kb_id
        self.region = region
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "bedrock-agent-runtime", region_name=self.region
            )
        return self._client

    def search(
        self,
        query: str,
        num_results: int = 5,
        scenario_name: Optional[str] = None,
    ) -> list[str]:
        """Retrieve context chunks via semantic search from Bedrock KB.

        Uses the KB's default search type (SEMANTIC for S3 Vectors,
        HYBRID for OpenSearch-backed KBs). Does not override search type
        so the KB storage backend determines the best strategy.

        Args:
            query: The search query (e.g., "handover failure timeout").
            num_results: Maximum number of chunks to return.
            scenario_name: Ignored — Bedrock KB is global.

        Returns:
            List of matching text chunks from the knowledge base.
        """
        try:
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": num_results,
                    }
                },
            )
            chunks = []
            for result in response.get("retrievalResults", []):
                content = result.get("content", {}).get("text", "")
                if content:
                    chunks.append(content)
            return chunks
        except Exception as e:
            logger.error(f"Bedrock KB search error for query '{query}': {e}")
            return []

    def health_check(self) -> dict:
        """Check Bedrock KB connectivity with a minimal retrieve call."""
        try:
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": "health check"},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": 1}
                },
            )
            chunk_count = len(response.get("retrievalResults", []))
            return {
                "status": "ok",
                "details": {
                    "kb_id": self.kb_id,
                    "region": self.region,
                    "has_data": chunk_count > 0,
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "details": {"kb_id": self.kb_id, "region": self.region},
            }

    def get_context(self, scenario_name: Optional[str] = None) -> dict:
        """Retrieve context using hybrid search from Bedrock KB.

        Delegates to :meth:`search` with two generic queries for
        backward compatibility.
        """
        context = {}

        runbook_chunks = self.search(
            f"runbooks troubleshooting guide {scenario_name or ''}",
        )
        if runbook_chunks:
            context["runbooks"] = "\n\n---\n\n".join(runbook_chunks)

        incident_chunks = self.search(
            f"past incidents similar issues {scenario_name or ''}",
        )
        if incident_chunks:
            context["past_incidents"] = "\n\n---\n\n".join(incident_chunks)

        return context


class LocalContextSource:
    """File-based context source for local development without Bedrock KB.

    Reads scenario context files from ``scenarios/{name}/context/*.md`` and
    performs simple keyword-scored chunk retrieval.
    """

    # Approximate chunk size in characters (split at paragraph boundaries).
    _CHUNK_SIZE = 500

    def __init__(self, scenarios_dir: Path):
        self.scenarios_dir = scenarios_dir

    def health_check(self) -> dict:
        """Check that the scenarios directory exists with context files."""
        try:
            if not self.scenarios_dir.exists():
                return {
                    "status": "error",
                    "message": f"Directory not found: {self.scenarios_dir}",
                    "details": {"directory": str(self.scenarios_dir)},
                }
            context_dirs = [
                d.name
                for d in self.scenarios_dir.iterdir()
                if d.is_dir() and (d / "context").is_dir()
            ]
            return {
                "status": "ok",
                "details": {
                    "directory": str(self.scenarios_dir),
                    "scenarios_with_context": len(context_dirs),
                },
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "details": {}}

    def _load_chunks(self, scenario_name: Optional[str]) -> list[str]:
        """Read all .md files for a scenario and split into chunks."""
        if not scenario_name:
            return []
        context_dir = self.scenarios_dir / scenario_name / "context"
        if not context_dir.is_dir():
            return []

        chunks: list[str] = []
        for md_file in sorted(context_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8", errors="replace")
            # Split on double-newlines (paragraph boundaries)
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            # Merge small paragraphs into chunks of ~_CHUNK_SIZE chars
            current = ""
            for para in paragraphs:
                if current and len(current) + len(para) > self._CHUNK_SIZE:
                    chunks.append(current)
                    current = para
                else:
                    current = f"{current}\n\n{para}" if current else para
            if current:
                chunks.append(current)
        return chunks

    @staticmethod
    def _score(query: str, chunk: str) -> int:
        """Score a chunk by counting how many query words appear in it."""
        words = set(query.lower().split())
        chunk_lower = chunk.lower()
        return sum(1 for w in words if w in chunk_lower)

    def search(
        self,
        query: str,
        num_results: int = 5,
        scenario_name: Optional[str] = None,
    ) -> list[str]:
        """Retrieve context chunks via keyword scoring from local files."""
        chunks = self._load_chunks(scenario_name)
        if not chunks:
            return []
        scored = [(self._score(query, c), c) for c in chunks]
        scored.sort(key=lambda x: x[0], reverse=True)
        # Return top chunks that have at least one keyword match
        return [c for score, c in scored[:num_results] if score > 0]


class OpenSearchLogSearchSource:
    """Log search using OpenSearch for full-text log queries."""

    def __init__(
        self,
        endpoint: str,
        index: str,
        auth_mode: str = "iam",
        region: str = "us-east-1",
        username: Optional[str] = None,
        password: Optional[str] = None,
        serverless: bool = False,
    ):
        from data_sources.opensearch import OpenSearchDataSource

        self.data_source = OpenSearchDataSource(
            endpoint=endpoint,
            index=index,
            auth_mode=auth_mode,
            region=region,
            username=username,
            password=password,
            serverless=serverless,
        )

    def set_scenario(self, scenario_name: str):
        """No-op for OpenSearch - all scenarios share the same index."""
        pass

    def list_sources(self) -> list[str]:
        """Return available log sources (OpenSearch cannot enumerate without query)."""
        return self.data_source.list_sources()

    def health_check(self) -> dict:
        """Delegate health check to the underlying OpenSearch data source."""
        return self.data_source.health_check()

    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        service: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Search logs in OpenSearch."""
        filters = {}
        if service:
            filters["service"] = service

        result = self.data_source.search(
            query=query,
            time_start=time_start,
            time_end=time_end,
            filters=filters if filters else None,
            limit=limit,
        )
        return format_search_results(result, self.list_sources())


class CloudWatchLogSearchSource:
    """Log search using CloudWatch Logs."""

    def __init__(
        self,
        log_group_names: Optional[list[str]] = None,
        log_group_prefix: Optional[str] = None,
        region: str = "us-east-1",
    ):
        from data_sources.cloudwatch_logs import CloudWatchLogsDataSource

        self.data_source = CloudWatchLogsDataSource(
            log_group_names=log_group_names,
            log_group_prefix=log_group_prefix,
            region=region,
        )

    def set_scenario(self, scenario_name: str):
        """No-op for CloudWatch - scenario is determined by log group prefix."""
        pass

    def list_sources(self) -> list[str]:
        """Return available CloudWatch log group names."""
        return self.data_source.list_sources()

    def health_check(self) -> dict:
        """Delegate health check to the underlying CloudWatch data source."""
        return self.data_source.health_check()

    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        service: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Search CloudWatch Logs."""
        filters = {}
        if service:
            filters["service"] = service

        result = self.data_source.search(
            query=query,
            time_start=time_start,
            time_end=time_end,
            filters=filters if filters else None,
            limit=limit,
        )
        return format_search_results(result, self.list_sources())


# =============================================================================
# Factory functions
# =============================================================================


def create_context_source() -> "BedrockContextSource | LocalContextSource":
    """Create context source for runbook/past-incident retrieval.

    Uses Bedrock KB when ``BEDROCK_KB_ID`` is set.  In LOCAL mode without
    a KB, falls back to :class:`LocalContextSource` (keyword search over
    scenario context files).  Raises in PRODUCTION mode without a KB.
    """
    config = get_config()

    if config.bedrock_kb_id:
        logger.info(f"Using Bedrock KB for context: {config.bedrock_kb_id}")
        return BedrockContextSource(config.bedrock_kb_id, config.region)

    if config.mode == DataSourceMode.LOCAL:
        scenarios_dir = Path(__file__).resolve().parent.parent / "scenarios"
        logger.info(
            f"BEDROCK_KB_ID not set — using local context files from {scenarios_dir}"
        )
        return LocalContextSource(scenarios_dir)

    raise RuntimeError(
        "BEDROCK_KB_ID is required for context retrieval in production mode. "
        "Set the environment variable to your Bedrock Knowledge Base ID."
    )


def create_log_search_source(
    scenarios_dir: Optional[Path] = None,
) -> "LocalLogSearchSource | AthenaLogSearchSource | CloudWatchLogSearchSource":
    """Create log search source based on configured mode."""
    config = get_config()

    if config.mode == DataSourceMode.LOCAL:
        if scenarios_dir is None:
            scenarios_dir = Path(__file__).parent.parent / "scenarios"
        logger.info(f"Using LOCAL log search: {scenarios_dir}")
        return LocalLogSearchSource(scenarios_dir)

    # Production mode - use configured backend
    if config.log_search_backend == LogSearchBackend.ATHENA:
        logger.info(
            f"Using S3+Athena log search: {config.athena_database}.{config.athena_table}"
        )
        return AthenaLogSearchSource(
            database=config.athena_database,
            table=config.athena_table,
            output_location=config.athena_output_location,
            region=config.region,
        )
    elif config.log_search_backend == LogSearchBackend.OPENSEARCH:
        logger.info(
            f"Using OpenSearch log search: {config.opensearch_endpoint}/{config.opensearch_index}"
        )
        return OpenSearchLogSearchSource(
            endpoint=config.opensearch_endpoint,
            index=config.opensearch_index,
            auth_mode=config.opensearch_auth_mode or "iam",
            region=config.region,
            username=config.opensearch_username,
            password=config.opensearch_password,
            serverless=config.opensearch_serverless,
        )
    else:
        log_source = (
            config.cloudwatch_log_group_prefix or config.cloudwatch_log_group_names
        )
        logger.info(f"Using CloudWatch log search: {log_source}")
        return CloudWatchLogSearchSource(
            log_group_names=config.cloudwatch_log_group_names,
            log_group_prefix=config.cloudwatch_log_group_prefix,
            region=config.region,
        )
