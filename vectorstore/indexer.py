import uuid
from qdrant_client.models import FilterSelector, PointStruct
from vectorstore.qdrant_client import vector_store_client
from vectorstore.embedder import embed_texts
from config import QDRANT_COLLECTION
from langchain_core.documents import Document
from qdrant_client.models import Filter, FieldCondition, MatchValue


def index_chunks(chunks: list[Document], filename: str, file_hash: str, batch_size: int = 64):
    """Idempotent: clears this document's old points, then upserts with deterministic ids,
    so re-running ingestion never creates duplicate chunks."""
    if not chunks:
        return

    vector_store_client.client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=FilterSelector(filter=Filter(
            must=[FieldCondition(key="document_hash", match=MatchValue(value=file_hash))]
        )),
    )

    embeddings = embed_texts(chunks)
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{file_hash}:{i}")),
            vector=embedding,
            payload={"text": chunk.page_content, "filename": filename,
                     "document_hash": file_hash, "chunk_index": i},
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    total = len(points)
    for start in range(0, total, batch_size):
        vector_store_client.client.upsert(collection_name=QDRANT_COLLECTION, points=points[start:start + batch_size])
        print(f"[indexer] Upserted {min(start + batch_size, total)}/{total} points into Qdrant.")
    print(f"[indexer] Finished indexing {total} chunks from '{filename}' into Qdrant.")
    
    

def search_chunks(query: str, top_k: int = 5, document_hash: str | None = None) -> list[dict]:
    from vectorstore.embedder import embed_text

    query_vector = embed_text(query)

    search_filter = None
    if document_hash:
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="document_hash",
                    match=MatchValue(value=document_hash),
                )
            ]
        )

    results = vector_store_client.client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=search_filter,
        limit=top_k,
    )

    return [
        {
            "text": hit.payload["text"],
            "filename": hit.payload["filename"],
            "score": hit.score,
        }
        for hit in results.points
    ]
