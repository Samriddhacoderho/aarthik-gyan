"""Tools that are handed to an LLM.

The LLM never receives the raw MCP tools. It receives small wrappers that:
  * expose only the arguments the model should choose (the search text), and
  * fill in everything else (which document to search, how many hits) from code the model cannot change.
"""
from langchain_core.tools import StructuredTool

from workflow.mcp_client import NodeToolbox

HITS_PER_SEARCH = 3
MAX_CHARS_PER_HIT = 700     


def make_document_search_tool(toolbox: NodeToolbox, document_hash: str) -> StructuredTool:
    """A search tool locked to ONE document. The model only chooses `query`; document_hash is baked in."""

    async def search_this_document(query: str) -> str:
        hits = await toolbox.call("retrieve_footnote_context", {
            "query": query, "document_hash": document_hash, "top_k": HITS_PER_SEARCH,
        })
        if not hits:
            return "No matching passages were found in this document for that query."
        return "\n\n---\n\n".join(h["text"][:MAX_CHARS_PER_HIT] for h in hits)

    return StructuredTool.from_function(
        coroutine=search_this_document,
        name="search_this_document",
        description=(
            "Search the text of THIS company's annual report for passages about a topic "
            "(for example 'related party loans' or 'auditor qualified opinion'). "
            "Input: a short search phrase. Returns up to 3 passages."
        ),
    )
