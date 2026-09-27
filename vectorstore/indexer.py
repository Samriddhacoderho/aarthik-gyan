import uuid
from qdrant_client.models import PointStruct
from vectorstore.qdrant_client import vector_store_client
from vectorstore.embedder import embed_texts
from config import QDRANT_COLLECTION
from langchain_core.documents import Document


def index_chunks(chunks: list[Document], filename: str, file_hash: str):
    """Embeds each chunk and upserts into Qdrant, tagged with source metadata
    so retrieval results can be traced back to the originating document."""
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

    vector_store_client.client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    print(f"[indexer] Indexed {len(points)} chunks from '{filename}' into Qdrant.")


def search_chunks(query: str, top_k: int = 5) -> list[dict]:
    """Semantic search — returns the top_k most similar chunks with their metadata."""
    from vectorstore.embedder import embed_text

    query_vector = embed_text(query)
    results = vector_store_client.client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_vector,
        limit=top_k,
    )

    return [
        {
            "text": hit.payload["text"],
            "filename": hit.payload["filename"],
            "score": hit.score,
        }
        for hit in results
    ]