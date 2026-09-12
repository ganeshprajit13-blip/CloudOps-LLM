"""
DynamoDB-backed configuration loader.

Loads agent configuration from a DynamoDB table, allowing UI-managed
configuration without code changes. Falls back to environment variables
when the config table is not configured.

Table schema:
    PK: AgentName (S)
    SK: CreatedAt (N) — epoch timestamp, newest = latest config
    ConfigurationValue (S) — JSON string with config fields

Usage:
    loader = DynamoDBConfigLoader("my-config-table", region="us-east-1")
    config_dict = loader.load_latest("rca-agent")
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DynamoDBConfigLoader:
    """Loads agent configuration from a DynamoDB table."""

    def __init__(self, table_name: str, region: str = "us-east-1"):
        self._table_name = table_name
        self._region = region
        self._table = None

    @property
    def table(self):
        if self._table is None:
            import boto3

            dynamodb = boto3.resource("dynamodb", region_name=self._region)
            self._table = dynamodb.Table(self._table_name)
        return self._table

    def load_latest(self, agent_name: str) -> Optional[dict]:
        """Load the latest configuration for an agent.

        Queries by AgentName, sorts by CreatedAt descending,
        returns the most recent ConfigurationValue as a parsed dict.

        Returns None if no configuration is found.
        """
        try:
            from boto3.dynamodb.conditions import Key

            response = self.table.query(
                KeyConditionExpression=Key("AgentName").eq(agent_name),
                ScanIndexForward=False,  # newest first
                Limit=1,
            )

            items = response.get("Items", [])
            if not items:
                logger.info("No config found in DynamoDB for agent '%s'", agent_name)
                return None

            item = items[0]
            config_value = item.get("ConfigurationValue", "{}")

            if isinstance(config_value, str):
                config_dict = json.loads(config_value)
            else:
                config_dict = config_value

            logger.info(
                "Loaded config from DynamoDB for agent '%s' (created_at=%s)",
                agent_name,
                item.get("CreatedAt"),
            )
            return config_dict

        except Exception as e:
            logger.error("Failed to load config from DynamoDB: %s", e)
            return None

    def save(self, agent_name: str, config_dict: dict) -> None:
        """Save a configuration entry for an agent.

        Creates a new entry with the current timestamp as CreatedAt.
        """
        import time

        self.table.put_item(
            Item={
                "AgentName": agent_name,
                "CreatedAt": int(time.time()),
                "ConfigurationValue": json.dumps(config_dict),
            }
        )
        logger.info("Saved config to DynamoDB for agent '%s'", agent_name)


# Field mapping from DynamoDB config keys to Config dataclass field names
_DYNAMODB_TO_CONFIG_MAP = {
    "model_id": "model_id",
    "max_tokens": "max_tokens",
    "log_level": "log_level",
    "log_search_backend": "log_search_backend",
    "bedrock_kb_id": "bedrock_kb_id",
    "athena_database": "athena_database",
    "athena_table": "athena_table",
    "athena_output_location": "athena_output_location",
    "opensearch_endpoint": "opensearch_endpoint",
    "opensearch_index": "opensearch_index",
    "opensearch_auth_mode": "opensearch_auth_mode",
    "checkpoint_backend": "checkpoint_backend",
    "checkpoint_table_name": "checkpoint_table_name",
    "otel_enabled": "otel_enabled",
    "otel_service_name": "otel_service_name",
    "enabled_tools": "enabled_tools",
}


def merge_dynamodb_config(env_config_kwargs: dict, dynamodb_config: dict) -> dict:
    """Merge DynamoDB config values into env-var-based config kwargs.

    DynamoDB values take precedence over env vars for fields present
    in the DynamoDB config. Fields not in DynamoDB fall back to env vars.

    Args:
        env_config_kwargs: Dict of kwargs from Config.from_env() flow.
        dynamodb_config: Dict loaded from DynamoDB ConfigurationValue.

    Returns:
        Merged kwargs dict for Config constructor.
    """
    merged = dict(env_config_kwargs)

    for db_key, config_key in _DYNAMODB_TO_CONFIG_MAP.items():
        if db_key in dynamodb_config:
            value = dynamodb_config[db_key]
            # Type coercions for specific fields
            if config_key == "max_tokens" and isinstance(value, str):
                try:
                    value = int(value)
                except ValueError:
                    logger.warning(
                        "Invalid max_tokens value from DynamoDB (not an integer), skipping"
                    )
                    continue
            if config_key == "otel_enabled" and isinstance(value, str):
                value = value.lower() in ("true", "1", "yes")
            merged[config_key] = value

    return merged
