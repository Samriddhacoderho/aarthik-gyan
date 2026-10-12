from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.types import TextContent

MCP_URL = "http://127.0.0.1:8000/mcp"

_tools_cache = None


async def _never_empty(request, handler):
    """Empty tool results make Groq reject the request (HTTP 400).
    Replace them with a short message the LLM can read."""
    result = await handler(request)
    if not getattr(result, "content", None):
        result.content = [
            TextContent(type="text", text="No results found for this query.")
        ]
    return result


def _strip_unsupported_keys(schema: Any) -> Any:
    """Gemini doesn't support 'additionalProperties' and warns about it."""
    if isinstance(schema, dict):
        return {
            k: _strip_unsupported_keys(v)
            for k, v in schema.items()
            if k != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_strip_unsupported_keys(v) for v in schema]
    return schema


async def get_mcp_tools():
    """Loads MCP tools once (cached). Requires `python -m mcp_server.server` running separately."""
    global _tools_cache
    if _tools_cache is None:
        client = MultiServerMCPClient(
            {
                "arthikgyaan": {
                    "url": MCP_URL,
                    "transport": "streamable_http",
                }
            },
            tool_interceptors=[_never_empty],
        )
        tools = await client.get_tools()
        for tool in tools:
            if isinstance(tool.args_schema, dict):
                tool.args_schema = _strip_unsupported_keys(tool.args_schema)
        _tools_cache = tools
        print(f"[mcp_client] Loaded {len(_tools_cache)} MCP tools: {[t.name for t in _tools_cache]}")
    return _tools_cache