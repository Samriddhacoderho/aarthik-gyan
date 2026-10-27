from fastmcp.exceptions import ToolError as McpToolError
from vectorstore.indexer import search_chunks
from schemas.mcp_outputs import FootnoteHit

MAX_TOP_K = 10


def register_retrieval_tools(mcp):
    @mcp.tool()
    def retrieve_footnote_context(query: str, document_hash: str, top_k: int = 5) -> list[FootnoteHit]:
        """Semantic search over the indexed chunks of ONE document — for fuzzy/qualitative
        questions that don't map to a specific graph relationship.
        document_hash is required: searching "all documents" is not allowed, because text from
        other companies' reports must never mix into one company's analysis."""
        if not document_hash or not document_hash.strip():
            raise McpToolError("document_hash is required: this tool only searches one document at a time.")
        top_k = max(1, min(top_k, MAX_TOP_K))
        results = search_chunks(query, top_k=top_k, document_hash=document_hash)
        return [FootnoteHit(**r) for r in results]
