from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION, EMBEDDING_DIM


class VectorStoreClient:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if QDRANT_COLLECTION not in existing:
            self.client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            print(f"[qdrant] Created collection '{QDRANT_COLLECTION}'.")
        else:
            print(f"[qdrant] Collection '{QDRANT_COLLECTION}' already exists.")

    def verify_connection(self):
        self.client.get_collections()
        print("[qdrant] Connected successfully.")


vector_store_client = VectorStoreClient()