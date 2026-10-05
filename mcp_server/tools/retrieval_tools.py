from vectorstore.indexer import search_chunks


def register_retrieval_tools(mcp):
    @mcp.tool()
    def retrieve_footnote_context(query: str, document_hash: str = None, top_k: int = 5) -> list[dict]:
        """Semantic search over indexed document chunks — for fuzzy/qualitative
        questions that don't map to a specific graph relationship (e.g.
        'concerning statements about liquidity'). Optionally scoped to one
        document via document_hash; otherwise searches across all ingested
        documents."""
        return search_chunks(query, top_k=top_k, document_hash=document_hash)