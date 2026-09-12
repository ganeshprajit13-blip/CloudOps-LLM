"""Tests for the checkpointer factory."""

import os
from unittest.mock import MagicMock, patch

import pytest

from checkpoint import create_checkpointer
from config import Config, DataSourceMode, reset_config, set_config


@pytest.fixture(autouse=True)
def _reset():
    """Reset global config between tests."""
    reset_config()
    yield
    reset_config()


def _make_config(**overrides):
    """Create a Config with sensible defaults, applying overrides."""
    defaults = dict(
        mode=DataSourceMode.LOCAL,
        region="us-east-1",
        model_id="test-model",
        max_tokens=1024,
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
        opensearch_index=None,
        opensearch_auth_mode=None,
        opensearch_username=None,
        opensearch_password=None,
        opensearch_serverless=False,
        checkpoint_backend="memory",
        checkpoint_table_name=None,
        checkpoint_sqlite_path="./test_checkpoints.db",
        otel_enabled=False,
        otel_service_name="test",
        otel_exporter_endpoint=None,
        enabled_tools=None,
        memory_id=None,
        agent_config_table=None,
        agent_name="rca-agent",
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestCheckpointerFactory:
    def test_default_returns_memory_saver(self):
        set_config(_make_config(checkpoint_backend="memory"))
        cp = create_checkpointer()
        assert type(cp).__name__ == "InMemorySaver"

    def test_explicit_memory_backend(self):
        set_config(_make_config(checkpoint_backend="memory"))
        cp = create_checkpointer(backend="memory")
        assert type(cp).__name__ == "InMemorySaver"

    def test_override_backend_parameter(self):
        """Backend parameter overrides config."""
        set_config(
            _make_config(checkpoint_backend="dynamodb", checkpoint_table_name="t")
        )
        cp = create_checkpointer(backend="memory")
        assert type(cp).__name__ == "InMemorySaver"

    def test_dynamodb_requires_table_name(self):
        set_config(
            _make_config(checkpoint_backend="dynamodb", checkpoint_table_name=None)
        )
        with pytest.raises(ValueError, match="CHECKPOINT_TABLE_NAME"):
            create_checkpointer()

    def test_dynamodb_creates_saver(self):
        """DynamoDB backend creates a DynamoDBSaver (mocked import)."""
        mock_saver = MagicMock()
        mock_saver.__class__.__name__ = "DynamoDBSaver"
        mock_module = MagicMock()
        mock_module.DynamoDBSaver.return_value = mock_saver

        set_config(
            _make_config(
                checkpoint_backend="dynamodb", checkpoint_table_name="my-table"
            )
        )
        with patch.dict("sys.modules", {"langgraph_checkpoint_aws": mock_module}):
            create_checkpointer()
            mock_module.DynamoDBSaver.assert_called_once_with(
                table_name="my-table",
                region_name="us-east-1",
            )

    def test_agentcore_memory_requires_memory_id(self):
        set_config(_make_config(checkpoint_backend="agentcore_memory", memory_id=None))
        with pytest.raises(ValueError, match="MEMORY_ID"):
            create_checkpointer()

    def test_agentcore_memory_auto_selected_when_memory_id_set(self):
        """When MEMORY_ID is set and backend is default 'memory', auto-selects agentcore_memory."""
        mock_saver = MagicMock()
        mock_saver.__class__.__name__ = "AgentCoreMemorySaver"
        mock_module = MagicMock()
        mock_module.AgentCoreMemorySaver.return_value = mock_saver

        set_config(_make_config(checkpoint_backend="memory", memory_id="mem-123"))
        with patch.dict("sys.modules", {"langgraph_checkpoint_aws": mock_module}):
            create_checkpointer()
            mock_module.AgentCoreMemorySaver.assert_called_once_with(
                memory_id="mem-123",
                region_name="us-east-1",
            )

    def test_explicit_memory_backend_ignores_memory_id(self):
        """Explicit backend='memory' parameter overrides auto-detection."""
        set_config(
            _make_config(
                checkpoint_backend="dynamodb",
                checkpoint_table_name="t",
                memory_id="mem-123",
            )
        )
        cp = create_checkpointer(backend="memory")
        assert type(cp).__name__ == "InMemorySaver"

    def test_uppercase_backend_normalized(self):
        """Backend names are case-insensitive."""
        set_config(_make_config(checkpoint_backend="MEMORY"))
        cp = create_checkpointer()
        assert type(cp).__name__ == "InMemorySaver"

    def test_uppercase_parameter_backend(self):
        """Explicit backend parameter is also case-insensitive."""
        set_config(
            _make_config(checkpoint_backend="dynamodb", checkpoint_table_name="t")
        )
        cp = create_checkpointer(backend="MEMORY")
        assert type(cp).__name__ == "InMemorySaver"

    def test_unknown_backend_falls_through_to_memory(self):
        """Unknown backend name falls through to the else branch (memory)."""
        set_config(_make_config(checkpoint_backend="redis"))
        cp = create_checkpointer()
        assert type(cp).__name__ == "InMemorySaver"

    def test_agentcore_auto_only_when_backend_is_memory(self):
        """Auto-detection only triggers when config backend is 'memory', not others."""
        mock_saver = MagicMock()
        mock_module = MagicMock()
        mock_module.DynamoDBSaver.return_value = mock_saver

        set_config(
            _make_config(
                checkpoint_backend="dynamodb",
                checkpoint_table_name="t",
                memory_id="mem-123",
            )
        )
        with patch.dict("sys.modules", {"langgraph_checkpoint_aws": mock_module}):
            create_checkpointer()
            # Should create DynamoDB, not AgentCore
            mock_module.DynamoDBSaver.assert_called_once()


class TestConfigCheckpointFields:
    def test_from_env_defaults(self):
        with patch.dict(os.environ, {}, clear=False):
            cfg = Config.from_env()
            assert cfg.checkpoint_backend == "memory"
            assert cfg.checkpoint_table_name is None
            assert cfg.checkpoint_sqlite_path == "./checkpoints.db"

    def test_from_env_dynamodb(self):
        env = {
            "CHECKPOINT_BACKEND": "dynamodb",
            "CHECKPOINT_TABLE_NAME": "rca-checkpoints",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = Config.from_env()
            assert cfg.checkpoint_backend == "dynamodb"
            assert cfg.checkpoint_table_name == "rca-checkpoints"

    def test_from_env_memory_id(self):
        env = {"MEMORY_ID": "mem-abc-123"}
        with patch.dict(os.environ, env, clear=False):
            cfg = Config.from_env()
            assert cfg.memory_id == "mem-abc-123"

    def test_from_env_agent_config_table(self):
        env = {"AGENT_CONFIG_TABLE": "my-config", "AGENT_NAME": "custom-agent"}
        with patch.dict(os.environ, env, clear=False):
            cfg = Config.from_env()
            assert cfg.agent_config_table == "my-config"
            assert cfg.agent_name == "custom-agent"

    def test_validation_dynamodb_missing_table(self):
        cfg = _make_config(checkpoint_backend="dynamodb", checkpoint_table_name=None)
        errors = cfg.validate()
        assert any("CHECKPOINT_TABLE_NAME" in e for e in errors)

    def test_validation_memory_no_errors(self):
        cfg = _make_config(checkpoint_backend="memory")
        errors = cfg.validate()
        assert not errors
