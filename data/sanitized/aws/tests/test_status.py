"""Tests for the Backend Status endpoint and health checks."""

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Patch heavy imports before loading api module
# ---------------------------------------------------------------------------

_mock_graph = MagicMock()
_mock_graph.get_state.return_value = MagicMock(
    next=None, values={"synthesized_report": "Test report"}
)
_mock_graph.aget_state = AsyncMock(return_value=MagicMock(next=None, values={}))


@pytest.fixture(autouse=True)
def _patch_graph():
    """Patch graph and checkpointer at module level for all tests."""
    with (
        patch("api._graph", _mock_graph),
        patch("api._checkpointer", MagicMock()),
        patch("api._investigations", {}),
    ):
        yield


@pytest.fixture
def client():
    from api import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: LogFileDataSource.health_check
# ---------------------------------------------------------------------------


class TestLogFileHealthCheck:
    def test_healthy_directory(self, tmp_path):
        """health_check returns ok when log files exist."""
        (tmp_path / "app.log").write_text("2024-01-01T00:00:00 test")
        (tmp_path / "db.json").write_text('{"msg":"ok"}')

        from data_sources.log_files import LogFileDataSource

        ds = LogFileDataSource(tmp_path)
        result = ds.health_check()
        assert result["status"] == "ok"
        assert result["details"]["file_count"] == 2

    def test_missing_directory(self, tmp_path):
        """health_check returns error when directory does not exist."""
        # Create and then remove to have a valid path that doesn't exist
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        from data_sources.log_files import LogFileDataSource

        ds = LogFileDataSource(log_dir)
        # Now remove the directory after construction
        log_dir.rmdir()

        result = ds.health_check()
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests: S3AthenaDataSource.health_check
# ---------------------------------------------------------------------------


class TestAthenaHealthCheck:
    def test_table_exists(self):
        """health_check returns ok when Glue table exists."""
        from data_sources.s3_athena import S3AthenaDataSource

        ds = S3AthenaDataSource(
            database="testdb", table="logs", output_location="s3://bucket/out/"
        )

        mock_glue = MagicMock()
        mock_glue.get_table.return_value = {"Table": {"Name": "logs"}}

        with patch("boto3.client", return_value=mock_glue):
            result = ds.health_check()

        assert result["status"] == "ok"
        assert result["details"]["database"] == "testdb"
        assert result["details"]["table"] == "logs"

    def test_table_missing(self):
        """health_check returns error when Glue table is not found."""
        from data_sources.s3_athena import S3AthenaDataSource

        ds = S3AthenaDataSource(
            database="testdb", table="missing", output_location="s3://bucket/out/"
        )

        mock_glue = MagicMock()
        mock_glue.get_table.side_effect = Exception("EntityNotFoundException")

        with patch("boto3.client", return_value=mock_glue):
            result = ds.health_check()

        assert result["status"] == "error"
        assert "EntityNotFoundException" in result["message"]


# ---------------------------------------------------------------------------
# Tests: CloudWatchLogsDataSource.health_check
# ---------------------------------------------------------------------------


class TestCloudWatchHealthCheck:
    def test_log_groups_found(self):
        """health_check returns ok when log groups exist."""
        from data_sources.cloudwatch_logs import CloudWatchLogsDataSource

        ds = CloudWatchLogsDataSource(
            log_group_names=["/aws/lambda/func1"], region="us-east-1"
        )

        mock_client = MagicMock()
        mock_client.describe_log_groups.return_value = {
            "logGroups": [{"logGroupName": "/aws/lambda/func1"}]
        }

        ds._client = mock_client
        result = ds.health_check()
        assert result["status"] == "ok"
        assert result["details"]["log_group_count"] == 1

    def test_no_log_groups_configured(self):
        """health_check returns error when no groups or prefix configured."""
        from data_sources.cloudwatch_logs import CloudWatchLogsDataSource

        ds = CloudWatchLogsDataSource(region="us-east-1")
        result = ds.health_check()
        assert result["status"] == "error"
        assert "No log groups" in result["message"]


# ---------------------------------------------------------------------------
# Tests: OpenSearchDataSource.health_check
# ---------------------------------------------------------------------------


class TestOpenSearchHealthCheck:
    def test_index_exists(self):
        """health_check returns ok when cluster reachable and index exists."""
        from data_sources.opensearch import OpenSearchDataSource

        ds = OpenSearchDataSource(
            endpoint="https://test.us-east-1.es.amazonaws.com",
            index="rca-logs",
            auth_mode="basic",
            username="admin",  # nosec B106 - test fixture with mocked client, not real credentials
            password="admin",  # nosec B105 - test fixture with mocked client, not real credentials
        )

        mock_client = MagicMock()
        mock_client.info.return_value = {"cluster_name": "test"}
        mock_client.indices.exists.return_value = True

        ds._client = mock_client
        result = ds.health_check()
        assert result["status"] == "ok"
        assert result["details"]["index_exists"] is True

    def test_index_missing(self):
        """health_check returns error when index doesn't exist."""
        from data_sources.opensearch import OpenSearchDataSource

        ds = OpenSearchDataSource(
            endpoint="https://test.us-east-1.es.amazonaws.com",
            index="rca-logs",
            auth_mode="basic",
            username="admin",  # nosec B106 - test fixture with mocked client, not real credentials
            password="admin",  # nosec B105 - test fixture with mocked client, not real credentials
        )

        mock_client = MagicMock()
        mock_client.info.return_value = {"cluster_name": "test"}
        mock_client.indices.exists.return_value = False

        ds._client = mock_client
        result = ds.health_check()
        assert result["status"] == "error"
        assert "does not exist" in result["message"]

    def test_connection_failure(self):
        """health_check returns error when cluster unreachable."""
        from data_sources.opensearch import OpenSearchDataSource

        ds = OpenSearchDataSource(
            endpoint="https://test.us-east-1.es.amazonaws.com",
            index="rca-logs",
            auth_mode="basic",
            username="admin",  # nosec B106 - test fixture with mocked client, not real credentials
            password="admin",  # nosec B105 - test fixture with mocked client, not real credentials
        )

        mock_client = MagicMock()
        mock_client.info.side_effect = ConnectionError("refused")

        ds._client = mock_client
        result = ds.health_check()
        assert result["status"] == "error"
        assert "refused" in result["message"]


# ---------------------------------------------------------------------------
# Tests: Factory wrapper health checks
# ---------------------------------------------------------------------------


class TestFactoryWrapperHealthChecks:
    def test_local_log_search_healthy(self, tmp_path):
        """LocalLogSearchSource.health_check checks scenarios directory."""
        # Create scenario with evidence dir
        scenario_dir = tmp_path / "test-scenario" / "evidence"
        scenario_dir.mkdir(parents=True)

        from data_source_factory import LocalLogSearchSource

        source = LocalLogSearchSource(tmp_path)
        result = source.health_check()
        assert result["status"] == "ok"
        assert result["details"]["scenarios_with_evidence"] == 1

    def test_local_context_healthy(self, tmp_path):
        """LocalContextSource.health_check checks scenarios with context."""
        context_dir = tmp_path / "test-scenario" / "context"
        context_dir.mkdir(parents=True)

        from data_source_factory import LocalContextSource

        source = LocalContextSource(tmp_path)
        result = source.health_check()
        assert result["status"] == "ok"
        assert result["details"]["scenarios_with_context"] == 1

    def test_bedrock_kb_healthy(self):
        """BedrockContextSource.health_check calls retrieve()."""
        from data_source_factory import BedrockContextSource

        source = BedrockContextSource(kb_id="test-kb-id", region="us-east-1")
        mock_client = MagicMock()
        mock_client.retrieve.return_value = {
            "retrievalResults": [{"content": {"text": "chunk"}}]
        }
        source._client = mock_client

        result = source.health_check()
        assert result["status"] == "ok"
        assert result["details"]["kb_id"] == "test-kb-id"
        assert result["details"]["has_data"] is True

    def test_bedrock_kb_unreachable(self):
        """BedrockContextSource.health_check returns error on failure."""
        from data_source_factory import BedrockContextSource

        source = BedrockContextSource(kb_id="test-kb-id", region="us-east-1")
        mock_client = MagicMock()
        mock_client.retrieve.side_effect = Exception("AccessDenied")
        source._client = mock_client

        result = source.health_check()
        assert result["status"] == "error"
        assert "AccessDenied" in result["message"]


# ---------------------------------------------------------------------------
# Tests: /api/config/status endpoint
# ---------------------------------------------------------------------------


class TestConfigStatusEndpoint:
    def test_returns_status(self, client):
        """GET /api/config/status returns backend status."""
        mock_result = {
            "agent": {"mode": "local", "region": "us-east-1"},
            "backends": {
                "log_search": {"type": "local", "status": "ok", "details": {}},
                "context_source": {
                    "type": "local_files",
                    "status": "ok",
                    "details": {},
                },
                "checkpoint": {"type": "memory", "status": "ok", "details": {}},
            },
        }

        with patch("status.get_system_status", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = mock_result
            response = client.get("/api/config/status")

        assert response.status_code == 200
        data = response.json()
        assert data["agent"]["mode"] == "local"
        assert "log_search" in data["backends"]
        assert "context_source" in data["backends"]
        assert "checkpoint" in data["backends"]


# ---------------------------------------------------------------------------
# Tests: get_system_status aggregation
# ---------------------------------------------------------------------------


class TestGetSystemStatus:
    def test_aggregates_backends(self):
        """get_system_status aggregates all backend health checks."""
        from config import Config, DataSourceMode

        mock_config = Config(
            mode=DataSourceMode.LOCAL,
            region="us-east-1",
            model_id="test-model",
            max_tokens=4096,
            log_level="INFO",
            scenarios_dir=None,
            log_search_backend=None,
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

        mock_log_source = MagicMock()
        mock_log_source.health_check.return_value = {
            "status": "ok",
            "details": {"file_count": 5},
        }

        mock_context_source = MagicMock()
        mock_context_source.health_check.return_value = {
            "status": "ok",
            "details": {"scenarios_with_context": 3},
        }

        import status

        # Clear cache
        status._cache = None
        status._cache_time = 0.0

        with (
            patch("status.get_config", return_value=mock_config),
            patch(
                "status._check_log_search",
                return_value={"type": "local", "status": "ok", "details": {}},
            ),
            patch(
                "status._check_context_source",
                return_value={"type": "local_files", "status": "ok", "details": {}},
            ),
            patch(
                "status._check_checkpoint",
                return_value={"type": "memory", "status": "ok", "details": {}},
            ),
        ):
            import asyncio

            result = asyncio.run(status.get_system_status())

        assert result["agent"]["mode"] == "local"
        assert result["agent"]["region"] == "us-east-1"
        assert result["backends"]["log_search"]["status"] == "ok"
        assert result["backends"]["context_source"]["status"] == "ok"
        assert result["backends"]["checkpoint"]["status"] == "ok"
