"""
MCP (Model Context Protocol) client for external tool servers.

Discovers tools from MCP servers via streamablehttp transport, wraps them
as LangGraph-compatible tools, and optionally uses SigV4 auth for AWS
MCP servers.

Configuration via environment variables:
    MCP_SERVERS: JSON array of server configs, e.g.:
        [{"name": "jira", "url": "https://mcp.example.com/sse", "auth_type": "none"}]
    MCP_SERVER_REGISTRY_TABLE: DynamoDB table name for server registry (alternative to JSON)

Usage:
    from mcp_client import MCPClientManager

    manager = MCPClientManager.from_env()
    if manager:
        await manager.connect()
        tools = manager.get_langchain_tools()
        await manager.cleanup()
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    url: str
    auth_type: str = "none"  # "none", "sigv4"
    region: str = "us-east-1"


class MCPClientManager:
    """Manages connections to MCP servers and exposes their tools."""

    def __init__(self, configs: list[MCPServerConfig]):
        self._configs = configs
        self._clients: dict[str, object] = {}
        self._tools: list = []

    @classmethod
    def from_env(cls) -> Optional["MCPClientManager"]:
        """Create manager from environment variables. Returns None if not configured."""
        servers_json = os.environ.get("MCP_SERVERS", "").strip()
        if servers_json:
            try:
                raw = json.loads(servers_json)
                configs = [
                    MCPServerConfig(
                        name=s["name"],
                        url=s["url"],
                        auth_type=s.get("auth_type", "none"),
                        region=s.get(
                            "region", os.environ.get("AWS_REGION", "us-east-1")
                        ),
                    )
                    for s in raw
                ]
                return cls(configs)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to parse MCP_SERVERS: %s", e)
                return None

        table_name = os.environ.get("MCP_SERVER_REGISTRY_TABLE", "").strip()
        if table_name:
            return cls._from_dynamodb(table_name)

        return None

    @classmethod
    def _from_dynamodb(cls, table_name: str) -> Optional["MCPClientManager"]:
        """Load server configs from a DynamoDB registry table."""
        try:
            import boto3

            region = os.environ.get("AWS_REGION", "us-east-1")
            table = boto3.resource("dynamodb", region_name=region).Table(table_name)
            response = table.scan()
            configs = []
            for item in response.get("Items", []):
                configs.append(
                    MCPServerConfig(
                        name=item["ServerName"],
                        url=item["ServerUrl"],
                        auth_type=item.get("AuthType", "none"),
                        region=item.get("Region", region),
                    )
                )
            if configs:
                return cls(configs)
        except Exception as e:
            logger.warning("Failed to load MCP servers from DynamoDB: %s", e)
        return None

    async def connect(self) -> None:
        """Connect to all configured MCP servers and discover tools."""
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError:
            logger.warning(
                "mcp package not installed. Install with: pip install mcp>=1.0.0"
            )
            return

        for config in self._configs:
            try:
                transport_cm = streamablehttp_client(
                    url=config.url,
                    headers=self._get_auth_headers(config),
                )
                read_stream, write_stream, _ = await transport_cm.__aenter__()
                session = ClientSession(read_stream, write_stream)
                await session.__aenter__()
                await session.initialize()

                self._clients[config.name] = {
                    "session": session,
                    "transport_cm": transport_cm,
                    "config": config,
                }

                # Discover tools
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    wrapped = self._wrap_tool(config.name, session, tool)
                    self._tools.append(wrapped)

                logger.info(
                    "Connected to MCP server '%s' at %s — %d tools discovered",
                    config.name,
                    config.url,
                    len(tools_result.tools),
                )
            except Exception as e:
                logger.warning(
                    "Failed to connect to MCP server '%s': %s", config.name, e
                )

    def _get_auth_headers(self, config: MCPServerConfig) -> dict:
        """Get auth headers for a server connection."""
        if config.auth_type == "sigv4":
            try:
                from mcp_proxy_for_aws import create_sigv4_headers

                return create_sigv4_headers(region=config.region, service="execute-api")
            except ImportError:
                logger.warning(
                    "SigV4 auth requested for '%s' but mcp-proxy-for-aws not installed",
                    config.name,
                )
        return {}

    def _wrap_tool(self, server_name: str, session, mcp_tool) -> object:
        """Wrap an MCP tool as a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool

        tool_name = f"{server_name}__{mcp_tool.name}"
        description = mcp_tool.description or f"MCP tool from {server_name}"

        # Build input schema from MCP tool's inputSchema
        _input_schema = mcp_tool.inputSchema if hasattr(mcp_tool, "inputSchema") else {}

        async def _call_tool(**kwargs) -> str:
            try:
                result = await session.call_tool(mcp_tool.name, arguments=kwargs)
                # MCP returns content as list of content blocks
                parts = []
                for block in result.content:
                    if hasattr(block, "text"):
                        parts.append(block.text)
                return "\n".join(parts) if parts else str(result)
            except Exception as e:
                return f"MCP tool error ({server_name}/{mcp_tool.name}): {e}"

        # LangGraph workers are async, so coroutine= is the primary execution path.
        # func= is a sync fallback that uses asyncio.run() for non-async callers
        # (e.g. CLI scripts). This is safe because non-async callers won't have
        # a running event loop.
        def _sync_fallback(**kwargs) -> str:
            return asyncio.run(_call_tool(**kwargs))

        return StructuredTool.from_function(
            func=_sync_fallback,
            coroutine=_call_tool,
            name=tool_name,
            description=description,
        )

    def get_langchain_tools(self) -> list:
        """Return all discovered tools as LangChain tools."""
        return list(self._tools)

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def server_count(self) -> int:
        return len(self._clients)

    async def cleanup(self) -> None:
        """Close all MCP server connections."""
        for name, client_info in self._clients.items():
            try:
                session = client_info["session"]
                transport_cm = client_info["transport_cm"]
                await session.__aexit__(None, None, None)
                await transport_cm.__aexit__(None, None, None)
            except Exception as e:
                logger.warning("Error closing MCP server '%s': %s", name, e)
        self._clients.clear()
        self._tools.clear()
