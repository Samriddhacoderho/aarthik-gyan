from vectorstore.indexer import search_chunks

METRIC_QUERIES = [
    "total liabilities total debt long-term debt",
    "total stockholders equity owners equity",
    "total current assets current liabilities",
    "total revenue net sales",
    "net income loss for the period",
]


def metric_queries(extra_queries: list[str] | None = None) -> list[str]:
    """The search texts used to find balance-sheet / income-statement chunks (+ optional analyst hint).
    Shared by the ingestion path (direct search) and the review workflow (MCP search)."""
    return METRIC_QUERIES + [q for q in (extra_queries or []) if q and q.strip()]


def merge_unique(chunk_texts: list[str]) -> str:
    """Joins retrieved chunk texts into one context string, dropping exact duplicates."""
    seen = set()
    collected = []
    for text in chunk_texts:
        if text not in seen:
            seen.add(text)
            collected.append(text)
    print(f"[metrics_retriever] Retrieved {len(collected)} unique chunks for metrics extraction.")
    return "\n\n---\n\n".join(collected)


def retrieve_metrics_context(document_hash: str, top_k_per_query: int = 3,
                             extra_queries: list[str] | None = None) -> str:
    """Targeted retrieval instead of dumping the whole document — pulls only
    the chunks most likely to contain balance sheet / income statement figures,
    filtered to this specific document so multi-doc collections don't bleed
    into each other.

    extra_queries: optional extra search texts (for example an analyst's hint such as
    "current assets are on the balance sheet") so a re-run can look in new places."""
    texts = []
    for query in metric_queries(extra_queries):
        texts.extend(hit["text"] for hit in search_chunks(query, top_k=top_k_per_query, document_hash=document_hash))
    return merge_unique(texts)
