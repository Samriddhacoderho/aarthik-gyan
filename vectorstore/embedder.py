from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_core.documents import Document

from config import EMBEDDING_MODEL

_model = None

def get_embedder():
    """Lazy-loaded singleton — avoids reloading the model on every call."""
    global _model
    if _model is None:
        print(f"[embedder] Loading model...")
        _model = HuggingFaceEndpointEmbeddings(model=EMBEDDING_MODEL)
    return _model


def embed_text(text: str) -> list[float]:
    model = get_embedder()
    return model.embed_query(text)


def embed_texts(documents: list[Document]) -> list[list[float]]:
    """Batched embedding — much faster than calling embed_text in a loop."""
    model = get_embedder()
    embeddings = model.embed_documents([doc.page_content for doc in documents])
    return embeddings