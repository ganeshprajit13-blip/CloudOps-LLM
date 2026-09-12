"""Tests for the tool registry."""

import os
from unittest.mock import patch

import pytest

from tool_registry import ToolRegistry, get_tool_registry, reset_tool_registry


@pytest.fixture(autouse=True)
def _reset():
    reset_tool_registry()
    yield
    reset_tool_registry()


def _dummy_schema():
    """A dummy schema function (stands in for an @tool-decorated function)."""
    pass


def _dummy_executor(tool_args, context):
    """A dummy executor that echoes args."""
    return f"executed: {tool_args}"


class TestToolRegistry:
    def test_register_and_get_schemas(self):
        reg = ToolRegistry()
        reg.register("my_tool", _dummy_schema, _dummy_executor)
        schemas = reg.get_schemas()
        assert len(schemas) == 1
        assert schemas[0] is _dummy_schema

    def test_get_executor(self):
        reg = ToolRegistry()
        reg.register("my_tool", _dummy_schema, _dummy_executor)
        executor = reg.get_executor("my_tool")
        assert executor is _dummy_executor

    def test_get_executor_unknown_tool(self):
        reg = ToolRegistry()
        assert reg.get_executor("nonexistent") is None

    def test_disabled_tool_excluded_from_schemas(self):
        reg = ToolRegistry()
        reg.register("enabled_tool", _dummy_schema, _dummy_executor, enabled=True)
        reg.register("disabled_tool", _dummy_schema, _dummy_executor, enabled=False)
        schemas = reg.get_schemas()
        assert len(schemas) == 1

    def test_disabled_tool_executor_returns_none(self):
        reg = ToolRegistry()
        reg.register("my_tool", _dummy_schema, _dummy_executor, enabled=False)
        assert reg.get_executor("my_tool") is None

    def test_list_enabled(self):
        reg = ToolRegistry()
        reg.register("a", _dummy_schema, _dummy_executor, enabled=True)
        reg.register("b", _dummy_schema, _dummy_executor, enabled=False)
        reg.register("c", _dummy_schema, _dummy_executor, enabled=True)
        assert reg.list_enabled() == ["a", "c"]


class TestGlobalRegistry:
    def test_get_tool_registry_returns_singleton(self):
        r1 = get_tool_registry()
        r2 = get_tool_registry()
        assert r1 is r2

    def test_builtin_tools_registered(self):
        reg = get_tool_registry()
        names = reg.list_enabled()
        assert "search_logs" in names
        assert "think" in names

    def test_search_logs_executor_exists(self):
        reg = get_tool_registry()
        executor = reg.get_executor("search_logs")
        assert executor is not None
        assert callable(executor)

    def test_think_executor_exists(self):
        reg = get_tool_registry()
        executor = reg.get_executor("think")
        assert executor is not None
        assert callable(executor)


class TestEnabledToolsConfig:
    def test_enabled_tools_env_filters(self):
        with patch.dict(os.environ, {"ENABLED_TOOLS": "search_logs"}, clear=False):
            reset_tool_registry()
            reg = get_tool_registry()
            assert "search_logs" in reg.list_enabled()
            assert "think" not in reg.list_enabled()

    def test_empty_enabled_tools_enables_all(self):
        with patch.dict(os.environ, {"ENABLED_TOOLS": ""}, clear=False):
            reset_tool_registry()
            reg = get_tool_registry()
            assert "search_logs" in reg.list_enabled()
            assert "think" in reg.list_enabled()


class TestThinkExecutor:
    def test_think_returns_string(self):
        reg = get_tool_registry()
        executor = reg.get_executor("think")
        result = executor({"reflection": "testing"}, {})
        assert isinstance(result, str)
        assert "testing" in result


class TestLookupContextExecutor:
    def test_search_called_with_query(self):
        """execute_lookup_context passes the query to context_source.search()."""
        from unittest.mock import MagicMock

        from tool_registry import execute_lookup_context

        mock_source = MagicMock()
        mock_source.search.return_value = ["Chunk about redis config"]
        ctx = {"context_source": mock_source, "scenario_name": "test"}

        result = execute_lookup_context({"query": "redis config"}, ctx)

        mock_source.search.assert_called_once_with(
            query="redis config", num_results=5, scenario_name="test"
        )
        assert "redis config" in result

    def test_empty_query_returns_error(self):
        """Empty query returns an error instead of searching."""
        from unittest.mock import MagicMock

        from tool_registry import execute_lookup_context

        mock_source = MagicMock()
        ctx = {"context_source": mock_source, "scenario_name": "test"}

        result = execute_lookup_context({"query": ""}, ctx)
        assert "ERROR" in result
        mock_source.search.assert_not_called()

    def test_no_results_message(self):
        """Returns a helpful message when search finds nothing."""
        from unittest.mock import MagicMock

        from tool_registry import execute_lookup_context

        mock_source = MagicMock()
        mock_source.search.return_value = []
        ctx = {"context_source": mock_source, "scenario_name": "test"}

        result = execute_lookup_context({"query": "nonexistent"}, ctx)
        assert "No context found" in result
