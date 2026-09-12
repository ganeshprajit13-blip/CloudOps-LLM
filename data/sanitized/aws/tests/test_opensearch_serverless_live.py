"""
Live integration tests against a real OpenSearch Serverless collection.

Requires:
- An active OpenSearch Serverless collection with scenario logs indexed
- IAM credentials with aoss:* permissions
- Environment variable: OPENSEARCH_SERVERLESS_ENDPOINT

To set up:
    python scripts/ingest_to_opensearch_serverless.py \
        --endpoint $OPENSEARCH_SERVERLESS_ENDPOINT --region us-west-2

Skip automatically if OPENSEARCH_SERVERLESS_ENDPOINT is not set.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

ENDPOINT = os.environ.get("OPENSEARCH_SERVERLESS_ENDPOINT", "")
REGION = os.environ.get("AWS_REGION", "us-west-2")
INDEX_NAME = "rca-logs"

pytestmark = pytest.mark.skipif(
    not ENDPOINT, reason="OPENSEARCH_SERVERLESS_ENDPOINT not set"
)


@pytest.fixture(scope="module")
def datasource():
    """OpenSearchDataSource pointing at the live Serverless collection."""
    from data_sources.opensearch import OpenSearchDataSource

    return OpenSearchDataSource(
        endpoint=ENDPOINT,
        index=INDEX_NAME,
        auth_mode="iam",
        region=REGION,
        serverless=True,
    )


# ---------------------------------------------------------------------------
# Coffee shop mystery
# ---------------------------------------------------------------------------


class TestServerlessCoffeeShop:
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


# ---------------------------------------------------------------------------
# Gradual degradation
# ---------------------------------------------------------------------------


class TestServerlessGradualDegradation:
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
        assert all("etl" in r.source.lower() for r in result.results)


# ---------------------------------------------------------------------------
# Cache thundering herd
# ---------------------------------------------------------------------------


class TestServerlessCacheThunderingHerd:
    def test_cache_expiration(self, datasource):
        """OpenSearch match queries tokenize to whole words.
        'expiring' matches; 'expir' does not (unlike Athena LIKE)."""
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


# ---------------------------------------------------------------------------
# Retry storm
# ---------------------------------------------------------------------------


class TestServerlessRetryStorm:
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


# ---------------------------------------------------------------------------
# DNS cache stale
# ---------------------------------------------------------------------------


class TestServerlessDnsCacheStale:
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
        assert all("payment" in r.source.lower() for r in result.results)


# ---------------------------------------------------------------------------
# Intermittent mobile failures
# ---------------------------------------------------------------------------


class TestServerlessIntermittentMobile:
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
        assert all("cdn" in r.source.lower() for r in result.results)


# ---------------------------------------------------------------------------
# Cross-cutting: quality score and IAM auth validation
# ---------------------------------------------------------------------------


class TestServerlessQualityAndAuth:
    """Verify quality scores and that IAM auth actually works end-to-end."""

    def test_broad_query_low_score(self, datasource):
        """Searching 'error' across all scenarios should be broad."""
        result = datasource.search(
            query="error",
            time_start=datetime(2024, 1, 1),
            time_end=datetime(2027, 1, 1),
            limit=5,
        )
        if result.total_matches > 50:
            assert result.quality_score <= 0.3

    def test_specific_query_high_score(self, datasource):
        result = datasource.search(
            query="DigiCert",
            time_start=datetime(2024, 3, 19, 2, 0),
            time_end=datetime(2024, 3, 19, 8, 0),
        )
        if result.total_matches > 0:
            assert result.quality_score >= 0.5

    def test_time_window_filtering(self, datasource):
        """Narrow time window should exclude other dates."""
        result = datasource.search(
            query="error",
            time_start=datetime(2024, 3, 18, 9, 0),
            time_end=datetime(2024, 3, 18, 10, 0),
        )
        # All results should be from March 18
        for r in result.results:
            if r.timestamp:
                assert r.timestamp.day == 18

    def test_level_filter(self, datasource):
        """Filter by log level should work."""
        result = datasource.search(
            query="error",
            time_start=datetime(2024, 1, 1),
            time_end=datetime(2027, 1, 1),
            filters={"level": "ERROR"},
            limit=5,
        )
        # Should return results (many scenarios have ERROR logs)
        assert result.total_matches > 0
