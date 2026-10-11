from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from config import EMBEDDING_MODEL

_model = None


def get_embedder():
    """Lazy-loaded singleton. Runs locally via sentence-transformers: no API, no credits."""
    global _model
    if _model is None:
        print("[embedder] Loading local model (first run downloads ~90MB)...")
        _model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            encode_kwargs={"normalize_embeddings": True, "batch_size": 64},
        )
    return _model


def embed_text(text: str) -> list[float]:
    return get_embedder().embed_query(text)


def embed_texts(documents: list[Document]) -> list[list[float]]:
    return get_embedder().embed_documents([doc.page_content for doc in documents])