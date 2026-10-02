import uuid
from qdrant_client.models import PointStruct
from vectorstore.qdrant_client import vector_store_client
from vectorstore.embedder import embed_texts
from config import QDRANT_COLLECTION
from langchain_core.documents import Document
from qdrant_client.models import Filter, FieldCondition, MatchValue


def index_chunks(chunks: list[Document], filename: str, file_hash: str, batch_size: int = 64):
    """Embeds all chunks, then upserts into Qdrant in smaller batches —
    a single upsert of hundreds of points can exceed the client's write timeout
    over a network connection to a cloud cluster."""
    if not chunks:
        return

    embeddings = embed_texts(chunks)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "text": chunk.page_content,
                "filename": filename,
                "document_hash": file_hash,
                "chunk_index": i,
            },
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    total = len(points)
    for start in range(0, total, batch_size):
        batch = points[start:start + batch_size]
        vector_store_client.client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
        print(f"[indexer] Upserted {min(start + batch_size, total)}/{total} points into Qdrant.")

    print(f"[indexer] Finished indexing {total} chunks from '{filename}' into Qdrant.")
    
    

def search_chunks(query: str, top_k: int = 5, document_hash: str | None = None) -> list[dict]:
    from vectorstore.embedder import embed_text

    query_vector = embed_text(query)
    search_filter = None
    if document_hash:
        search_filter = Filter(must=[FieldCondition(key="document_hash", match=MatchValue(value=document_hash))])

    results = vector_store_client.client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_vector,
        query_filter=search_filter,
        limit=top_k,
    )
    return [{"text": hit.payload["text"], "filename": hit.payload["filename"], "score": hit.score} for hit in results]