"""Shared parsing utilities for timestamp and service-name handling."""

import re
from datetime import datetime
from typing import Optional, Set

# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

_TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
]


def parse_timestamp(ts_value) -> Optional[datetime]:
    """Parse various timestamp formats to datetime.

    Handles:
    - ISO 8601 strings (with/without Z, with/without microseconds)
    - Space-separated datetime strings
    - Epoch milliseconds (int/float)
    - Timezone offset stripping (+00:00)

    Returns None if the value cannot be parsed.
    """
    if ts_value is None:
        return None

    # Numeric: epoch millis
    if isinstance(ts_value, (int, float)):
        try:
            return datetime.fromtimestamp(ts_value / 1000)
        except (ValueError, OSError):
            return None

    ts_str = str(ts_value)
    if not ts_str:
        return None

    # Normalize: remove timezone suffix for parsing
    ts_clean = ts_str.rstrip("Z").split("+")[0]

    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(ts_clean, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Service name word splitting
# ---------------------------------------------------------------------------

_SERVICE_SPLIT_RE = re.compile(r"[\s/\-_]+")


def parse_service_words(service_name: str) -> Set[str]:
    """Split a service name into searchable words.

    Splits on whitespace, slashes, hyphens, and underscores.
    Filters out words with 2 or fewer characters.
    """
    return {w.lower() for w in _SERVICE_SPLIT_RE.split(service_name) if len(w) > 2}
