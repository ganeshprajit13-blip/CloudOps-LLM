"""
System status aggregation for the Backend Status panel.

Collects configuration and health check results from all backends
(log search, context source, checkpoint) into a single response.
"""

import asyncio
import logging
import time

from config import get_config, DataSourceMode

logger = logging.getLogger(__name__)

# Cache to avoid hammering backends on repeated panel opens
_cache: dict | None = None
_cache_time: float = 0.0
_CACHE_TTL = 30.0  # seconds


def _check_log_search() -> dict:
    """Health-check the configured log search backend."""
    config = get_config()

    if config.mode == DataSourceMode.LOCAL:
        try:
            from data_source_factory import create_log_search_source

            source = create_log_search_source()
            result = source.health_check()
            return {"type": "local", **result}
        except Exception as e:
            return {
                "type": "local",
                "status": "error",
                "message": str(e),
                "details": {},
            }

    # Production mode
    backend = config.log_search_backend
    type_name = backend.value if backend else "unknown"
    try:
        from data_source_factory import create_log_search_source

        source = create_log_search_source()
        result = source.health_check()
        return {"type": type_name, **result}
    except Exception as e:
        return {"type": type_name, "status": "error", "message": str(e), "details": {}}


def _check_context_source() -> dict:
    """Health-check the configured context source (Bedrock KB or local)."""
    config = get_config()

    try:
        from data_source_factory import create_context_source

        source = create_context_source()
        result = source.health_check()
        type_name = "bedrock_kb" if config.bedrock_kb_id else "local_files"
        return {"type": type_name, **result}
    except RuntimeError as e:
        # create_context_source raises RuntimeError when KB ID missing in prod
        return {
            "type": "unconfigured",
            "status": "error",
            "message": str(e),
            "details": {},
        }
    except Exception as e:
        type_name = "bedrock_kb" if config.bedrock_kb_id else "local_files"
        return {"type": type_name, "status": "error", "message": str(e), "details": {}}


def _check_checkpoint() -> dict:
    """Report checkpoint backend type and basic status."""
    config = get_config()
    backend = config.checkpoint_backend

    # Memory ID auto-selects agentcore_memory
    if config.memory_id and backend == "memory":
        backend = "agentcore_memory"

    details = {}
    if backend == "sqlite":
        details["path"] = config.checkpoint_sqlite_path
    elif backend == "dynamodb":
        details["table"] = config.checkpoint_table_name

    return {"type": backend, "status": "ok", "details": details}


async def get_system_status() -> dict:
    """Aggregate config and backend health into a single status response.

    Results are cached for 30 seconds to avoid redundant backend calls.
    """
    global _cache, _cache_time

    now = time.monotonic()
    if _cache is not None and (now - _cache_time) < _CACHE_TTL:
        return _cache

    config = get_config()

    # Run health checks concurrently (they involve network I/O)
    log_result, context_result, checkpoint_result = await asyncio.gather(
        asyncio.to_thread(_check_log_search),
        asyncio.to_thread(_check_context_source),
        asyncio.to_thread(_check_checkpoint),
    )

    result = {
        "agent": {
            "mode": config.mode.value,
            "region": config.region,
        },
        "backends": {
            "log_search": log_result,
            "context_source": context_result,
            "checkpoint": checkpoint_result,
        },
    }

    _cache = result
    _cache_time = now
    return result
