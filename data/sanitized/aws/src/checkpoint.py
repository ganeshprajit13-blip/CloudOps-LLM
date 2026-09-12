"""
Checkpointer factory for LangGraph state persistence.

Supports four backends:
- memory: In-memory (default for local dev, lost on restart)
- sqlite: SQLite file (durable local dev)
- dynamodb: AWS DynamoDB (production, raw table)
- agentcore_memory: AgentCore managed memory (production, managed service)

The backend is selected via CHECKPOINT_BACKEND env var or the Config object.
When MEMORY_ID is set and no explicit backend is configured, agentcore_memory
is auto-selected.
"""

import logging
from typing import Optional

from config import get_config

logger = logging.getLogger(__name__)


def create_checkpointer(backend: Optional[str] = None):
    """Create a LangGraph checkpointer based on backend configuration.

    Args:
        backend: One of "memory", "sqlite", "dynamodb", "agentcore_memory".
                 Defaults to Config.checkpoint_backend (from CHECKPOINT_BACKEND env var).
                 When MEMORY_ID is set and backend is "memory" (the default),
                 auto-selects "agentcore_memory".
    """
    config = get_config()
    explicit_backend = backend is not None
    backend = (backend or config.checkpoint_backend).lower()

    # Auto-select agentcore_memory when MEMORY_ID is set and backend wasn't
    # explicitly overridden via the function parameter
    if not explicit_backend and backend == "memory" and config.memory_id:
        backend = "agentcore_memory"

    if backend == "agentcore_memory":
        memory_id = config.memory_id
        if not memory_id:
            raise ValueError("MEMORY_ID is required for AgentCore Memory checkpointer")

        from langgraph_checkpoint_aws import AgentCoreMemorySaver

        region = config.region
        logger.info(
            "Using AgentCore Memory checkpointer: memory_id=%s, region=%s",
            memory_id,
            region,
        )
        return AgentCoreMemorySaver(
            memory_id=memory_id,
            region_name=region,
        )
    elif backend == "dynamodb":
        table_name = config.checkpoint_table_name
        if not table_name:
            raise ValueError(
                "CHECKPOINT_TABLE_NAME is required for DynamoDB checkpointer"
            )

        from langgraph_checkpoint_aws import DynamoDBSaver

        logger.info(
            "Using DynamoDB checkpointer: table=%s, region=%s",
            table_name,
            config.region,
        )
        return DynamoDBSaver(
            table_name=table_name,
            region_name=config.region,
        )
    elif backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = config.checkpoint_sqlite_path
        logger.info("Using SQLite checkpointer: %s", db_path)
        return SqliteSaver.from_conn_string(db_path)
    else:
        from langgraph.checkpoint.memory import MemorySaver

        logger.info("Using in-memory checkpointer (not durable)")
        return MemorySaver()


async def create_async_checkpointer(backend: Optional[str] = None):
    """Create an async LangGraph checkpointer for use in async contexts (e.g. FastAPI).

    Args:
        backend: One of "memory", "sqlite", "dynamodb", "agentcore_memory".
                 Defaults to Config.checkpoint_backend (from CHECKPOINT_BACKEND env var).
                 When MEMORY_ID is set and backend is "memory" (the default),
                 auto-selects "agentcore_memory".
    """
    config = get_config()
    explicit_backend = backend is not None
    backend = (backend or config.checkpoint_backend).lower()

    if not explicit_backend and backend == "memory" and config.memory_id:
        backend = "agentcore_memory"

    if backend == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        db_path = config.checkpoint_sqlite_path
        logger.info("Using async SQLite checkpointer: %s", db_path)
        return await AsyncSqliteSaver.from_conn_string(db_path)

    # For non-sqlite backends, the sync versions work in async contexts
    return create_checkpointer(backend=backend)
