from fastmcp import FastMCP
from mcp_server.tools.risk_tools import register_risk_tools
from mcp_server.tools.graph_tools import register_graph_tools
from mcp_server.tools.retrieval_tools import register_retrieval_tools



mcp = FastMCP("arthikgyaan")

register_graph_tools(mcp)
register_risk_tools(mcp)
register_retrieval_tools(mcp)

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)