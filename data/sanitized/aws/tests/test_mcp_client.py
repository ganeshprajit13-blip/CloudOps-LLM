"""Tests for the MCP client module."""

import asyncio
import json
import os
from unittest.mock import MagicMock, patch


from mcp_client import MCPClientManager, MCPServerConfig


class TestMCPServerConfig:
    def test_defaults(self):
        config = MCPServerConfig(name="test", url="http://localhost:8080/sse")
        assert config.auth_type == "none"
        assert config.region == "us-east-1"


class TestMCPClientManagerFromEnv:
    def test_returns_none_when_no_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            manager = MCPClientManager.from_env()
            assert manager is None

    def test_parses_mcp_servers_json(self):
        servers = json.dumps(
            [
                {"name": "jira", "url": "http://localhost:8080/sse"},
                {
                    "name": "pagerduty",
                    "url": "http://localhost:8081/sse",
                    "auth_type": "sigv4",
                },
            ]
        )
        with patch.dict(os.environ, {"MCP_SERVERS": servers}, clear=True):
            manager = MCPClientManager.from_env()
            assert manager is not None
            assert len(manager._configs) == 2
            assert manager._configs[0].name == "jira"
            assert manager._configs[1].auth_type == "sigv4"

    def test_returns_none_on_invalid_json(self):
        with patch.dict(os.environ, {"MCP_SERVERS": "not-json"}, clear=True):
            manager = MCPClientManager.from_env()
            assert manager is None

    def test_returns_none_on_missing_required_fields(self):
        servers = json.dumps([{"name": "test"}])  # missing url
        with patch.dict(os.environ, {"MCP_SERVERS": servers}, clear=True):
            manager = MCPClientManager.from_env()
            assert manager is None

    def test_dynamodb_fallback(self):
        with patch.dict(
            os.environ, {"MCP_SERVER_REGISTRY_TABLE": "mcp-servers"}, clear=True
        ):
            with patch.object(
                MCPClientManager, "_from_dynamodb", return_value=None
            ) as mock:
                MCPClientManager.from_env()
                mock.assert_called_once_with("mcp-servers")


class TestMCPClientManagerConnect:
    def test_connect_without_mcp_package(self):
        """When mcp package is not installed, connect is a no-op."""
        configs = [MCPServerConfig(name="test", url="http://localhost:8080/sse")]
        manager = MCPClientManager(configs)

        with patch.dict(
            "sys.modules", {"mcp": None, "mcp.client.streamable_http": None}
        ):
            # Should not raise, just warn
            asyncio.run(manager.connect())
            assert manager.tool_count == 0

    def test_get_langchain_tools_empty(self):
        manager = MCPClientManager([])
        assert manager.get_langchain_tools() == []

    def test_tool_count(self):
        manager = MCPClientManager([])
        assert manager.tool_count == 0

    def test_server_count(self):
        manager = MCPClientManager([])
        assert manager.server_count == 0


class TestMCPClientManagerDynamoDB:
    def test_from_dynamodb_parses_items(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [
                {
                    "ServerName": "jira",
                    "ServerUrl": "http://jira:8080/sse",
                    "AuthType": "none",
                },
                {
                    "ServerName": "pd",
                    "ServerUrl": "http://pd:8081/sse",
                    "AuthType": "sigv4",
                    "Region": "eu-west-1",
                },
            ]
        }

        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value.Table.return_value = mock_table
            manager = MCPClientManager._from_dynamodb("mcp-servers")

        assert manager is not None
        assert len(manager._configs) == 2
        assert manager._configs[0].name == "jira"
        assert manager._configs[1].region == "eu-west-1"

    def test_from_dynamodb_returns_none_on_empty(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}

        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value.Table.return_value = mock_table
            manager = MCPClientManager._from_dynamodb("mcp-servers")

        assert manager is None

    def test_from_dynamodb_returns_none_on_error(self):
        with patch("boto3.resource", side_effect=Exception("AWS error")):
            manager = MCPClientManager._from_dynamodb("mcp-servers")
        assert manager is None


class TestMCPClientManagerEnvPrecedence:
    def test_mcp_servers_json_takes_precedence_over_dynamodb(self):
        """When both MCP_SERVERS and MCP_SERVER_REGISTRY_TABLE are set, JSON wins."""
        servers = json.dumps([{"name": "jira", "url": "http://localhost:8080/sse"}])
        env = {"MCP_SERVERS": servers, "MCP_SERVER_REGISTRY_TABLE": "mcp-servers"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(MCPClientManager, "_from_dynamodb") as mock_db:
                manager = MCPClientManager.from_env()
                mock_db.assert_not_called()
                assert manager is not None
                assert manager._configs[0].name == "jira"

    def test_region_from_aws_region_env(self):
        """Region defaults to AWS_REGION env var."""
        servers = json.dumps([{"name": "test", "url": "http://localhost:8080/sse"}])
        env = {"MCP_SERVERS": servers, "AWS_REGION": "ap-southeast-1"}
        with patch.dict(os.environ, env, clear=True):
            manager = MCPClientManager.from_env()
            assert manager._configs[0].region == "ap-southeast-1"

    def test_per_server_region_overrides_global(self):
        """Per-server region in JSON overrides AWS_REGION."""
        servers = json.dumps(
            [
                {
                    "name": "test",
                    "url": "http://localhost:8080/sse",
                    "region": "eu-west-1",
                }
            ]
        )
        env = {"MCP_SERVERS": servers, "AWS_REGION": "ap-southeast-1"}
        with patch.dict(os.environ, env, clear=True):
            manager = MCPClientManager.from_env()
            assert manager._configs[0].region == "eu-west-1"

    def test_whitespace_only_env_var_treated_as_empty(self):
        """Whitespace-only MCP_SERVERS is treated as not configured."""
        with patch.dict(os.environ, {"MCP_SERVERS": "   "}, clear=True):
            manager = MCPClientManager.from_env()
            assert manager is None


class TestMCPClientManagerCleanup:
    def test_cleanup_on_empty_manager(self):
        """cleanup() on manager with no connections doesn't raise."""
        manager = MCPClientManager([])
        asyncio.run(manager.cleanup())
        assert manager.tool_count == 0
        assert manager.server_count == 0
