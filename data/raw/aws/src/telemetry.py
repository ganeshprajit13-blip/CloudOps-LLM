"""
OpenTelemetry instrumentation utilities for the RCA agent.

Provides decorators for LangGraph node functions and tool execution.
When OTEL_ENABLED != "true" (the default), all decorators are true no-ops
with zero overhead — the original function is returned unwrapped.

Usage:
    from telemetry import trace_node, trace_tool_call

    @trace_node("context_enrichment")
    async def context_enrichment(state):
        ...

    with trace_tool_call("search_logs", worker_id="inv-1"):
        result = log_search.search(...)
"""

import functools
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "false").lower() == "true"
_tracer = None  # Lazy-initialized


def _get_tracer():
    """Lazy-init the OpenTelemetry tracer. Returns None if unavailable."""
    global _tracer
    if _tracer is None:
        if not _OTEL_ENABLED:
            _tracer = False  # Sentinel: disabled
        else:
            try:
                from opentelemetry import trace

                _tracer = trace.get_tracer("rca-deep-research-agent")
                logger.info("OpenTelemetry tracer initialized")
            except ImportError:
                logger.warning("OpenTelemetry not installed — tracing disabled")
                _tracer = False
    return _tracer if _tracer is not False else None


def trace_node(node_name: str):
    """Decorator for async LangGraph node functions.

    Creates a span named ``graph.node.<node_name>`` with scenario metadata.
    True no-op when OTEL_ENABLED is not "true".
    """

    def decorator(func):
        if not _OTEL_ENABLED:
            return func  # Zero overhead: return the original function

        @functools.wraps(func)
        async def wrapper(state, *args, **kwargs):
            tracer = _get_tracer()
            if tracer is None:
                return await func(state, *args, **kwargs)

            scenario = ""
            if isinstance(state, dict):
                scenario = state.get("scenario_name", "")

            with tracer.start_as_current_span(
                f"graph.node.{node_name}",
                attributes={
                    "langgraph.node": node_name,
                    "rca.scenario": scenario,
                },
            ):
                return await func(state, *args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def trace_tool_call(tool_name: str, worker_id: str = ""):
    """Context manager to trace a tool execution.

    Usage:
        with trace_tool_call("search_logs", worker_id="inv-1"):
            result = log_search.search(...)

    No-op when tracing is disabled.
    """
    tracer = _get_tracer()
    if tracer is None:
        yield
        return

    with tracer.start_as_current_span(
        f"tool.{tool_name}",
        attributes={
            "tool.name": tool_name,
            "rca.worker_id": worker_id,
        },
    ):
        yield
