from vectorstore.indexer import search_chunks


def retrieve_from_vector(question: str, top_k: int = 5) -> dict:
    results = search_chunks(question, top_k=top_k)
    return {"source": "vector", "results": results}