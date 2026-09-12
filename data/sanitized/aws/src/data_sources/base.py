"""
Abstract base class for data sources.

Implement this interface to connect the Deep Research agent to your data backend.

IMPORTANT: Time windowing is MANDATORY for production-realistic search.
All searches must specify a time range to prevent "easy mode" where
agents can see all incidents at once.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single search result from a data source."""

    source: str  # e.g., "ts-order-service.log", "index/doc_id"
    content: str  # The matching content
    timestamp: Optional[datetime] = None  # Parsed timestamp
    metadata: Optional[dict] = None  # Additional metadata


@dataclass
class SearchResponse:
    """Response from a data source search."""

    results: List[SearchResult]
    total_matches: int
    query: str
    truncated: bool = False  # True if results were limited
    time_start: Optional[datetime] = None  # Time window used
    time_end: Optional[datetime] = None
    quality_score: float = 0.0  # 0-1, higher = more specific search
    error: Optional[str] = None

    def __post_init__(self):
        """Calculate quality score based on result specificity."""
        if self.total_matches == 0:
            self.quality_score = 0.0
        elif self.total_matches <= 5:
            self.quality_score = 1.0  # Very specific - excellent
        elif self.total_matches <= 10:
            self.quality_score = 0.8  # Good specificity
        elif self.total_matches <= 25:
            self.quality_score = 0.5  # Moderate - consider refining
        elif self.total_matches <= 50:
            self.quality_score = 0.3  # Broad - needs refinement
        else:
            self.quality_score = 0.1  # Too broad - almost useless


@dataclass
class TimeWindow:
    """Time window for search queries."""

    start: datetime
    end: datetime

    def contains(self, ts: datetime) -> bool:
        """Check if timestamp falls within this window.

        Handles mixed naive/aware datetimes by stripping tzinfo from all
        sides before comparison. This prevents TypeError when log timestamps
        include 'Z' suffixes (parsed as aware) but the search window is naive.
        """
        # Strip tzinfo to make all comparisons naive — avoids TypeError
        s = self.start.replace(tzinfo=None) if self.start.tzinfo else self.start
        e = self.end.replace(tzinfo=None) if self.end.tzinfo else self.end
        t = ts.replace(tzinfo=None) if ts.tzinfo else ts
        return s <= t <= e

    @classmethod
    def from_strings(
        cls, start: str, end: str, fmt: str = "%Y-%m-%dT%H:%M:%S"
    ) -> "TimeWindow":
        """Create from string timestamps."""
        return cls(
            start=datetime.strptime(start.split(".")[0].split("Z")[0], fmt),
            end=datetime.strptime(end.split(".")[0].split("Z")[0], fmt),
        )

    @classmethod
    def from_iso(cls, start: str, end: str) -> "TimeWindow":
        """Create from ISO format strings."""
        return cls.from_strings(start, end)


class DataSource(ABC):
    """
    Simple abstract base class for context/knowledge retrieval.

    Use this for data sources that don't require time windowing:
    - Bedrock Knowledge Bases (runbooks, documentation)
    - Static context retrieval

    For log search with time constraints, use BaseDataSource instead.
    """

    @abstractmethod
    def search(
        self, query: str, filters: Optional[dict] = None, limit: int = 10
    ) -> list[dict]:
        """
        Search the data source.

        Args:
            query: Search query string
            filters: Optional filters
            limit: Maximum results

        Returns:
            List of matching documents
        """
        pass

    def health_check(self) -> dict:
        """Lightweight connectivity/readiness check.

        Returns:
            {"status": "ok"|"error", "message": "...", "details": {...}}
        """
        return {"status": "ok", "details": {}}


class BaseDataSource(ABC):
    """
    Abstract base class for log/evidence search with time windowing.

    Implement this to connect the agent to your observability stack:
    - OpenSearch / Elasticsearch
    - CloudWatch Logs Insights
    - Splunk / Datadog
    - Local log files

    IMPORTANT: Time windowing is MANDATORY. Searches without time constraints
    allow agents to see all incidents at once, making investigation trivially easy.

    For context retrieval without time constraints (KB, runbooks), use DataSource instead.

    Example:
        class MyOpenSearchSource(BaseDataSource):
            def __init__(self, client, index):
                self.client = client
                self.index = index

            def search(self, query, time_start, time_end, filters=None, limit=10):
                # Your OpenSearch query logic here
                ...
    """

    @abstractmethod
    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        filters: Optional[dict] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Search the data source within a time window.

        Args:
            query: Search query string (single term recommended)
            time_start: Start of time window (REQUIRED)
            time_end: End of time window (REQUIRED)
            filters: Optional filters (e.g., {"service": "pricing-service"})
            limit: Maximum number of results to return

        Returns:
            SearchResponse with matching results and quality score
        """
        pass

    def list_sources(self) -> List[str]:
        """Return available log source names (filenames, log groups, indices, etc.).

        Override in subclasses that can enumerate their sources.
        Used to help investigation agents discover valid service filter values.
        """
        return []

    def health_check(self) -> dict:
        """Lightweight connectivity/readiness check.

        Returns:
            {"status": "ok"|"error", "message": "...", "details": {...}}
        """
        return {"status": "ok", "details": {}}

    def get_tool_schema(self) -> dict:
        """
        Returns the tool schema for Claude to use this data source.

        Time parameters are REQUIRED to prevent "easy mode" investigation.
        """
        return {
            "name": "search_logs",
            "description": """Search service logs for evidence within a specific time window.

IMPORTANT CONSTRAINTS:
- Time window is REQUIRED (time_start and time_end)
- Use ONE specific search term per query (e.g., 'timeout' not 'timeout OR error')
- Service filter is RECOMMENDED for focused results
- Multiple targeted searches are better than one broad query

The quality_score in results indicates search specificity:
- 0.8-1.0: Excellent (few, specific matches)
- 0.5-0.7: Good (moderate matches)
- 0.3-0.4: Broad (consider refining)
- 0.0-0.2: Too broad (refine with service filter or different terms)""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Single search term or short phrase. Use specific terms from your hypothesis.",
                    },
                    "time_start": {
                        "type": "string",
                        "description": "Start of time window in ISO format (e.g., '2024-03-15T14:00:00'). REQUIRED.",
                    },
                    "time_end": {
                        "type": "string",
                        "description": "End of time window in ISO format (e.g., '2024-03-15T14:30:00'). REQUIRED.",
                    },
                    "service": {
                        "type": "string",
                        "description": "Filter to specific service logs (recommended for focused results)",
                    },
                },
                "required": ["query", "time_start", "time_end"],
            },
        }

    def format_results(self, response: SearchResponse) -> str:
        """
        Format search results as a string for the agent.

        Includes quality score to help agent assess search specificity.
        """
        if not response.results:
            return f"No matches for '{response.query}' in time window"

        lines = []

        # Quality indicator
        if response.quality_score >= 0.8:
            quality = "EXCELLENT"
        elif response.quality_score >= 0.5:
            quality = "GOOD"
        elif response.quality_score >= 0.3:
            quality = "BROAD - consider refining"
        else:
            quality = "TOO BROAD - add service filter or more specific terms"

        if response.truncated:
            lines.append(
                f"Found {response.total_matches} matches (showing {len(response.results)}) - Quality: {quality}"
            )
        else:
            lines.append(f"Found {len(response.results)} matches - Quality: {quality}")

        lines.append("")
        for result in response.results:
            ts_str = (
                result.timestamp.strftime("%H:%M:%S")
                if result.timestamp
                else "??:??:??"
            )
            lines.append(f"[{result.source} @ {ts_str}] {result.content}")

        return "\n".join(lines)
