from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
from config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION, EMBEDDING_DIM


class VectorStoreClient:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
        self._ensure_collection()
        self._ensure_indexes()

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

    def _ensure_indexes(self):
        """Qdrant requires an explicit payload index before a field can be used
        in a filter — unlike SQL, there's no implicit scan fallback. This is
        idempotent: re-creating an existing index is a safe no-op."""
        try:
            self.client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name="document_hash",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            print("[qdrant] Ensured payload index on 'document_hash'.")
        except Exception as e:
            # Already exists — Qdrant raises on duplicate index creation in some versions
            print(f"[qdrant] Payload index on 'document_hash' already present or skipped: {e}")

    def verify_connection(self):
        self.client.get_collections()
        print("[qdrant] Connected successfully.")


vector_store_client = VectorStoreClient()