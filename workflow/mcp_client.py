import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

_tools_cache = None


async def _load_tools_async():
    client = MultiServerMCPClient({
        "arthikgyaan": {
            "url": "http://127.0.0.1:8000/mcp",
            "transport": "streamable_http",
        }
    })
    return await client.get_tools()


def get_mcp_tools():
    """Loads MCP tools once, cached. Requires mcp_server/server.py already
    running separately (python -m mcp_server.server) since this connects over
    HTTP rather than spawning the server itself."""
    global _tools_cache
    if _tools_cache is None:
        _tools_cache = asyncio.run(_load_tools_async())
        print(f"[mcp_client] Loaded {len(_tools_cache)} MCP tools: "
              f"{[t.name for t in _tools_cache]}")
    return _tools_cache