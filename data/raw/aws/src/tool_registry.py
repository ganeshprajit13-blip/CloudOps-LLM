"""
Tool registry for investigation worker agents.

Manages tool definitions (schemas for LLM binding) and executors
(callables for actual execution). This separation exists because tools
like search_logs need runtime dependency injection — the @tool function
is a schema declaration, while the executor receives the data source
and time window from the worker's state context.

Built-in tools (search_logs, think) are registered automatically.
Tools can be enabled/disabled via ENABLED_TOOLS env var.

Usage:
    from tool_registry import get_tool_registry

    registry = get_tool_registry()
    schemas = registry.get_schemas()       # For LLM binding
    executor = registry.get_executor("search_logs")  # For tool dispatch
"""

import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolEntry:
    """A registered tool with its schema and executor."""

    name: str
    schema_fn: object  # The @tool-decorated function (for LLM binding)
    executor_fn: Callable  # The actual execution function
    enabled: bool = True


class ToolRegistry:
    """Registry of available investigation tools."""

    def __init__(self):
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        schema_fn,
        executor_fn: Callable,
        enabled: bool = True,
    ) -> None:
        """Register a tool with its schema and executor."""
        self._tools[name] = ToolEntry(
            name=name,
            schema_fn=schema_fn,
            executor_fn=executor_fn,
            enabled=enabled,
        )
        logger.info("Registered tool: %s (enabled=%s)", name, enabled)

    def get_schemas(self) -> list:
        """Get tool schema functions for LLM binding."""
        return [t.schema_fn for t in self._tools.values() if t.enabled]

    def get_executor(self, name: str) -> Optional[Callable]:
        """Get executor for a tool by name. Returns None if not found or disabled."""
        entry = self._tools.get(name)
        if entry and entry.enabled:
            return entry.executor_fn
        return None

    def list_enabled(self) -> list[str]:
        """Get names of all enabled tools."""
        return [name for name, t in self._tools.items() if t.enabled]


# ---------------------------------------------------------------------------
# Built-in tool executors
# ---------------------------------------------------------------------------


def execute_search_logs(tool_args: dict, context: dict) -> str:
    """Execute search_logs with injected data source from context.

    Context keys:
        log_search: The log search source instance (with scenario set)
        default_time_start: Fallback time window start (ISO string)
        default_time_end: Fallback time window end (ISO string)
    """
    from rca_agent import parse_iso_timestamp
    from telemetry import trace_tool_call

    log_search = context["log_search"]
    default_time_start = context.get("default_time_start")
    default_time_end = context.get("default_time_end")
    worker_id = context.get("worker_id", "")

    query = tool_args.get("query", "")
    service = tool_args.get("service")
    time_start_str = tool_args.get("time_start") or default_time_start
    time_end_str = tool_args.get("time_end") or default_time_end

    if not time_start_str or not time_end_str:
        return (
            "ERROR: Time window is REQUIRED. Please specify time_start and "
            "time_end in ISO format (e.g., '2024-03-15T14:00:00')."
        )

    try:
        time_start = parse_iso_timestamp(time_start_str)
        time_end = parse_iso_timestamp(time_end_str)
        with trace_tool_call("search_logs", worker_id=worker_id):
            result = log_search.search(
                query=query,
                time_start=time_start,
                time_end=time_end,
                service=service,
                limit=10,
            )
        return result
    except ValueError as e:
        return f"ERROR parsing time: {e}. Use ISO format like '2024-03-15T14:00:00'"
    except Exception as e:
        return f"ERROR during search: {e}"


def execute_think(tool_args: dict, context: dict) -> str:
    """Execute the think (reflection) tool."""
    from rca_agent import think

    return think.invoke(tool_args)


def execute_list_log_sources(tool_args: dict, context: dict) -> str:
    """Execute list_log_sources with injected data source from context."""
    log_search = context.get("log_search")
    if not log_search:
        return "ERROR: No log search source available."
    sources = log_search.list_sources()
    if sources:
        return "Available log sources:\n" + "\n".join(f"  - {s}" for s in sources)
    return "No log sources available."


def execute_lookup_context(tool_args: dict, context: dict) -> str:
    """Execute lookup_context with query-based hybrid search via Bedrock KB.

    Context keys:
        context_source: BedrockContextSource instance
        scenario_name: Current scenario name (unused by Bedrock KB, kept for interface compat)
    """
    context_source = context.get("context_source")
    scenario_name = context.get("scenario_name")

    if not context_source:
        return "ERROR: No context source available."

    query = tool_args.get("query", "")
    context_type = tool_args.get("context_type", "all") or "all"

    if not query:
        return "ERROR: Please provide a query describing what you're looking for."

    search_query = query if context_type == "all" else f"{context_type}: {query}"
    chunks = context_source.search(
        query=search_query, num_results=5, scenario_name=scenario_name
    )
    if not chunks:
        return f"No context found matching '{query}'."
    return f"# Context: {query}\n\n" + "\n\n---\n\n".join(chunks)


# ---------------------------------------------------------------------------
# Global registry singleton
# ---------------------------------------------------------------------------

_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry with built-in tools registered."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_builtins(_registry)
        _register_mcp_tools(_registry)
        _apply_config(_registry)
    return _registry


def reset_tool_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None


def _register_builtins(registry: ToolRegistry) -> None:
    """Register the built-in search_logs, think, lookup_context, and list_log_sources tools."""
    from rca_agent import search_logs, think, lookup_context, list_log_sources

    registry.register("search_logs", search_logs, execute_search_logs)
    registry.register("think", think, execute_think)
    registry.register("lookup_context", lookup_context, execute_lookup_context)
    registry.register("list_log_sources", list_log_sources, execute_list_log_sources)


def _register_mcp_tools(registry: ToolRegistry) -> None:
    """Discover and register tools from configured MCP servers.

    No-op if MCP is not configured or the mcp package is not installed.
    """
    try:
        from mcp_client import MCPClientManager
    except ImportError:
        return

    manager = MCPClientManager.from_env()
    if not manager:
        return

    try:
        import asyncio

        # get_tool_registry() is called at startup before any async code runs,
        # so asyncio.run() is safe here. If somehow called from async context
        # (e.g. tests), fall back to creating a new loop in a thread.
        try:
            asyncio.get_running_loop()
            # Already in async context — run in a thread to avoid nested loop error
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, manager.connect()).result(timeout=30)
        except RuntimeError:
            # No running loop — safe to use asyncio.run()
            asyncio.run(manager.connect())
    except Exception as e:
        logger.warning("Failed to connect to MCP servers: %s", e)
        return

    for tool in manager.get_langchain_tools():

        def _make_executor(t):
            """Create a closure executor for an MCP tool."""

            def executor(tool_args: dict, context: dict) -> str:
                return t.invoke(tool_args)

            return executor

        registry.register(tool.name, tool, _make_executor(tool))

    logger.info(
        "Registered %d MCP tools from %d servers",
        manager.tool_count,
        manager.server_count,
    )


def _apply_config(registry: ToolRegistry) -> None:
    """Apply ENABLED_TOOLS env var to enable/disable tools.

    If ENABLED_TOOLS is set (comma-separated list), only those tools are enabled.
    If not set, all registered tools remain enabled.
    """
    enabled_str = os.environ.get("ENABLED_TOOLS", "").strip()
    if not enabled_str:
        return

    enabled_set = {t.strip() for t in enabled_str.split(",") if t.strip()}
    for name, entry in registry._tools.items():
        entry.enabled = name in enabled_set
    logger.info("Tools configured from ENABLED_TOOLS: %s", enabled_set)
