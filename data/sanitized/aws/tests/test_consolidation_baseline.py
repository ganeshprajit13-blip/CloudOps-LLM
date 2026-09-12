"""
Regression tests for consolidated shared utilities.

Tests the canonical implementations in parsing_utils, stream_formatter,
and rca_agent.build_initial_state, plus the thin wrappers that delegate
to them.  Pure unit tests -- no AWS credentials, no LLM calls, no network.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_source_factory import format_search_results  # noqa: E402
from data_sources.base import BaseDataSource, SearchResponse, SearchResult  # noqa: E402
from parsing_utils import parse_service_words, parse_timestamp  # noqa: E402
from stream_formatter import extract_text_content  # noqa: E402


# ============================================================================
# 1. parse_timestamp (parsing_utils.py) — the single shared implementation
# ============================================================================


class TestParseTimestamp:
    """Test parsing_utils.parse_timestamp — all data sources delegate here."""

    def test_iso_with_millis_and_z(self):
        assert parse_timestamp("2024-03-15T14:05:30.123456Z") == datetime(
            2024, 3, 15, 14, 5, 30, 123456
        )

    def test_iso_without_millis_z(self):
        assert parse_timestamp("2024-03-15T14:05:30Z") == datetime(
            2024, 3, 15, 14, 5, 30
        )

    def test_iso_with_millis_no_z(self):
        assert parse_timestamp("2024-03-15T14:05:30.123456") == datetime(
            2024, 3, 15, 14, 5, 30, 123456
        )

    def test_iso_no_millis_no_z(self):
        assert parse_timestamp("2024-03-15T14:05:30") == datetime(
            2024, 3, 15, 14, 5, 30
        )

    def test_space_separated(self):
        assert parse_timestamp("2024-03-15 14:05:30") == datetime(
            2024, 3, 15, 14, 5, 30
        )

    def test_space_with_millis(self):
        assert parse_timestamp("2024-03-15 14:05:30.123456") == datetime(
            2024, 3, 15, 14, 5, 30, 123456
        )

    def test_strips_timezone_offset(self):
        assert parse_timestamp("2024-03-15T14:05:30.000000+00:00") == datetime(
            2024, 3, 15, 14, 5, 30
        )

    def test_epoch_millis_int(self):
        result = parse_timestamp(1710511500000)
        assert result is not None and result.year == 2024

    def test_epoch_millis_float(self):
        result = parse_timestamp(1710511500000.0)
        assert result is not None and result.year == 2024

    def test_epoch_bad_value_returns_none(self):
        assert parse_timestamp(99999999999999999) is None

    def test_none_returns_none(self):
        assert parse_timestamp(None) is None

    def test_empty_string_returns_none(self):
        assert parse_timestamp("") is None

    def test_garbage_returns_none(self):
        assert parse_timestamp("not-a-timestamp") is None

    def test_numeric_string_not_parsed_as_epoch(self):
        assert parse_timestamp("1710511500000") is None


# ============================================================================
# 2. Wrapper: parse_iso_timestamp raises ValueError on None
# ============================================================================


class TestParseIsoTimestamp:
    """Test the ValueError-raising wrapper in rca_agent."""

    def test_valid_input_parses(self):
        from rca_agent import parse_iso_timestamp

        assert parse_iso_timestamp("2024-03-15T14:05:30Z") == datetime(
            2024, 3, 15, 14, 5, 30
        )

    def test_raises_on_garbage(self):
        from rca_agent import parse_iso_timestamp

        with pytest.raises(ValueError, match="Cannot parse timestamp"):
            parse_iso_timestamp("not-a-timestamp")

    def test_raises_on_empty(self):
        from rca_agent import parse_iso_timestamp

        with pytest.raises(ValueError, match="Cannot parse timestamp"):
            parse_iso_timestamp("")


# ============================================================================
# 3. parse_service_words (parsing_utils.py)
# ============================================================================


class TestParseServiceWords:
    """Test parsing_utils.parse_service_words — all data sources delegate here."""

    def test_slash_separated(self):
        assert parse_service_words("Staffing/Scheduling") == {"staffing", "scheduling"}

    def test_hyphen_separated(self):
        assert parse_service_words("order-processing-service") == {
            "order",
            "processing",
            "service",
        }

    def test_underscore_separated(self):
        assert parse_service_words("payment_gateway_v2") == {"payment", "gateway"}

    def test_space_separated(self):
        assert parse_service_words("API Gateway Service") == {
            "api",
            "gateway",
            "service",
        }

    def test_mixed_delimiters(self):
        assert parse_service_words("auth/user-service_v2 main") == {
            "auth",
            "user",
            "service",
            "main",
        }

    def test_short_words_excluded(self):
        assert parse_service_words("a-b-pricing") == {"pricing"}

    def test_all_short_words(self):
        assert parse_service_words("a/b-c") == set()

    def test_empty_string(self):
        assert parse_service_words("") == set()


class TestServiceFilterIntegration:
    """Verify LogFileDataSource service filtering uses word-based matching."""

    def test_filters_by_service_words(self, tmp_path):
        from data_sources.log_files import LogFileDataSource

        (tmp_path / "pricing-service.log").write_text(
            "2024-03-15T14:05:30Z ERROR connection timeout\n"
        )
        (tmp_path / "order-api.log").write_text(
            "2024-03-15T14:05:30Z ERROR order failed\n"
        )

        ds = LogFileDataSource(tmp_path)
        result = ds.search(
            query="error",
            time_start=datetime(2024, 3, 15, 14, 0, 0),
            time_end=datetime(2024, 3, 15, 15, 0, 0),
            filters={"service": "pricing"},
        )

        sources = {r.source for r in result.results}
        assert "pricing-service" in sources or "pricing-service.log" in sources
        assert "order-api" not in sources and "order-api.log" not in sources


# ============================================================================
# 4. extract_text_content (stream_formatter.py)
# ============================================================================

_EXTRACT_TEXT_CASES = [
    ("string_passthrough", "hello world", "hello world"),
    ("empty_string", "", ""),
    (
        "list_of_text_blocks",
        [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}],
        "hello world",
    ),
    ("list_with_string_blocks", ["hello ", "world"], "hello world"),
    ("list_mixed_dict_and_string", [{"type": "text", "text": "a"}, "b"], "ab"),
    ("dict_without_text_key", [{"type": "image", "url": "..."}], ""),
    ("empty_list", [], ""),
    ("none_input", None, "None"),
    ("int_input", 42, "42"),
    ("list_with_empty_dict", [{}], ""),
]


class TestExtractText:
    """Test extract_text_content (rca_agent._extract_text is a re-export of this)."""

    @pytest.mark.parametrize(
        "name,input_val,expected",
        _EXTRACT_TEXT_CASES,
        ids=[c[0] for c in _EXTRACT_TEXT_CASES],
    )
    def test_extract_text(self, name, input_val, expected):
        assert extract_text_content(input_val) == expected


# ============================================================================
# 5. build_initial_state (rca_agent.py)
# ============================================================================


class TestBuildInitialState:
    """Test the single build_initial_state function all entrypoints share."""

    EXPECTED_KEYS = {
        "messages",
        "incident",
        "incident_time",
        "incident_details",
        "context",
        "enriched_context",
        "current_hypotheses",
        "selected_hypotheses",
        "worker_messages",
        "synthesized_report",
        "scenario_name",
        "investigation_complete",
    }

    def test_keys(self):
        from rca_agent import build_initial_state

        state = build_initial_state("test incident", "test-scenario")
        assert set(state.keys()) == self.EXPECTED_KEYS

    def test_values(self):
        from rca_agent import build_initial_state

        state = build_initial_state("test incident", "test-scenario")
        assert state["incident"] == "test incident"
        assert state["scenario_name"] == "test-scenario"
        assert state["investigation_complete"] is False
        assert state["messages"][0].content == "test incident"
        assert state["incident_time"] is None
        assert state["incident_details"] is None
        assert state["context"] == {}
        assert state["enriched_context"] == ""
        assert state["current_hypotheses"] is None
        assert state["selected_hypotheses"] is None
        assert state["worker_messages"] == []
        assert state["synthesized_report"] == ""

    def test_agentcore_alias_matches(self):
        """agentcore_app._build_initial_state is a re-export of build_initial_state."""
        from agentcore_app import _build_initial_state
        from rca_agent import build_initial_state

        assert _build_initial_state is build_initial_state


# ============================================================================
# 6. format_search_results (data_source_factory.py)
# ============================================================================


class TestFormatSearchResults:
    """Test data_source_factory.format_search_results."""

    def test_error_response(self):
        resp = SearchResponse(
            results=[],
            total_matches=0,
            query="test",
            error="Connection failed",
        )
        output = format_search_results(resp)
        assert output.startswith("SEARCH ERROR: Connection failed")

    def test_no_results(self):
        resp = SearchResponse(
            results=[],
            total_matches=0,
            query="timeout",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 15, 0),
        )
        output = format_search_results(resp)
        assert "No logs found matching 'timeout'" in output

    def test_normal_results(self):
        results = [
            SearchResult(
                source="pricing-service",
                content="Connection timeout",
                timestamp=datetime(2024, 3, 15, 14, 5, 30),
            ),
            SearchResult(
                source="order-api",
                content="Order failed",
                timestamp=datetime(2024, 3, 15, 14, 6, 0),
            ),
        ]
        resp = SearchResponse(
            results=results,
            total_matches=2,
            query="error",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 15, 0),
        )
        output = format_search_results(resp)
        assert "Found 2 logs" in output
        assert "Connection timeout" in output

    def test_truncated_results(self):
        resp = SearchResponse(
            results=[
                SearchResult(
                    source="svc", content="msg", timestamp=datetime(2024, 3, 15, 14, 0)
                )
            ],
            total_matches=50,
            query="test",
            truncated=True,
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 15, 0),
        )
        output = format_search_results(resp)
        assert "49 more results" in output

    def test_result_without_timestamp(self):
        resp = SearchResponse(
            results=[SearchResult(source="x.log", content="boom", timestamp=None)],
            total_matches=1,
            query="boom",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 15, 0),
        )
        output = format_search_results(resp)
        assert "[unknown]" in output


# ============================================================================
# 7. BaseDataSource.format_results (base.py)
# ============================================================================


class TestFormatResultsBase:
    """Test data_sources/base.py:BaseDataSource.format_results."""

    @pytest.fixture
    def datasource(self):
        class ConcreteDS(BaseDataSource):
            def search(self, **kwargs):
                pass

        return ConcreteDS()

    def test_no_results(self, datasource):
        resp = SearchResponse(results=[], total_matches=0, query="test")
        output = datasource.format_results(resp)
        assert "No matches for 'test' in time window" in output

    def test_quality_excellent(self, datasource):
        resp = SearchResponse(
            results=[
                SearchResult(
                    source="s", content="c", timestamp=datetime(2024, 1, 1, 12, 0)
                )
            ],
            total_matches=1,
            query="test",
        )
        output = datasource.format_results(resp)
        assert "EXCELLENT" in output

    def test_quality_good(self, datasource):
        results = [
            SearchResult(source="s", content="c", timestamp=datetime(2024, 1, 1, 12, 0))
            for _ in range(11)
        ]
        resp = SearchResponse(results=results, total_matches=11, query="test")
        output = datasource.format_results(resp)
        assert "GOOD" in output

    def test_quality_broad(self, datasource):
        results = [
            SearchResult(source="s", content="c", timestamp=datetime(2024, 1, 1, 12, 0))
            for _ in range(26)
        ]
        resp = SearchResponse(results=results, total_matches=26, query="test")
        output = datasource.format_results(resp)
        assert "BROAD" in output

    def test_quality_too_broad(self, datasource):
        results = [
            SearchResult(source="s", content="c", timestamp=datetime(2024, 1, 1, 12, 0))
            for _ in range(51)
        ]
        resp = SearchResponse(results=results, total_matches=51, query="test")
        output = datasource.format_results(resp)
        assert "TOO BROAD" in output

    def test_truncated_shows_total(self, datasource):
        results = [
            SearchResult(source="s", content="c", timestamp=datetime(2024, 1, 1, 12, 0))
            for _ in range(5)
        ]
        resp = SearchResponse(
            results=results,
            total_matches=50,
            query="test",
            truncated=True,
        )
        output = datasource.format_results(resp)
        assert "Found 50 matches (showing 5)" in output

    def test_timestamp_formatting(self, datasource):
        resp = SearchResponse(
            results=[
                SearchResult(
                    source="s", content="c", timestamp=datetime(2024, 3, 15, 14, 5, 30)
                )
            ],
            total_matches=1,
            query="test",
        )
        output = datasource.format_results(resp)
        assert "14:05:30" in output

    def test_no_timestamp_shows_placeholder(self, datasource):
        resp = SearchResponse(
            results=[SearchResult(source="s", content="c", timestamp=None)],
            total_matches=1,
            query="test",
        )
        output = datasource.format_results(resp)
        assert "??:??:??" in output
