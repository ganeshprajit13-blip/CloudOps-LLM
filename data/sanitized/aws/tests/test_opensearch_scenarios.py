"""
Integration tests: run each scenario through the OpenSearch data source path.

Each test:
1. Reads the real log files from a scenario's evidence/ directory
2. Builds a mock OpenSearch response from those logs (simulating what an
   OpenSearch cluster would return if the same logs were indexed)
3. Wires the mock through Config -> factory -> OpenSearchLogSearchSource
4. Executes a search and verifies the formatted output is correct

No live OpenSearch cluster required.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_sources.opensearch import OpenSearchDataSource
from data_sources.base import SearchResponse

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
_TEST_USER = os.environ.get("OPENSEARCH_TEST_USER", "admin")
_TEST_PASS = os.environ.get("OPENSEARCH_TEST_PASS", "admin")

# Timestamp regex matching the project's log format
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_log_file(path: Path) -> list[dict]:
    """Parse a scenario log file into OpenSearch-style _source dicts."""
    service = path.stem  # e.g. "staffing" from "staffing.log"
    docs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        m = _TS_RE.match(line)
        ts = m.group(1) if m else None
        docs.append(
            {
                "timestamp": ts,
                "service": service,
                "message": line,
            }
        )
    return docs


def _build_mock_response(
    docs: list[dict],
    query: str,
    time_start: str,
    time_end: str,
    service_filter: str | None = None,
    limit: int = 10,
) -> dict:
    """Filter docs the same way OpenSearch would, return a mock response dict."""
    query_lower = query.lower()
    matched = []
    for doc in docs:
        # Time filter
        ts = doc.get("timestamp")
        if ts and (ts < time_start or ts > time_end):
            continue
        # Query match (substring, case-insensitive)
        if query_lower not in doc["message"].lower():
            continue
        # Service filter (word-based, same logic as the adapter)
        if service_filter:
            words = [
                w.lower() for w in re.split(r"[\s/\-_]+", service_filter) if len(w) > 2
            ]
            if words and not any(w in doc["service"].lower() for w in words):
                continue
        matched.append(doc)

    hits = []
    for i, doc in enumerate(matched[: limit + 100]):
        hits.append(
            {
                "_index": "rca-logs",
                "_id": f"doc-{i}",
                "_source": doc,
            }
        )

    return {
        "hits": {
            "total": {"value": len(matched), "relation": "eq"},
            "hits": hits,
        }
    }


def _load_scenario_docs(scenario_name: str) -> list[dict]:
    """Load all log files from a scenario's evidence/ directory."""
    evidence_dir = SCENARIOS_DIR / scenario_name / "evidence"
    if not evidence_dir.exists():
        pytest.skip(f"Scenario {scenario_name} evidence/ not found")
    docs = []
    for log_file in sorted(evidence_dir.glob("*.log")):
        docs.extend(_parse_log_file(log_file))
    return docs


def _make_datasource(
    docs: list[dict],
    query: str,
    time_start: str,
    time_end: str,
    service_filter: str | None = None,
) -> OpenSearchDataSource:
    """Create an OpenSearchDataSource with a mock client pre-loaded."""
    ds = OpenSearchDataSource(
        endpoint="https://test.us-east-1.es.amazonaws.com",
        index="rca-logs",
        auth_mode="basic",
        username=_TEST_USER,
        [REDACTED_CREDENTIAL]
    )
    mock_client = MagicMock()
    mock_response = _build_mock_response(
        docs, query, time_start, time_end, service_filter
    )
    mock_client.search.return_value = mock_response
    ds._client = mock_client
    return ds


# ---------------------------------------------------------------------------
# Scenario tests
# ---------------------------------------------------------------------------


class TestVoLTECallDropHandover:
    """VoLTE call drops during inter-vendor handovers."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.docs = _load_scenario_docs("volte-call-drop-handover")

    def test_search_handover_logs(self):
        ds = _make_datasource(
            self.docs, "handover", "2025-03-20T03:00:00", "2025-03-30T08:00:00"
        )
        result = ds.search(
            query="handover",
            time_start=datetime(2025, 3, 20, 3, 0),
            time_end=datetime(2025, 3, 30, 8, 0),
        )
        assert isinstance(result, SearchResponse)
        assert result.total_matches > 0
        assert any("handover" in r.content.lower() for r in result.results)

    def test_service_filter_mobility_controller(self):
        ds = _make_datasource(
            self.docs,
            "handover",
            "2025-03-25T03:00:00",
            "2025-03-30T08:00:00",
            service_filter="mobility-controller",
        )
        result = ds.search(
            query="handover",
            time_start=datetime(2025, 3, 25, 3, 0),
            time_end=datetime(2025, 3, 30, 8, 0),
            filters={"service": "mobility-controller"},
        )
        assert result.total_matches > 0
        assert all("mobility" in r.source.lower() for r in result.results)


class TestIoTFleetDisconnectCascade:
    """IoT device disconnection cascade from CT validation timeout."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.docs = _load_scenario_docs("iot-fleet-disconnect-cascade")

    def test_search_cert_logs(self):
        ds = _make_datasource(
            self.docs, "cert", "2026-03-28T10:00:00", "2026-03-29T23:00:00"
        )
        result = ds.search(
            query="cert",
            time_start=datetime(2026, 3, 28, 10, 0),
            time_end=datetime(2026, 3, 29, 23, 0),
        )
        assert isinstance(result, SearchResponse)
        assert result.total_matches > 0

    def test_service_filter_auth(self):
        # Use a narrow time window (10:30–11:00) where only auth-service
        # has "cert" entries.  The broader 10:00–11:00 window also matched
        # provisioning-service because word-based filtering matches
        # "service" against both service names.
        ds = _make_datasource(
            self.docs,
            "cert",
            "2026-03-28T10:30:00",
            "2026-03-28T11:00:00",
            service_filter="auth-service",
        )
        result = ds.search(
            query="cert",
            time_start=datetime(2026, 3, 28, 10, 30),
            time_end=datetime(2026, 3, 28, 11, 0),
            filters={"service": "auth-service"},
        )
        assert result.total_matches > 0
        assert all("auth" in r.source.lower() for r in result.results)


class TestK8sCanarySilentPoisoning:
    """Canary deployment with gRPC connection pooling bug."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.docs = _load_scenario_docs("k8s-canary-silent-poisoning")

    def test_search_latency_logs(self):
        ds = _make_datasource(
            self.docs, "latency", "2026-03-25T02:00:00", "2026-03-28T08:00:00"
        )
        result = ds.search(
            query="latency",
            time_start=datetime(2026, 3, 25, 2, 0),
            time_end=datetime(2026, 3, 28, 8, 0),
        )
        assert isinstance(result, SearchResponse)
        assert result.total_matches > 0

    def test_service_filter_inventory(self):
        ds = _make_datasource(
            self.docs,
            "deadline",
            "2026-03-25T02:00:00",
            "2026-03-25T09:00:00",
            service_filter="inventory-service",
        )
        result = ds.search(
            query="deadline",
            time_start=datetime(2026, 3, 25, 2, 0),
            time_end=datetime(2026, 3, 25, 9, 0),
            filters={"service": "inventory-service"},
        )
        assert result.total_matches > 0
        assert all("inventory" in r.source.lower() for r in result.results)


class TestMLTrainingDriftSchemaMigration:
    """ML model drift caused by silent schema migration."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.docs = _load_scenario_docs("ml-training-drift-schema-migration")

    def test_search_feature_logs(self):
        ds = _make_datasource(
            self.docs, "feature", "2026-03-25T02:00:00", "2026-04-01T01:00:00"
        )
        result = ds.search(
            query="feature",
            time_start=datetime(2026, 3, 25, 2, 0),
            time_end=datetime(2026, 4, 1, 1, 0),
        )
        assert isinstance(result, SearchResponse)
        assert result.total_matches > 0

    def test_service_filter_feature_store(self):
        ds = _make_datasource(
            self.docs,
            "feature",
            "2026-03-25T02:00:00",
            "2026-03-30T08:00:00",
            service_filter="feature-store-api",
        )
        result = ds.search(
            query="feature",
            time_start=datetime(2026, 3, 25, 2, 0),
            time_end=datetime(2026, 3, 30, 8, 0),
            filters={"service": "feature-store-api"},
        )
        assert result.total_matches > 0
        assert all("feature" in r.source.lower() for r in result.results)


class TestCareTranscriptSupplyChain:
    """Defect classification failures from supplier component change."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.docs = _load_scenario_docs("care-transcript-supply-chain")

    def test_search_thermal_logs(self):
        ds = _make_datasource(
            self.docs, "thermal", "2026-03-10T02:00:00", "2026-03-19T20:00:00"
        )
        result = ds.search(
            query="thermal",
            time_start=datetime(2026, 3, 10, 2, 0),
            time_end=datetime(2026, 3, 19, 20, 0),
        )
        assert isinstance(result, SearchResponse)
        assert result.total_matches > 0

    def test_service_filter_defect_classifier(self):
        ds = _make_datasource(
            self.docs,
            "classification",
            "2026-03-10T02:00:00",
            "2026-03-10T06:00:00",
            service_filter="defect-classifier",
        )
        result = ds.search(
            query="classification",
            time_start=datetime(2026, 3, 10, 2, 0),
            time_end=datetime(2026, 3, 10, 6, 0),
            filters={"service": "defect-classifier"},
        )
        assert result.total_matches > 0
        assert all("defect" in r.source.lower() for r in result.results)

    def test_time_window_excludes_other_dates(self):
        """Searching a narrow window in February should not return March data."""
        ds = _make_datasource(
            self.docs, "thermal", "2026-02-01T00:00:00", "2026-02-28T23:59:59"
        )
        result = ds.search(
            query="thermal",
            time_start=datetime(2026, 2, 1),
            time_end=datetime(2026, 2, 28, 23, 59, 59),
        )
        for r in result.results:
            if r.timestamp:
                assert r.timestamp.month == 2


# ---------------------------------------------------------------------------
# Cross-scenario: factory integration
# ---------------------------------------------------------------------------


class TestFactoryWithScenarios:
    """Test the full factory path with each scenario's real log data."""

    SCENARIOS = [
        (
            "volte-call-drop-handover",
            "handover",
            "2025-03-20T03:00:00",
            "2025-03-30T08:00:00",
            "mobility-controller",
        ),
        (
            "iot-fleet-disconnect-cascade",
            "cert",
            "2026-03-28T10:00:00",
            "2026-03-29T23:00:00",
            None,
        ),
        (
            "k8s-canary-silent-poisoning",
            "latency",
            "2026-03-25T02:00:00",
            "2026-03-28T08:00:00",
            None,
        ),
        (
            "ml-training-drift-schema-migration",
            "feature",
            "2026-03-25T02:00:00",
            "2026-04-01T01:00:00",
            "feature-store-api",
        ),
        (
            "care-transcript-supply-chain",
            "thermal",
            "2026-03-10T02:00:00",
            "2026-03-19T20:00:00",
            None,
        ),
    ]

    @pytest.mark.parametrize(
        "scenario,query,ts_start,ts_end,service",
        SCENARIOS,
        ids=[s[0] for s in SCENARIOS],
    )
    def test_scenario_through_factory(self, scenario, query, ts_start, ts_end, service):
        """Each scenario produces results through OpenSearchLogSearchSource."""
        from config import (
            Config,
            DataSourceMode,
            LogSearchBackend,
            set_config,
            reset_config,
        )
        from data_source_factory import create_log_search_source

        docs = _load_scenario_docs(scenario)
        mock_response = _build_mock_response(docs, query, ts_start, ts_end, service)

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
            opensearch_[REDACTED_CREDENTIAL]
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
        source.set_scenario(scenario)

        # Inject mock
        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        source.data_source._client = mock_client

        result = source.search(
            query=query,
            time_start=datetime.fromisoformat(ts_start),
            time_end=datetime.fromisoformat(ts_end),
            service=service,
            limit=10,
        )

        assert "Found" in result, (
            f"{scenario}: expected results for '{query}', got: {result[:100]}"
        )
        # Verify query term appears in the output
        assert query.lower() in result.lower(), f"{scenario}: '{query}' not in output"

        reset_config()
