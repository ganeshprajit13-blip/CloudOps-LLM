"""
Configuration for Deep Research RCA Agent.

Supports two modes:
- LOCAL: File-based logs, Bedrock KB for context (for demos)
- PRODUCTION: AWS-backed logs (S3+Athena, CloudWatch, or OpenSearch) and Bedrock KB for context

Configuration is read from environment variables.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Valid log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging(level: str = "INFO") -> None:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # Also set level for root logger
    logging.getLogger().setLevel(log_level)


class DataSourceMode(Enum):
    """Data source mode for the agent."""

    LOCAL = "local"  # File-based logs and context (default for demos)
    PRODUCTION = (
        "production"  # AWS-backed: Athena/CloudWatch for logs, Bedrock KB for context
    )


class LogSearchBackend(Enum):
    """Log search backend for production mode."""

    ATHENA = "athena"  # S3 + Athena (no timestamp limit, ~$5/TB, 2-10s latency)
    CLOUDWATCH = "cloudwatch"  # CloudWatch Logs (14-day limit, real-time)
    OPENSEARCH = (
        "opensearch"  # OpenSearch (full-text, sub-second latency, scalable retention)
    )


@dataclass
class Config:
    """Agent configuration."""

    # Mode
    mode: DataSourceMode

    # AWS region
    region: str

    # Model configuration
    model_id: str
    max_tokens: int

    # Logging
    log_level: str

    # LOCAL mode: scenario path for file-based sources
    scenarios_dir: Optional[str]

    # PRODUCTION mode: Log search backend
    log_search_backend: Optional[LogSearchBackend]

    # PRODUCTION mode: Knowledge Base (Bedrock with S3 Vectors)
    bedrock_kb_id: Optional[str]

    # CloudWatch backend config
    cloudwatch_log_group_names: Optional[list[str]]
    cloudwatch_log_group_prefix: Optional[str]

    # Athena backend config
    athena_database: Optional[str]
    athena_table: Optional[str]
    athena_output_location: Optional[str]

    # OpenSearch backend config
    opensearch_endpoint: Optional[str]
    opensearch_index: Optional[str]
    opensearch_auth_mode: Optional[str]  # "iam" or "basic"
    opensearch_username: Optional[str]
    opensearch_password: Optional[str]
    opensearch_serverless: bool

    # Checkpoint backend: "memory" (default), "sqlite", "dynamodb"
    checkpoint_backend: str
    checkpoint_table_name: Optional[str]  # DynamoDB table name
    checkpoint_sqlite_path: str  # SQLite file path

    # OpenTelemetry
    otel_enabled: bool
    otel_service_name: str
    otel_exporter_endpoint: Optional[str]

    # Tool registry: comma-separated tool names to enable (None = all)
    enabled_tools: Optional[str]

    # AgentCore Memory ID (when deployed on AgentCore with managed memory)
    memory_id: Optional[str]

    # DynamoDB config storage (optional, overrides env vars)
    agent_config_table: Optional[str]
    agent_name: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        # Determine mode
        mode_str = os.environ.get("RCA_AGENT_MODE", "local").lower()
        if mode_str == "production":
            mode = DataSourceMode.PRODUCTION
        else:
            mode = DataSourceMode.LOCAL

        # Determine log search backend (for production mode)
        backend_str = os.environ.get("LOG_SEARCH_BACKEND", "athena").lower()
        if backend_str == "cloudwatch":
            log_search_backend = LogSearchBackend.CLOUDWATCH
        elif backend_str == "opensearch":
            log_search_backend = LogSearchBackend.OPENSEARCH
        else:
            log_search_backend = LogSearchBackend.ATHENA

        # Parse log group names from comma-separated string
        log_groups_str = os.environ.get("CLOUDWATCH_LOG_GROUP_NAMES", "")
        log_group_names = [
            g.strip() for g in log_groups_str.split(",") if g.strip()
        ] or None

        # Get KB ID (required for context retrieval)
        kb_id = os.environ.get("BEDROCK_KB_ID", "")

        return cls(
            mode=mode,
            region=os.environ.get("AWS_REGION", "us-east-1"),
            model_id=os.environ.get(
                "BEDROCK_MODEL_ID", "global.anthropic.claude-opus-4-6-v1"
            ),
            max_tokens=int(os.environ.get("BEDROCK_MAX_TOKENS", "8192")),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            scenarios_dir=os.environ.get("SCENARIOS_DIR"),
            log_search_backend=log_search_backend
            if mode == DataSourceMode.PRODUCTION
            else None,
            bedrock_kb_id=kb_id or None,
            cloudwatch_log_group_names=log_group_names,
            cloudwatch_log_group_prefix=os.environ.get("CLOUDWATCH_LOG_GROUP_PREFIX"),
            athena_database=os.environ.get("ATHENA_DATABASE"),
            athena_table=os.environ.get("ATHENA_TABLE"),
            athena_output_location=os.environ.get("ATHENA_OUTPUT_LOCATION"),
            opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT"),
            opensearch_index=os.environ.get("OPENSEARCH_INDEX", "rca-logs"),
            opensearch_auth_mode=os.environ.get("OPENSEARCH_AUTH_MODE", "iam"),
            opensearch_username=os.environ.get("OPENSEARCH_USERNAME"),
            opensearch_password=os.environ.get("OPENSEARCH_PASSWORD"),
            opensearch_serverless=os.environ.get("OPENSEARCH_SERVERLESS", "").lower()
            == "true",
            # Checkpoint
            checkpoint_backend=os.environ.get("CHECKPOINT_BACKEND", "memory").lower(),
            checkpoint_table_name=os.environ.get("CHECKPOINT_TABLE_NAME"),
            checkpoint_sqlite_path=os.environ.get(
                "CHECKPOINT_SQLITE_PATH", "./checkpoints.db"
            ),
            # OpenTelemetry
            otel_enabled=os.environ.get("OTEL_ENABLED", "false").lower() == "true",
            otel_service_name=os.environ.get(
                "OTEL_SERVICE_NAME", "rca-deep-research-agent"
            ),
            otel_exporter_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
            # Tool registry
            enabled_tools=os.environ.get("ENABLED_TOOLS"),
            # AgentCore Memory
            memory_id=os.environ.get("MEMORY_ID"),
            # DynamoDB config storage
            agent_config_table=os.environ.get("AGENT_CONFIG_TABLE"),
            agent_name=os.environ.get("AGENT_NAME", "rca-agent"),
        )

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of errors."""
        errors = []

        if self.mode == DataSourceMode.PRODUCTION:
            if self.log_search_backend == LogSearchBackend.CLOUDWATCH:
                if (
                    not self.cloudwatch_log_group_names
                    and not self.cloudwatch_log_group_prefix
                ):
                    errors.append(
                        "CLOUDWATCH_LOG_GROUP_NAMES or CLOUDWATCH_LOG_GROUP_PREFIX required for CloudWatch backend"
                    )
            elif self.log_search_backend == LogSearchBackend.ATHENA:
                if not self.athena_database:
                    errors.append("ATHENA_DATABASE required for Athena backend")
                if not self.athena_table:
                    errors.append("ATHENA_TABLE required for Athena backend")
                if not self.athena_output_location:
                    errors.append("ATHENA_OUTPUT_LOCATION required for Athena backend")
            elif self.log_search_backend == LogSearchBackend.OPENSEARCH:
                if not self.opensearch_endpoint:
                    errors.append("OPENSEARCH_ENDPOINT required for OpenSearch backend")
                if self.opensearch_auth_mode == "basic":
                    if not self.opensearch_username:
                        errors.append(
                            "OPENSEARCH_USERNAME required for OpenSearch basic auth"
                        )
                    if not self.opensearch_password:
                        errors.append(
                            "OPENSEARCH_PASSWORD required for OpenSearch basic auth"
                        )

        if self.mode == DataSourceMode.PRODUCTION and not self.bedrock_kb_id:
            errors.append(
                "BEDROCK_KB_ID is required for context retrieval via Bedrock Knowledge Base"
            )

        if self.checkpoint_backend == "dynamodb" and not self.checkpoint_table_name:
            errors.append(
                "CHECKPOINT_TABLE_NAME required for DynamoDB checkpoint backend"
            )

        return errors

    def __str__(self) -> str:
        """Format config for logging."""
        if self.mode == DataSourceMode.LOCAL:
            return f"Config(mode=LOCAL, scenarios={self.scenarios_dir})"
        else:
            kb_info = (
                f"kb={self.bedrock_kb_id}"
                if self.bedrock_kb_id
                else "context=file-based"
            )
            if self.log_search_backend == LogSearchBackend.ATHENA:
                return f"Config(mode=PRODUCTION, logs=athena:{self.athena_database}.{self.athena_table}, {kb_info})"
            elif self.log_search_backend == LogSearchBackend.OPENSEARCH:
                return f"Config(mode=PRODUCTION, logs=opensearch:{self.opensearch_endpoint}/{self.opensearch_index}, {kb_info})"
            else:
                log_source = (
                    self.cloudwatch_log_group_prefix or self.cloudwatch_log_group_names
                )
                return (
                    f"Config(mode=PRODUCTION, logs=cloudwatch:{log_source}, {kb_info})"
                )


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global config.

    When AGENT_CONFIG_TABLE is set, loads config from DynamoDB first,
    then fills gaps from environment variables. Otherwise uses env vars only.
    """
    global _config
    if _config is None:
        _config = Config.from_env()

        # Overlay DynamoDB config if configured
        table_name = _config.agent_config_table
        if table_name:
            try:
                from config_loader import DynamoDBConfigLoader, merge_dynamodb_config

                loader = DynamoDBConfigLoader(table_name, region=_config.region)
                db_config = loader.load_latest(_config.agent_name)
                if db_config:
                    # Re-create config with DynamoDB values merged in
                    env_kwargs = _config.__dict__.copy()
                    merged = merge_dynamodb_config(env_kwargs, db_config)
                    _config = Config(**merged)
            except ImportError:
                logging.getLogger(__name__).warning(
                    "config_loader not available, skipping DynamoDB config"
                )
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "Failed to load DynamoDB config: %s", e
                )

    return _config


def set_config(config: Config) -> None:
    """Override the global config (for testing)."""
    global _config
    _config = config


def reset_config() -> None:
    """Reset the global config (for testing)."""
    global _config
    _config = None
