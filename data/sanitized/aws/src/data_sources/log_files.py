"""
Log file data source - reads from local log files with time windowing.

This is included as a working example and for demos.
Use this as a reference when implementing your own data source.

IMPORTANT: Time windowing is MANDATORY. This prevents "easy mode" where
agents can see all incidents in a scenario at once.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import BaseDataSource, SearchResponse, SearchResult, TimeWindow

logger = logging.getLogger(__name__)


class LogFileDataSource(BaseDataSource):
    """
    Data source that searches local log files with time windowing.

    Supports both plain text logs and JSON logs.

    Example:
        source = LogFileDataSource("/path/to/logs")
        results = source.search(
            query="timeout",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            filters={"service": "pricing-service"}
        )
    """

    # Common timestamp patterns in log files
    TIMESTAMP_PATTERNS = [
        # ISO format: 2024-03-15T14:00:00.123Z
        (r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", "%Y-%m-%dT%H:%M:%S"),
        # Space-separated: 2024-03-15 14:00:00
        (r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", "%Y-%m-%d %H:%M:%S"),
        # Compact: 20240315140000
        (r"(\d{14})", "%Y%m%d%H%M%S"),
    ]

    def __init__(self, log_directory: str | Path, log_format: str = "auto"):
        """
        Initialize with path to log directory.

        Args:
            log_directory: Path to directory containing log files (.log or .json)
            log_format: "auto", "text", or "json"
        """
        self.log_dir = Path(log_directory)
        if not self.log_dir.exists():
            raise ValueError(f"Log directory does not exist: {log_directory}")
        self.log_format = log_format

    def search(
        self,
        query: str,
        time_start: datetime,
        time_end: datetime,
        filters: Optional[dict] = None,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Search log files for matching lines within time window.

        Args:
            query: Text to search for (case-insensitive, exact substring match).
                   Use specific terms like "timeout" or "cache miss" rather
                   than broad queries. One concept per search works best.
            time_start: Start of time window (REQUIRED)
            time_end: End of time window (REQUIRED)
            filters: Optional {"service": "service-name"} to filter files
            limit: Max results to return

        Returns:
            SearchResponse with matching log lines and quality score
        """
        results = []
        query_lower = query.lower()
        time_window = TimeWindow(start=time_start, end=time_end)

        # Get log files (.log and .json)
        log_files = list(self.log_dir.glob("*.log")) + list(self.log_dir.glob("*.json"))

        # Filter by service if specified (word-based matching)
        service_filter = filters.get("service") if filters else None
        if service_filter:
            from parsing_utils import parse_service_words

            service_words = parse_service_words(service_filter)
            # Match if ANY service word appears in the filename
            log_files = [
                f
                for f in log_files
                if any(word in f.stem.lower() for word in service_words)
            ]

        # Search each file
        for log_file in log_files:
            try:
                file_results = self._search_file(log_file, query_lower, time_window)
                results.extend(file_results)
            except PermissionError:
                logger.warning(f"Permission denied reading {log_file}")
                continue
            except UnicodeDecodeError as e:
                logger.warning(f"Encoding error in {log_file}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error reading {log_file}: {type(e).__name__}: {e}")
                continue

        # Sort by timestamp
        results.sort(key=lambda r: r.timestamp or datetime.min)

        total = len(results)
        truncated = total > limit

        return SearchResponse(
            results=results[:limit],
            total_matches=total,
            query=query,
            truncated=truncated,
            time_start=time_start,
            time_end=time_end,
        )

    def _search_file(
        self, log_file: Path, query_lower: str, time_window: TimeWindow
    ) -> list[SearchResult]:
        """Search a single log file."""
        results = []

        if log_file.suffix == ".json" or self.log_format == "json":
            results = self._search_json_file(log_file, query_lower, time_window)
        else:
            results = self._search_text_file(log_file, query_lower, time_window)

        return results

    def _search_text_file(
        self, log_file: Path, query_lower: str, time_window: TimeWindow
    ) -> list[SearchResult]:
        """Search a plain text log file."""
        results = []

        with open(log_file, "r") as f:
            for line in f:
                # Extract timestamp
                timestamp = self._extract_timestamp(line)

                # Skip if timestamp not in window (or no timestamp found)
                if timestamp is None:
                    continue
                if not time_window.contains(timestamp):
                    continue

                # Check if query matches
                if query_lower in line.lower():
                    results.append(
                        SearchResult(
                            source=log_file.name,
                            content=line.strip(),
                            timestamp=timestamp,
                        )
                    )

        return results

    def _search_json_file(
        self, log_file: Path, query_lower: str, time_window: TimeWindow
    ) -> list[SearchResult]:
        """Search a JSON log file (one JSON object per line)."""
        results = []

        with open(log_file, "r") as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                # Extract timestamp from common fields
                timestamp = self._extract_json_timestamp(record)

                # Skip if timestamp not in window
                if timestamp is None:
                    continue
                if not time_window.contains(timestamp):
                    continue

                # Check if query matches any field
                line_str = json.dumps(record).lower()
                if query_lower in line_str:
                    # Format the content nicely
                    content = self._format_json_log(record)
                    results.append(
                        SearchResult(
                            source=log_file.name,
                            content=content,
                            timestamp=timestamp,
                            metadata=record,
                        )
                    )

        return results

    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Try to extract timestamp from a log line."""
        for pattern, fmt in self.TIMESTAMP_PATTERNS:
            match = re.search(pattern, line)
            if match:
                try:
                    return datetime.strptime(match.group(1), fmt)
                except ValueError:
                    continue
        return None

    def _extract_json_timestamp(self, record: dict) -> Optional[datetime]:
        """Extract timestamp from JSON log record."""
        # Common timestamp field names
        ts_fields = ["timestamp", "@timestamp", "time", "datetime", "ts", "date"]

        for field in ts_fields:
            if field in record:
                ts_value = record[field]
                # Handle epoch milliseconds
                if isinstance(ts_value, (int, float)):
                    if ts_value > 1e12:  # Milliseconds
                        return datetime.fromtimestamp(ts_value / 1000)
                    return datetime.fromtimestamp(ts_value)
                # Handle string timestamps
                if isinstance(ts_value, str):
                    return self._parse_timestamp_string(ts_value)

        return None

    def _parse_timestamp_string(self, ts: str) -> Optional[datetime]:
        """Parse various timestamp string formats."""
        from parsing_utils import parse_timestamp

        return parse_timestamp(ts)

    def list_sources(self) -> list[str]:
        """Return available log filenames (without extension)."""
        files = list(self.log_dir.glob("*.log")) + list(self.log_dir.glob("*.json"))
        return sorted(f.stem for f in files)

    def health_check(self) -> dict:
        """Check that the log directory exists and count available log files."""
        try:
            if not self.log_dir.exists():
                return {
                    "status": "error",
                    "message": f"Directory not found: {self.log_dir}",
                    "details": {"directory": str(self.log_dir)},
                }
            files = list(self.log_dir.glob("*.log")) + list(self.log_dir.glob("*.json"))
            return {
                "status": "ok",
                "details": {
                    "directory": str(self.log_dir),
                    "file_count": len(files),
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "details": {"directory": str(self.log_dir)},
            }

    def _format_json_log(self, record: dict) -> str:
        """Format a JSON log record as readable string."""
        # Extract common fields
        level = record.get("level", record.get("severity", ""))
        service = record.get("service", record.get("source", ""))
        message = record.get("message", record.get("msg", ""))

        if level and service and message:
            return f"{level.upper()} [{service}] {message}"
        elif message:
            return message
        else:
            # Fallback to compact JSON
            return json.dumps(record, separators=(",", ":"))


# Convenience function for quick setup
def create_log_source(path: str | Path, log_format: str = "auto") -> LogFileDataSource:
    """Create a log file data source."""
    return LogFileDataSource(path, log_format)
