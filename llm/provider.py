from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from config import GROQ_MODEL, GEMINI_MODEL

_chain = None


def get_llm():
    """Returns a chat model with automatic fallback: Groq first, Gemini if Groq
    errors (rate limit, 5xx, timeout, etc). Cached as a module-level singleton
    since building the chain is cheap but we don't need to redo it every call."""
    global _chain
    if _chain is None:
        primary = ChatGroq(model=GROQ_MODEL, temperature=0)
        fallback = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0)
        _chain = primary.with_fallbacks([fallback])
        print(f"[llm] Provider chain ready: {GROQ_MODEL} -> {GEMINI_MODEL}")
    return _chain