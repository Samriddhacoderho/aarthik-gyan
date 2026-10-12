from vectorstore.indexer import search_chunks
from schemas.mcp_outputs import FootnoteHit


def register_retrieval_tools(mcp):
    @mcp.tool()
    def retrieve_footnote_context(query: str, document_hash: str = "", top_k: int = 5) -> list[FootnoteHit]:
        """Semantic search over indexed document chunks — for fuzzy/qualitative
        questions that don't map to a specific graph relationship.
        Leave document_hash empty to search all documents."""
        results = search_chunks(query, top_k=top_k, document_hash=document_hash or None)
        return [FootnoteHit(**r) for r in results]