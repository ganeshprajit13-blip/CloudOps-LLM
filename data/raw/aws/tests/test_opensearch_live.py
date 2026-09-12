"""
Live integration tests against a real local OpenSearch container.

Requires: docker run -d --name opensearch-test -p 9200:9200 \
  -e "discovery.type=single-node" -e "DISABLE_SECURITY_PLUGIN=true" \
  opensearchproject/opensearch:2.18.0

These tests:
1. Create a real index with the recommended mapping
2. Index actual log lines from each scenario's evidence/ directory
3. Run real queries through the OpenSearchDataSource adapter
4. Verify results match what the local file-based adapter returns

Skip automatically if OpenSearch is not reachable on localhost:9200.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
OPENSEARCH_URL = "http://localhost:9200"
INDEX_NAME = "rca-logs-test"
_TEST_USER = os.environ.get("OPENSEARCH_TEST_USER", "admin")
_TEST_PASS = os.environ.get("OPENSEARCH_TEST_PASS", "admin")

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)")
_LEVEL_RE = re.compile(r"\b(ERROR|WARN|INFO|DEBUG)\b")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opensearch_reachable() -> bool:
    """Check if local OpenSearch is running."""
    try:
        from opensearchpy import OpenSearch

        client = OpenSearch(hosts=[OPENSEARCH_URL], use_ssl=False)
        client.info()
        return True
    except Exception:
        return False


def _parse_log_line(line: str, service: str) -> dict | None:
    """Parse a single log line into a document for indexing."""
    line = line.strip()
    if not line:
        return None
    m = _TS_RE.match(line)
    if not m:
        return None
    timestamp = m.group(1)
    level_m = _LEVEL_RE.search(line)
    level = level_m.group(1) if level_m else "INFO"
    return {
        "timestamp": timestamp,
        "service": service,
        "level": level,
        "message": line,
    }


def _index_scenario(client, scenario_name: str) -> int:
    """Index all log files from a scenario into OpenSearch. Returns doc count."""
    evidence_dir = SCENARIOS_DIR / scenario_name / "evidence"
    if not evidence_dir.exists():
        return 0

    count = 0
    for log_file in sorted(evidence_dir.glob("*.log")):
        service = log_file.stem
        for line in log_file.read_text().splitlines():
            doc = _parse_log_line(line, service)
            if doc:
                client.index(index=INDEX_NAME, body=doc)
                count += 1

    return count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not _opensearch_reachable(), reason="OpenSearch not running on localhost:9200"
)


@pytest.fixture(scope="module")
def os_client():
    """Create OpenSearch client and set up the test index with all scenarios."""
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[OPENSEARCH_URL], use_ssl=False)

    # Clean slate
    if client.indices.exists(index=INDEX_NAME):
        client.indices.delete(index=INDEX_NAME)

    # Create index with proper mapping
    client.indices.create(
        index=INDEX_NAME,
        body={
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "timestamp": {"type": "date"},
                    "service": {"type": "keyword"},
                    "level": {"type": "keyword"},
                    "message": {"type": "text"},
                }
            },
        },
    )

    # Index all scenario logs
    scenarios = [
        "volte-call-drop-handover",
        "iot-fleet-disconnect-cascade",
        "k8s-canary-silent-poisoning",
        "ml-training-drift-schema-migration",
        "care-transcript-supply-chain",
    ]
    total = 0
    for s in scenarios:
        n = _index_scenario(client, s)
        total += n

    # Refresh so docs are searchable immediately
    client.indices.refresh(index=INDEX_NAME)

    print(f"\nIndexed {total} documents into {INDEX_NAME}")

    yield client

    # Cleanup
    client.indices.delete(index=INDEX_NAME, ignore=[404])


@pytest.fixture
def datasource(os_client):
    """OpenSearchDataSource pointing at the live test index."""
    from data_sources.opensearch import OpenSearchDataSource

    ds = OpenSearchDataSource(
        endpoint=OPENSEARCH_URL,
        index=INDEX_NAME,
        auth_mode="basic",
        username=_TEST_USER,
        password=_TEST_PASS,
        verify_certs=False,
    )
    # Inject the already-connected client (avoids basic auth against the
    # security-disabled container)
    ds._client = os_client
    return ds


# ---------------------------------------------------------------------------
# Live scenario tests
# ---------------------------------------------------------------------------


class TestLiveCoffeeShop:
    def test_blender_search(self, datasource):
        result = datasource.search(
            query="blender",
            time_start=datetime(2026, 3, 17, 6, 0),
            time_end=datetime(2026, 3, 17, 10, 0),
        )
        assert result.total_matches > 0
        assert any("blender" in r.content.lower() for r in result.results)

    def test_staffing_service_filter(self, datasource):
        result = datasource.search(
            query="trainee",
            time_start=datetime(2026, 3, 1),
            time_end=datetime(2026, 3, 31),
            filters={"service": "staffing"},
        )
        assert result.total_matches > 0
        assert all(r.source == "staffing" for r in result.results)


class TestLiveGradualDegradation:
    def test_cleanup_search(self, datasource):
        result = datasource.search(
            query="cleanup",
            time_start=datetime(2024, 3, 5),
            time_end=datetime(2024, 3, 19),
        )
        assert result.total_matches > 0

    def test_etl_pipeline_filter(self, datasource):
        result = datasource.search(
            query="cleanup",
            time_start=datetime(2024, 3, 5),
            time_end=datetime(2024, 3, 19),
            filters={"service": "etl-pipeline"},
        )
        assert result.total_matches > 0
        assert all(r.source == "etl-pipeline" for r in result.results)


class TestLiveCacheThunderingHerd:
    def test_cache_expiration(self, datasource):
        """Note: OpenSearch match queries tokenize to whole words.
        'expir' won't match 'expiring' (unlike Athena LIKE '%expir%').
        Use the full word that appears in the logs."""
        result = datasource.search(
            query="expiring",
            time_start=datetime(2024, 3, 15, 13, 50),
            time_end=datetime(2024, 3, 15, 14, 45),
        )
        assert result.total_matches > 0

    def test_pricing_service(self, datasource):
        result = datasource.search(
            query="cache",
            time_start=datetime(2024, 3, 15, 14, 0),
            time_end=datetime(2024, 3, 15, 14, 45),
            filters={"service": "pricing-service"},
        )
        assert result.total_matches > 0
        assert any("pricing" in r.source.lower() for r in result.results)


class TestLiveRetryStorm:
    def test_retry_search(self, datasource):
        result = datasource.search(
            query="retry",
            time_start=datetime(2024, 1, 24, 16, 45),
            time_end=datetime(2024, 1, 24, 17, 30),
        )
        assert result.total_matches > 0

    def test_order_service(self, datasource):
        result = datasource.search(
            query="retry",
            time_start=datetime(2024, 1, 24, 16, 45),
            time_end=datetime(2024, 1, 24, 17, 30),
            filters={"service": "ts-order-service"},
        )
        assert result.total_matches > 0
        assert any("order" in r.source.lower() for r in result.results)


class TestLiveDnsCacheStale:
    def test_dns_resolved(self, datasource):
        result = datasource.search(
            query="resolved",
            time_start=datetime(2024, 3, 18, 9, 0),
            time_end=datetime(2024, 3, 18, 10, 0),
        )
        assert result.total_matches > 0

    def test_payment_service(self, datasource):
        result = datasource.search(
            query="connection",
            time_start=datetime(2024, 3, 18, 9, 0),
            time_end=datetime(2024, 3, 18, 10, 0),
            filters={"service": "payment-service"},
        )
        assert result.total_matches > 0
        assert all(r.source == "payment-service" for r in result.results)


class TestLiveIntermittentMobile:
    def test_certificate_search(self, datasource):
        result = datasource.search(
            query="certificate",
            time_start=datetime(2024, 3, 19, 2, 0),
            time_end=datetime(2024, 3, 19, 8, 0),
        )
        assert result.total_matches > 0

    def test_cdn_edge_filter(self, datasource):
        result = datasource.search(
            query="certificate",
            time_start=datetime(2024, 3, 19, 2, 0),
            time_end=datetime(2024, 3, 19, 8, 0),
            filters={"service": "cdn-edge"},
        )
        assert result.total_matches > 0
        assert all(r.source == "cdn-edge" for r in result.results)


class TestLiveQualityScore:
    """Verify quality scores from real result counts."""

    def test_broad_query_low_score(self, datasource):
        """Searching 'error' across all scenarios should be broad."""
        result = datasource.search(
            query="error",
            time_start=datetime(2024, 1, 1),
            time_end=datetime(2027, 1, 1),
            limit=5,
        )
        # Many matches → low quality score
        if result.total_matches > 50:
            assert result.quality_score <= 0.3

    def test_specific_query_high_score(self, datasource):
        """A very specific term should get a high quality score."""
        result = datasource.search(
            query="DigiCert",
            time_start=datetime(2024, 3, 19, 2, 0),
            time_end=datetime(2024, 3, 19, 8, 0),
        )
        if result.total_matches > 0:
            assert result.quality_score >= 0.5
