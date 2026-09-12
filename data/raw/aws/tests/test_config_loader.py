"""Tests for the DynamoDB config loader."""

import json
from unittest.mock import MagicMock, patch

import pytest

from config_loader import DynamoDBConfigLoader, merge_dynamodb_config


class TestDynamoDBConfigLoader:
    def test_load_latest_returns_parsed_config(self):
        config_dict = {"model_id": "test-model", "max_tokens": 2048}

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "AgentName": "rca-agent",
                    "CreatedAt": 1700000000,
                    "ConfigurationValue": json.dumps(config_dict),
                }
            ]
        }

        loader = DynamoDBConfigLoader("test-table")
        loader._table = mock_table

        result = loader.load_latest("rca-agent")
        assert result == config_dict
        mock_table.query.assert_called_once()

    def test_load_latest_returns_none_when_no_items(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        loader = DynamoDBConfigLoader("test-table")
        loader._table = mock_table

        result = loader.load_latest("nonexistent-agent")
        assert result is None

    def test_load_latest_returns_none_on_error(self):
        mock_table = MagicMock()
        mock_table.query.side_effect = Exception("DynamoDB error")

        loader = DynamoDBConfigLoader("test-table")
        loader._table = mock_table

        result = loader.load_latest("rca-agent")
        assert result is None

    def test_load_latest_queries_newest_first(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [{"ConfigurationValue": "{}"}]}

        loader = DynamoDBConfigLoader("test-table")
        loader._table = mock_table

        loader.load_latest("rca-agent")
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ScanIndexForward"] is False
        assert call_kwargs["Limit"] == 1

    def test_save_puts_item(self):
        mock_table = MagicMock()

        loader = DynamoDBConfigLoader("test-table")
        loader._table = mock_table

        loader.save("rca-agent", {"model_id": "test"})
        mock_table.put_item.assert_called_once()
        put_item = mock_table.put_item.call_args[1]["Item"]
        assert put_item["AgentName"] == "rca-agent"
        assert "CreatedAt" in put_item
        assert json.loads(put_item["ConfigurationValue"]) == {"model_id": "test"}


class TestMergeDynamoDBConfig:
    def test_dynamodb_values_override_env(self):
        env_kwargs = {"model_id": "env-model", "max_tokens": 1024, "log_level": "INFO"}
        db_config = {"model_id": "db-model", "max_tokens": 2048}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["model_id"] == "db-model"
        assert merged["max_tokens"] == 2048
        assert merged["log_level"] == "INFO"  # not in db, kept from env

    def test_unknown_db_keys_ignored(self):
        env_kwargs = {"model_id": "env-model"}
        db_config = {"model_id": "db-model", "unknown_key": "ignored"}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["model_id"] == "db-model"
        assert "unknown_key" not in merged

    def test_string_max_tokens_coerced_to_int(self):
        env_kwargs = {"max_tokens": 1024}
        db_config = {"max_tokens": "4096"}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["max_tokens"] == 4096

    def test_string_otel_enabled_coerced_to_bool(self):
        env_kwargs = {"otel_enabled": False}
        db_config = {"otel_enabled": "true"}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["otel_enabled"] is True

    def test_empty_db_config_returns_env_unchanged(self):
        env_kwargs = {"model_id": "env-model", "max_tokens": 1024}

        merged = merge_dynamodb_config(env_kwargs, {})
        assert merged == env_kwargs

    def test_invalid_max_tokens_string_skipped(self):
        """Non-numeric max_tokens string is skipped, env value preserved."""
        env_kwargs = {"max_tokens": 1024}
        db_config = {"max_tokens": "not-a-number"}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["max_tokens"] == 1024  # env value preserved

    def test_otel_enabled_false_string(self):
        env_kwargs = {"otel_enabled": True}
        db_config = {"otel_enabled": "false"}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["otel_enabled"] is False

    def test_otel_enabled_yes_string(self):
        env_kwargs = {"otel_enabled": False}
        db_config = {"otel_enabled": "yes"}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["otel_enabled"] is True

    def test_otel_enabled_one_string(self):
        env_kwargs = {"otel_enabled": False}
        db_config = {"otel_enabled": "1"}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["otel_enabled"] is True

    def test_int_max_tokens_passed_through_unchanged(self):
        """Integer max_tokens from DynamoDB (not string) is passed through as-is."""
        env_kwargs = {"max_tokens": 1024}
        db_config = {"max_tokens": 8192}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["max_tokens"] == 8192

    def test_bool_otel_enabled_passed_through_unchanged(self):
        """Boolean otel_enabled from DynamoDB (not string) is passed through as-is."""
        env_kwargs = {"otel_enabled": False}
        db_config = {"otel_enabled": True}

        merged = merge_dynamodb_config(env_kwargs, db_config)
        assert merged["otel_enabled"] is True


class TestDynamoDBConfigLoaderEdgeCases:
    def test_load_latest_config_value_as_dict(self):
        """ConfigurationValue can be a dict (already parsed by DynamoDB SDK)."""
        config_dict = {"model_id": "test-model"}

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [{"ConfigurationValue": config_dict}]}

        loader = DynamoDBConfigLoader("test-table")
        loader._table = mock_table

        result = loader.load_latest("rca-agent")
        assert result == config_dict

    def test_table_property_lazily_initializes(self):
        """Table property creates boto3 resource on first access."""
        with patch("boto3.resource") as mock_boto:
            mock_dynamo = MagicMock()
            mock_boto.return_value = mock_dynamo

            loader = DynamoDBConfigLoader("test-table", region="eu-west-1")
            _ = loader.table

            mock_boto.assert_called_once_with("dynamodb", region_name="eu-west-1")
            mock_dynamo.Table.assert_called_once_with("test-table")

    def test_save_error_propagates(self):
        """save() doesn't catch exceptions — they propagate to caller."""
        mock_table = MagicMock()
        mock_table.put_item.side_effect = Exception("DynamoDB write error")

        loader = DynamoDBConfigLoader("test-table")
        loader._table = mock_table

        with pytest.raises(Exception, match="DynamoDB write error"):
            loader.save("rca-agent", {"model_id": "test"})
