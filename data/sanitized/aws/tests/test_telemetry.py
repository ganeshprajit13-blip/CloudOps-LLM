"""Tests for the telemetry module."""

import os
from unittest.mock import patch


class TestTraceNodeDisabled:
    """When OTEL_ENABLED is not 'true', decorators should be no-ops."""

    def test_returns_original_function_when_disabled(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "false"}, clear=False):
            # Re-import to pick up the env var
            import importlib
            import telemetry

            importlib.reload(telemetry)

            @telemetry.trace_node("test_node")
            async def my_func(state):
                return state

            # Should return the unwrapped function (no wrapper overhead)
            assert my_func.__name__ == "my_func"

    def test_trace_tool_call_is_noop_when_disabled(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "false"}, clear=False):
            import importlib
            import telemetry

            importlib.reload(telemetry)

            executed = False
            with telemetry.trace_tool_call("search_logs", worker_id="inv-1"):
                executed = True
            assert executed


class TestTraceNodeEnabled:
    """When OTEL_ENABLED is 'true' but OpenTelemetry is not installed,
    the decorator should still work (graceful degradation)."""

    def test_decorator_wraps_function_when_enabled(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}, clear=False):
            import importlib
            import telemetry

            # Reset the tracer singleton
            telemetry._tracer = None
            importlib.reload(telemetry)

            @telemetry.trace_node("test_node")
            async def my_func(state):
                return {"result": True}

            # When enabled, the function is wrapped
            assert my_func.__name__ == "my_func"  # functools.wraps preserves name

    def test_decorated_function_still_executes(self):
        import asyncio

        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}, clear=False):
            import importlib
            import telemetry

            telemetry._tracer = None
            importlib.reload(telemetry)

            @telemetry.trace_node("test_node")
            async def my_func(state):
                return {"value": state.get("input", "default")}

            result = asyncio.run(my_func({"input": "hello"}))
            assert result == {"value": "hello"}

    def test_trace_tool_call_executes_body_when_enabled(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}, clear=False):
            import importlib
            import telemetry

            telemetry._tracer = None
            importlib.reload(telemetry)

            executed = False
            with telemetry.trace_tool_call("search_logs"):
                executed = True
            assert executed
