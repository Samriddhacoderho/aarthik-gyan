from vectorstore.indexer import search_chunks

METRIC_QUERIES = [
    "total liabilities total debt long-term debt",
    "total stockholders equity owners equity",
    "total current assets current liabilities",
    "total revenue net sales",
    "net income loss for the period",
]


def retrieve_metrics_context(document_hash: str, top_k_per_query: int = 3) -> str:
    """Targeted retrieval instead of dumping the whole document — pulls only
    the chunks most likely to contain balance sheet / income statement figures,
    filtered to this specific document so multi-doc collections don't bleed
    into each other."""
    seen = set()
    collected = []

    for query in METRIC_QUERIES:
        hits = search_chunks(query, top_k=top_k_per_query, document_hash=document_hash)
        for hit in hits:
            if hit["text"] not in seen:
                seen.add(hit["text"])
                collected.append(hit["text"])

    context = "\n\n---\n\n".join(collected)
    print(f"[metrics_retriever] Retrieved {len(collected)} unique chunks for metrics extraction.")
    return context