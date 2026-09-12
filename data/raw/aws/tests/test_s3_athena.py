"""
Tests for S3 Athena data source.

Tests parameterized query construction, LIKE wildcard escaping,
ExecutionParameters passing, and SQL injection safety.
All tests mock the Athena client — no AWS credentials required.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_sources.s3_athena import (
    S3AthenaDataSource,
    _escape_like_wildcards,
    _validate_identifier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_athena_client():
    """Return a mock Athena client with canned responses."""
    client = MagicMock()
    client.start_query_execution.return_value = {"QueryExecutionId": "test-123"}
    client.get_query_execution.return_value = {
        "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
    }
    client.get_query_results.return_value = {
        "ResultSet": {
            "Rows": [
                {
                    "Data": [
                        {"VarCharValue": "timestamp"},
                        {"VarCharValue": "service"},
                        {"VarCharValue": "message"},
                    ]
                },
                {
                    "Data": [
                        {"VarCharValue": "2024-03-15T14:05:00"},
                        {"VarCharValue": "pricing-service"},
                        {"VarCharValue": "Connection timeout after 30s"},
                    ]
                },
            ]
        }
    }
    return client


@pytest.fixture
def datasource(mock_athena_client):
    """Return an S3AthenaDataSource with a mocked client."""
    ds = S3AthenaDataSource(
        database="rca_logs",
        table="logs",
        output_location="s3://bucket/results/",
    )
    ds._client = mock_athena_client
    return ds


@pytest.fixture
def time_range():
    """Return a standard time range for tests."""
    return (
        datetime(2024, 3, 15, 14, 0),
        datetime(2024, 3, 15, 14, 30),
    )


# ---------------------------------------------------------------------------
# _escape_like_wildcards
# ---------------------------------------------------------------------------


class TestEscapeLikeWildcards:
    def test_escapes_percent(self):
        assert _escape_like_wildcards("100%") == "100\\%"

    def test_escapes_underscore(self):
        assert _escape_like_wildcards("user_name") == "user\\_name"

    def test_plain_string_unchanged(self):
        assert _escape_like_wildcards("timeout") == "timeout"

    def test_escapes_both(self):
        assert _escape_like_wildcards("50%_done") == "50\\%\\_done"

    def test_escapes_backslash_first(self):
        # Backslash must be escaped before % and _ to avoid double-escaping
        assert _escape_like_wildcards("a\\b") == "a\\\\b"
        assert _escape_like_wildcards("a\\%b") == "a\\\\\\%b"


# ---------------------------------------------------------------------------
# _validate_identifier
# ---------------------------------------------------------------------------


class TestValidateIdentifier:
    def test_valid_identifiers(self):
        assert _validate_identifier("logs", "table") == "logs"
        assert _validate_identifier("rca_logs", "db") == "rca_logs"
        assert _validate_identifier("_private", "col") == "_private"

    def test_rejects_sql_injection(self):
        with pytest.raises(ValueError):
            _validate_identifier("logs; DROP TABLE", "table")

    def test_rejects_quotes(self):
        with pytest.raises(ValueError):
            _validate_identifier("logs'--", "table")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError):
            _validate_identifier("my table", "table")


# ---------------------------------------------------------------------------
# _build_query — parameterized query construction
# ---------------------------------------------------------------------------


class TestBuildQuery:
    def test_basic_query_uses_placeholders(self, datasource, time_range):
        sql, params = datasource._build_query("timeout", time_range[0], time_range[1])
        assert "?" in sql
        assert "timeout" not in sql
        assert len(params) >= 1

    def test_query_param_is_lowercased_with_wildcards(self, datasource, time_range):
        sql, params = datasource._build_query("TimeOut", time_range[0], time_range[1])
        assert params[0] == "%timeout%"

    def test_sql_contains_like_placeholder(self, datasource, time_range):
        sql, params = datasource._build_query("error", time_range[0], time_range[1])
        assert "LOWER(message) LIKE ?" in sql

    def test_service_filter_generates_multiple_params(self, datasource, time_range):
        sql, params = datasource._build_query(
            "timeout",
            time_range[0],
            time_range[1],
            filters={"service": "Staffing/Scheduling"},
        )
        # 1 query param + 2 service word params
        assert len(params) == 3
        assert "%staffing%" in params
        assert "%scheduling%" in params

    def test_level_filter_adds_param(self, datasource, time_range):
        sql, params = datasource._build_query(
            "timeout",
            time_range[0],
            time_range[1],
            filters={"level": "ERROR"},
        )
        assert "LOWER(level) = ?" in sql
        assert "error" in params

    def test_all_filters_combined(self, datasource, time_range):
        sql, params = datasource._build_query(
            "timeout",
            time_range[0],
            time_range[1],
            filters={"service": "pricing-service", "level": "WARN"},
        )
        # 1 query + 1 service word ("pricing" — "service" is >2 chars too) + 1 level
        assert len(params) == 4
        assert params[0] == "%timeout%"
        assert params[-1] == "warn"

    def test_partition_values_embedded_directly(self, datasource, time_range):
        sql, params = datasource._build_query("timeout", time_range[0], time_range[1])
        assert "year = '2024'" in sql
        assert "month = '03'" in sql
        assert "day = '15'" in sql

    def test_timestamp_values_embedded_directly(self, datasource, time_range):
        sql, params = datasource._build_query("timeout", time_range[0], time_range[1])
        assert "2024-03-15T14:00:00" in sql
        assert "2024-03-15T14:30:00" in sql

    def test_sql_injection_in_query_stays_in_params(self, datasource, time_range):
        payload = "'; DROP TABLE logs; --"
        sql, params = datasource._build_query(payload, time_range[0], time_range[1])
        # The injection payload must NOT appear in the SQL string
        assert "DROP" not in sql
        assert "DROP TABLE" not in sql
        # It should only be in the params list (safely parameterized)
        assert any("drop table logs" in p for p in params)

    def test_like_wildcards_in_query_escaped(self, datasource, time_range):
        sql, params = datasource._build_query(
            "100% cpu_usage", time_range[0], time_range[1]
        )
        assert params[0] == "%100\\% cpu\\_usage%"

    def test_limit_embedded_directly(self, datasource, time_range):
        sql, params = datasource._build_query(
            "timeout", time_range[0], time_range[1], limit=10
        )
        assert "LIMIT 110" in sql

    def test_service_words_shorter_than_3_excluded(self, datasource, time_range):
        sql, params = datasource._build_query(
            "timeout",
            time_range[0],
            time_range[1],
            filters={"service": "a-pricing"},
        )
        # "a" is <=2 chars, excluded; "pricing" kept
        assert len(params) == 2  # query + 1 service word
        assert "%pricing%" in params

    def test_multi_day_range(self, datasource):
        sql, params = datasource._build_query(
            "error",
            datetime(2024, 3, 14, 23, 0),
            datetime(2024, 3, 15, 2, 0),
        )
        # Should have multi-day partition logic
        assert "month >" in sql or "month <" in sql


# ---------------------------------------------------------------------------
# Parameterized execution
# ---------------------------------------------------------------------------


class TestParameterizedExecution:
    def test_execution_parameters_passed(
        self, datasource, mock_athena_client, time_range
    ):
        datasource.search("timeout", time_range[0], time_range[1])

        call_kwargs = mock_athena_client.start_query_execution.call_args[1]
        assert "ExecutionParameters" in call_kwargs
        assert isinstance(call_kwargs["ExecutionParameters"], list)
        assert "%timeout%" in call_kwargs["ExecutionParameters"]

    def test_execution_parameters_with_filters(
        self, datasource, mock_athena_client, time_range
    ):
        datasource.search(
            "error",
            time_range[0],
            time_range[1],
            filters={"level": "ERROR"},
        )

        call_kwargs = mock_athena_client.start_query_execution.call_args[1]
        params = call_kwargs["ExecutionParameters"]
        assert "%error%" in params
        assert "error" in params
        assert len(params) == 2

    def test_query_string_has_placeholders(
        self, datasource, mock_athena_client, time_range
    ):
        datasource.search("timeout", time_range[0], time_range[1])

        call_kwargs = mock_athena_client.start_query_execution.call_args[1]
        sql = call_kwargs["QueryString"]
        assert "?" in sql
        assert "timeout" not in sql

    def test_error_returns_empty_response(
        self, datasource, mock_athena_client, time_range
    ):
        mock_athena_client.start_query_execution.side_effect = RuntimeError("fail")
        result = datasource.search("timeout", time_range[0], time_range[1])
        assert result.total_matches == 0
        assert result.results == []

    def test_successful_result_parsing(self, datasource, time_range):
        result = datasource.search("timeout", time_range[0], time_range[1])
        assert result.total_matches == 1
        assert len(result.results) == 1
        assert result.results[0].source == "pricing-service"
        assert "timeout" in result.results[0].content.lower()


# ---------------------------------------------------------------------------
# _escape_sql removed
# ---------------------------------------------------------------------------


class TestEscapeSqlRemoved:
    def test_no_escape_sql_method(self):
        assert not hasattr(S3AthenaDataSource, "_escape_sql")
