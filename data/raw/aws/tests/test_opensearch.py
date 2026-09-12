"""
Tests for OpenSearch data source.

Tests query construction, response parsing, service filtering,
timestamp handling, config validation, and factory wiring.
All tests mock the OpenSearch client — no live cluster required.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_sources.opensearch import OpenSearchDataSource
from data_sources.base import SearchResponse

# Test credentials for local Docker OpenSearch (DISABLE_SECURITY_PLUGIN=true)
_TEST_USER = os.environ.get("OPENSEARCH_TEST_USER", "admin")
_TEST_PASS = os.environ.get("OPENSEARCH_TEST_PASS", "admin")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_opensearch_client():
    """Return a mock OpenSearch client with a canned search response."""
    client = MagicMock()
    client.search.return_value = {
        "hits": {
            "total": {"value": 3, "relation": "eq"},
            "hits": [
                {
                    "_index": "rca-logs",
                    "_id": "abc1",
                    "_source": {
                        "timestamp": "2024-03-15T14:05:00.000Z",
                        "service": "pricing-service",
                        "message": "Connection timeout after 30s",
                    },
                },
                {
                    "_index": "rca-logs",
                    "_id": "abc2",
                    "_source": {
                        "timestamp": "2024-03-15T14:06:00.000Z",
                        "service": "pricing-service",
                        "message": "Retry timeout on upstream call",
                    },
                },
                {
                    "_index": "rca-logs",
                    "_id": "abc3",
                    "_source": {
                        "timestamp": "2024-03-15T14:07:00.000Z",
                        "service": "order-service",
                        "message": "timeout waiting for pricing-service response",
                    },
                },
            ],
        }
    }
    return client


@pytest.fixture
def datasource(mock_opensearch_client):
    """OpenSearchDataSource with the client pre-injected (no network)."""
    ds = OpenSearchDataSource(
        endpoint="https://test-domain.us-east-1.es.amazonaws.com",
        index="rca-logs",
        auth_mode="basic",
        username=_TEST_USER,
        password=_TEST_PASS,
    )
    ds._client = mock_opensearch_client
    return ds


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


class TestQueryConstruction:
    def test_basic_query_structure(self, datasource):
        """Query has time range, match, sort, and track_total_hits."""
        body = datasource._build_query(
            query="timeout",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            filters=None,
            limit=10,
        )

        must = body["query"]["bool"]["must"]
        assert len(must) == 2  # range + match

        # Time range
        range_clause = must[0]["range"]["timestamp"]
        assert range_clause["gte"] == "2024-03-15T14:00:00"
        assert range_clause["lte"] == "2024-03-15T14:30:00"

        # Match
        assert must[1]["match"]["message"]["query"] == "timeout"
        assert must[1]["match"]["message"]["operator"] == "and"

        # Sort ascending
        assert body["sort"] == [{"timestamp": {"order": "asc"}}]

        # track_total_hits
        assert body["track_total_hits"] is True

    def test_service_filter_word_based(self, datasource):
        """Service filter splits into words and uses wildcard matching."""
        body = datasource._build_query(
            query="error",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            filters={"service": "Staffing/Scheduling"},
            limit=10,
        )

        must = body["query"]["bool"]["must"]
        # range + match + service bool
        assert len(must) == 3

        service_bool = must[2]["bool"]
        should = service_bool["should"]
        assert service_bool["minimum_should_match"] == 1

        wildcard_values = [list(s["wildcard"].values())[0] for s in should]
        assert "*staffing*" in wildcard_values
        assert "*scheduling*" in wildcard_values

    def test_service_filter_short_words_excluded(self, datasource):
        """Words <= 2 chars are excluded from service filter."""
        body = datasource._build_query(
            query="error",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            filters={"service": "a-pricing"},
            limit=10,
        )

        must = body["query"]["bool"]["must"]
        service_bool = must[2]["bool"]
        wildcard_values = [
            list(s["wildcard"].values())[0] for s in service_bool["should"]
        ]
        # "a" is <= 2 chars and should be excluded
        assert "*pricing*" in wildcard_values
        assert len(wildcard_values) == 1

    def test_level_filter(self, datasource):
        """Level filter adds a term clause using the level_field."""
        body = datasource._build_query(
            query="error",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            filters={"level": "error"},
            limit=10,
        )

        must = body["query"]["bool"]["must"]
        assert len(must) == 3  # range + match + level term
        assert must[2]["term"]["level"] == "ERROR"

    def test_level_filter_with_custom_field(self):
        """Level filter uses configurable level_field, not derived from service_field."""
        ds = OpenSearchDataSource(
            endpoint="https://example.com",
            index="logs",
            auth_mode="basic",
            username=_TEST_USER,
            password=_TEST_PASS,
            service_field="svc_name",
            level_field="log_level",
        )
        body = ds._build_query(
            query="error",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            filters={"level": "error"},
            limit=10,
        )
        must = body["query"]["bool"]["must"]
        assert must[2]["term"]["log_level"] == "ERROR"

    def test_service_filter_escapes_wildcards(self, datasource):
        """Wildcard special chars in service names are escaped."""
        body = datasource._build_query(
            query="error",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            filters={"service": "price*service"},
            limit=10,
        )
        must = body["query"]["bool"]["must"]
        service_bool = must[2]["bool"]
        wildcard_values = [
            list(s["wildcard"].values())[0] for s in service_bool["should"]
        ]
        # "price*service" splits to ["price*service"] (no split chars)
        # The * inside should be escaped
        assert all("\\*" in v or "*" not in v.strip("*") for v in wildcard_values)

    def test_size_includes_overflow(self, datasource):
        """Requested size includes +100 for total_matches estimation."""
        body = datasource._build_query(
            query="x",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            filters=None,
            limit=10,
        )
        assert body["size"] == 110


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestResponseParsing:
    def test_search_returns_search_response(self, datasource):
        """search() returns a valid SearchResponse."""
        result = datasource.search(
            query="timeout",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
        )
        assert isinstance(result, SearchResponse)
        assert result.total_matches == 3
        assert len(result.results) == 3
        assert result.query == "timeout"
        assert result.time_start == datetime(2024, 3, 15, 14, 0)
        assert result.time_end == datetime(2024, 3, 15, 14, 30)

    def test_result_fields_populated(self, datasource):
        """Each SearchResult has source, content, timestamp, metadata."""
        result = datasource.search(
            query="timeout",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
        )
        first = result.results[0]
        assert first.source == "pricing-service"
        assert "timeout" in first.content.lower()
        assert first.timestamp == datetime(2024, 3, 15, 14, 5)
        assert first.metadata["index"] == "rca-logs"
        assert first.metadata["id"] == "abc1"

    def test_truncation_flag(self, datasource, mock_opensearch_client):
        """truncated=True when total_matches > limit."""
        result = datasource.search(
            query="timeout",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
            limit=2,
        )
        assert result.truncated is True
        assert len(result.results) == 2
        assert result.total_matches == 3

    def test_empty_response(self, datasource, mock_opensearch_client):
        """Empty results returned cleanly."""
        mock_opensearch_client.search.return_value = {
            "hits": {"total": {"value": 0}, "hits": []}
        }
        result = datasource.search(
            query="nonexistent",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
        )
        assert result.total_matches == 0
        assert result.results == []
        assert result.truncated is False

    def test_error_returns_empty_response(self, datasource, mock_opensearch_client):
        """Client exception returns empty SearchResponse, not a raise."""
        mock_opensearch_client.search.side_effect = Exception("Connection refused")
        result = datasource.search(
            query="timeout",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 30),
        )
        assert result.total_matches == 0
        assert result.results == []


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


class TestTimestampParsing:
    def test_iso_with_millis(self, datasource):
        assert datasource._parse_timestamp("2024-03-15T14:05:00.123Z") == datetime(
            2024, 3, 15, 14, 5, 0, 123000
        )

    def test_iso_without_millis(self, datasource):
        assert datasource._parse_timestamp("2024-03-15T14:05:00") == datetime(
            2024, 3, 15, 14, 5
        )

    def test_space_separated(self, datasource):
        assert datasource._parse_timestamp("2024-03-15 14:05:00") == datetime(
            2024, 3, 15, 14, 5
        )

    def test_epoch_millis(self, datasource):
        # 2024-03-15T14:05:00 UTC ≈ 1710511500000 ms
        ts = datasource._parse_timestamp(1710511500000)
        assert ts is not None
        assert ts.year == 2024

    def test_none_input(self, datasource):
        assert datasource._parse_timestamp(None) is None

    def test_unparseable_string(self, datasource):
        assert datasource._parse_timestamp("not-a-timestamp") is None

    def test_iso_with_timezone_offset(self, datasource):
        ts = datasource._parse_timestamp("2024-03-15T14:05:00.000+00:00")
        assert ts == datetime(2024, 3, 15, 14, 5)


# ---------------------------------------------------------------------------
# Config & factory wiring
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_opensearch_backend_in_enum(self):
        from config import LogSearchBackend

        assert LogSearchBackend.OPENSEARCH.value == "opensearch"

    def test_config_from_env_opensearch(self):
        from config import Config, DataSourceMode, LogSearchBackend, reset_config

        reset_config()

        env = {
            "RCA_AGENT_MODE": "production",
            "LOG_SEARCH_BACKEND": "opensearch",
            "OPENSEARCH_ENDPOINT": "https://my-domain.us-east-1.es.amazonaws.com",
            "OPENSEARCH_INDEX": "my-logs",
            "OPENSEARCH_AUTH_MODE": "iam",
            "OPENSEARCH_SERVERLESS": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            reset_config()
            cfg = Config.from_env()

        assert cfg.mode == DataSourceMode.PRODUCTION
        assert cfg.log_search_backend == LogSearchBackend.OPENSEARCH
        assert cfg.opensearch_endpoint == "https://my-domain.us-east-1.es.amazonaws.com"
        assert cfg.opensearch_index == "my-logs"
        assert cfg.opensearch_auth_mode == "iam"
        assert cfg.opensearch_serverless is True

    def test_config_validates_missing_endpoint(self):
        from config import Config, DataSourceMode, LogSearchBackend

        cfg = Config(
            mode=DataSourceMode.PRODUCTION,
            region="us-east-1",
            model_id="test",
            max_tokens=4096,
            log_level="INFO",
            scenarios_dir=None,
            log_search_backend=LogSearchBackend.OPENSEARCH,
            bedrock_kb_id=None,
            cloudwatch_log_group_names=None,
            cloudwatch_log_group_prefix=None,
            athena_database=None,
            athena_table=None,
            athena_output_location=None,
            opensearch_endpoint=None,
            opensearch_index="rca-logs",
            opensearch_auth_mode="iam",
            opensearch_username=None,
            opensearch_password=None,
            opensearch_serverless=False,
            checkpoint_backend="memory",
            checkpoint_table_name=None,
            checkpoint_sqlite_path="./checkpoints.db",
            otel_enabled=False,
            otel_service_name="test",
            otel_exporter_endpoint=None,
            enabled_tools=None,
            memory_id=None,
            agent_config_table=None,
            agent_name="rca-agent",
        )
        errors = cfg.validate()
        assert any("OPENSEARCH_ENDPOINT" in e for e in errors)

    def test_config_validates_basic_auth_credentials(self):
        from config import Config, DataSourceMode, LogSearchBackend

        cfg = Config(
            mode=DataSourceMode.PRODUCTION,
            region="us-east-1",
            model_id="test",
            max_tokens=4096,
            log_level="INFO",
            scenarios_dir=None,
            log_search_backend=LogSearchBackend.OPENSEARCH,
            bedrock_kb_id=None,
            cloudwatch_log_group_names=None,
            cloudwatch_log_group_prefix=None,
            athena_database=None,
            athena_table=None,
            athena_output_location=None,
            opensearch_endpoint="https://example.com",
            opensearch_index="rca-logs",
            opensearch_auth_mode="basic",
            opensearch_username=None,
            opensearch_password=None,
            opensearch_serverless=False,
            checkpoint_backend="memory",
            checkpoint_table_name=None,
            checkpoint_sqlite_path="./checkpoints.db",
            otel_enabled=False,
            otel_service_name="test",
            otel_exporter_endpoint=None,
            enabled_tools=None,
            memory_id=None,
            agent_config_table=None,
            agent_name="rca-agent",
        )
        errors = cfg.validate()
        assert any("OPENSEARCH_USERNAME" in e for e in errors)
        assert any("OPENSEARCH_PASSWORD" in e for e in errors)

    def test_factory_creates_opensearch_source(self):
        from config import (
            Config,
            DataSourceMode,
            LogSearchBackend,
            set_config,
            reset_config,
        )

        reset_config()
        cfg = Config(
            mode=DataSourceMode.PRODUCTION,
            region="us-east-1",
            model_id="test",
            max_tokens=4096,
            log_level="INFO",
            scenarios_dir=None,
            log_search_backend=LogSearchBackend.OPENSEARCH,
            bedrock_kb_id=None,
            cloudwatch_log_group_names=None,
            cloudwatch_log_group_prefix=None,
            athena_database=None,
            athena_table=None,
            athena_output_location=None,
            opensearch_endpoint="https://example.com",
            opensearch_index="rca-logs",
            opensearch_auth_mode="basic",
            opensearch_username=_TEST_USER,
            opensearch_password=_TEST_PASS,
            opensearch_serverless=False,
            checkpoint_backend="memory",
            checkpoint_table_name=None,
            checkpoint_sqlite_path="./checkpoints.db",
            otel_enabled=False,
            otel_service_name="test",
            otel_exporter_endpoint=None,
            enabled_tools=None,
            memory_id=None,
            agent_config_table=None,
            agent_name="rca-agent",
        )
        set_config(cfg)

        from data_source_factory import (
            create_log_search_source,
            OpenSearchLogSearchSource,
        )

        source = create_log_search_source()
        assert isinstance(source, OpenSearchLogSearchSource)

        reset_config()


# ---------------------------------------------------------------------------
# Client creation
# ---------------------------------------------------------------------------


class TestClientCreation:
    def test_basic_auth_requires_credentials(self):
        ds = OpenSearchDataSource(
            endpoint="https://example.com",
            index="logs",
            auth_mode="basic",
        )
        # Mock opensearchpy so the import succeeds, then hit validation
        mock_os_module = MagicMock()
        with patch.dict("sys.modules", {"opensearchpy": mock_os_module}):
            with pytest.raises(ValueError, match="username and password required"):
                ds._create_client()

    def test_unknown_auth_mode_raises(self):
        ds = OpenSearchDataSource(
            endpoint="https://example.com",
            index="logs",
            auth_mode="kerberos",
        )
        mock_os_module = MagicMock()
        with patch.dict("sys.modules", {"opensearchpy": mock_os_module}):
            with pytest.raises(ValueError, match="Unknown auth_mode"):
                ds._create_client()

    def test_endpoint_trailing_slash_stripped(self):
        ds = OpenSearchDataSource(
            endpoint="https://example.com/",
            index="logs",
        )
        assert ds.endpoint == "https://example.com"


# ---------------------------------------------------------------------------
# Wildcard escaping
# ---------------------------------------------------------------------------


class TestWildcardEscaping:
    def test_escapes_star(self):
        assert OpenSearchDataSource._escape_wildcard("price*svc") == "price\\*svc"

    def test_escapes_question_mark(self):
        assert OpenSearchDataSource._escape_wildcard("svc?name") == "svc\\?name"

    def test_escapes_backslash(self):
        assert OpenSearchDataSource._escape_wildcard("svc\\name") == "svc\\\\name"

    def test_plain_string_unchanged(self):
        assert OpenSearchDataSource._escape_wildcard("pricing") == "pricing"


# ---------------------------------------------------------------------------
# Scenario integration test (mocked OpenSearch, real factory path)
# ---------------------------------------------------------------------------


class TestScenarioIntegration:
    """End-to-end test: config -> factory -> OpenSearchLogSearchSource -> formatted output."""

    def test_full_search_through_factory(self):
        """Simulate a scenario search through the full factory stack with a mocked client."""
        from config import (
            Config,
            DataSourceMode,
            LogSearchBackend,
            set_config,
            reset_config,
        )
        from data_source_factory import create_log_search_source

        reset_config()
        cfg = Config(
            mode=DataSourceMode.PRODUCTION,
            region="us-east-1",
            model_id="test",
            max_tokens=4096,
            log_level="INFO",
            scenarios_dir=None,
            log_search_backend=LogSearchBackend.OPENSEARCH,
            bedrock_kb_id=None,
            cloudwatch_log_group_names=None,
            cloudwatch_log_group_prefix=None,
            athena_database=None,
            athena_table=None,
            athena_output_location=None,
            opensearch_endpoint="https://test.us-east-1.es.amazonaws.com",
            opensearch_index="rca-logs",
            opensearch_auth_mode="basic",
            opensearch_username=_TEST_USER,
            opensearch_password=_TEST_PASS,
            opensearch_serverless=False,
            checkpoint_backend="memory",
            checkpoint_table_name=None,
            checkpoint_sqlite_path="./checkpoints.db",
            otel_enabled=False,
            otel_service_name="test",
            otel_exporter_endpoint=None,
            enabled_tools=None,
            memory_id=None,
            agent_config_table=None,
            agent_name="rca-agent",
        )
        set_config(cfg)

        source = create_log_search_source()
        # set_scenario is a no-op for OpenSearch
        source.set_scenario("volte-call-drop-handover")

        # Inject mock client into the underlying data source
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {
                        "_index": "rca-logs",
                        "_id": "1",
                        "_source": {
                            "timestamp": "2026-03-22T08:30:00.000Z",
                            "service": "staffing",
                            "message": "Schedule conflict detected for morning shift",
                        },
                    },
                    {
                        "_index": "rca-logs",
                        "_id": "2",
                        "_source": {
                            "timestamp": "2026-03-22T08:35:00.000Z",
                            "service": "staffing",
                            "message": "Understaffed alert: only 1 barista for peak hours",
                        },
                    },
                ],
            }
        }
        source.data_source._client = mock_client

        result = source.search(
            query="schedule conflict",
            time_start=datetime(2026, 3, 22, 8, 0),
            time_end=datetime(2026, 3, 22, 9, 0),
            service="Staffing/Scheduling",
            limit=10,
        )

        # Verify formatted output
        assert "Found 2 logs" in result
        assert "Schedule conflict" in result
        assert "staffing" in result

        # Verify the query sent to OpenSearch had service filter
        call_body = mock_client.search.call_args[1]["body"]
        must = call_body["query"]["bool"]["must"]
        assert len(must) == 3  # range + match + service bool
        service_bool = must[2]["bool"]
        wildcard_values = [
            list(s["wildcard"].values())[0] for s in service_bool["should"]
        ]
        assert "*staffing*" in wildcard_values
        assert "*scheduling*" in wildcard_values

        reset_config()
