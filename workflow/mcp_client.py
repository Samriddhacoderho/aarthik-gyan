"""How workflow nodes talk to the MCP server.

Each node gets a "toolbox" that only lets it call the tools on ITS allow-list. A tool that is not on the
list can't be called, and (for the LLM) is never even bound, so the model can't see it, let alone pick it.

Requires `python -m mcp_server.server` running in a separate terminal.
"""
import json
from contextlib import asynccontextmanager
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_URL = "http://127.0.0.1:8000/mcp"
SERVER_NAME = "arthikgyaan"

NODE_TOOL_ALLOWLIST: dict[str, frozenset[str]] = {
    "auditor": frozenset({"get_company_profile", "get_connected_entities", "retrieve_footnote_context"}),
    "quant": frozenset({"get_debt_ratios", "calculate_graph_centrality",
                        "retrieve_footnote_context", "save_risk_assessment"}),
}

_client: MultiServerMCPClient | None = None


def _get_client() -> MultiServerMCPClient:
    global _client
    if _client is None:
        _client = MultiServerMCPClient(
            {SERVER_NAME: {"url": MCP_URL, "transport": "streamable_http"}}
        )
    return _client


def _unwrap(result) -> Any:
    """Turns an MCP tool result into plain Python data (FastMCP wraps every return value as {"result": ...})."""
    if result.isError:
        message = " ".join(getattr(block, "text", "") for block in result.content) or "unknown error"
        raise RuntimeError(f"MCP tool failed: {message}")
    data = result.structuredContent
    if data is None:
        text = "".join(getattr(block, "text", "") for block in result.content)
        data = json.loads(text) if text else None
    if isinstance(data, dict) and set(data) == {"result"}:
        data = data["result"]
    return data


class NodeToolbox:
    """One node's connection to the MCP server. Only tools on the node's allow-list can be called."""

    def __init__(self, node: str, session):
        self.node = node
        self._session = session
        self.allowed = NODE_TOOL_ALLOWLIST[node]

    async def call(self, tool_name: str, args: dict) -> Any:
        if tool_name not in self.allowed:
            raise PermissionError(
                f"The '{self.node}' node is not allowed to call '{tool_name}'. "
                f"Allowed tools: {sorted(self.allowed)}"
            )
        return _unwrap(await self._session.call_tool(tool_name, args))


@asynccontextmanager
async def node_toolbox(node: str):
    """Opens one MCP session for a node, checks the server really has every tool the node needs,
    and hands back a toolbox limited to that node's allow-list.

        async with node_toolbox("quant") as tools:
            history = await tools.call("get_debt_ratios", {"company_id": "..."})
    """
    if node not in NODE_TOOL_ALLOWLIST:
        raise KeyError(f"No MCP allow-list defined for node '{node}'.")
    async with _get_client().session(SERVER_NAME) as session:
        on_server = {tool.name for tool in (await session.list_tools()).tools}
        missing = NODE_TOOL_ALLOWLIST[node] - on_server
        if missing:
            raise RuntimeError(
                f"The MCP server is missing tools the '{node}' node needs: {sorted(missing)}. "
                "Restart `python -m mcp_server.server` so it picks up the latest code."
            )
        print(f"[mcp_client] {node}: allowed tools = {sorted(NODE_TOOL_ALLOWLIST[node])}")
        yield NodeToolbox(node, session)
