import threading
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from config import GROQ_MODEL, GEMINI_MODEL, LLM_TIMEOUT_SECONDS
import time
from langchain_core.runnables import RunnableLambda

_chain = None
_lock = threading.Lock()


def get_llm():
    """Groq first, Gemini on any Groq error. Both have hard request timeouts so
    a stalled connection fails (and triggers fallback) instead of hanging forever.
    Groq's own SDK retries are off (max_retries=0): tenacity + the fallback chain
    already handle retries, and stacking them just burns time during rate limits."""
    global _chain
    if _chain is None:
        with _lock:
            if _chain is None:
                primary = ChatGroq(
                    model=GROQ_MODEL, temperature=0,
                    timeout=LLM_TIMEOUT_SECONDS, max_retries=0,
                )
                fallback = ChatGoogleGenerativeAI(
                    model=GEMINI_MODEL, temperature=0,
                    timeout=LLM_TIMEOUT_SECONDS, max_retries=1,
                )
                _chain = primary.with_fallbacks([fallback])
                print(f"[llm] Provider chain ready: {GROQ_MODEL} -> {GEMINI_MODEL}")
    return _chain

COOLDOWN_BASE_SECONDS = 15      
COOLDOWN_CAP_SECONDS = 60
OTHER_ERROR_COOLDOWN_SECONDS = 10
MAX_ROUNDS = 3                 

_state_lock = threading.Lock()
_slots = None


class AllProvidersExhausted(Exception):
    pass


class _ProviderSlot:
    def __init__(self, name, model):
        self.name = name
        self.model = model
        self.cooldown_until = 0.0
        self.consecutive_rate_limits = 0


def _get_slots():
    global _slots
    if _slots is None:
        with _lock:
            if _slots is None:
                groq = ChatGroq(model=GROQ_MODEL, temperature=0,
                                timeout=LLM_TIMEOUT_SECONDS, max_retries=0)
                gemini = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0,
                                                timeout=LLM_TIMEOUT_SECONDS, max_retries=0)
                _slots = [_ProviderSlot("groq", groq), _ProviderSlot("gemini", gemini)]  # order = priority
                print(f"[llm] Extraction router ready: {GROQ_MODEL} -> {GEMINI_MODEL}")
    return _slots


def _is_rate_limit(error: Exception) -> bool:
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status == 429:
        return True
    text = str(error).lower()
    return any(k in text for k in ("429", "rate limit", "rate_limit", "resource_exhausted", "quota"))


def _failover_invoke(prompt_value, max_rounds: int = MAX_ROUNDS):
    slots = _get_slots()
    last_error = None

    for _ in range(max_rounds):
        with _state_lock:
            now = time.monotonic()
            ready = [s for s in slots if s.cooldown_until <= now]
            earliest = min(s.cooldown_until for s in slots)

        if not ready:
            wait = max(0.0, earliest - now) + 0.5
            print(f"[llm] all providers cooling down; waiting {wait:.0f}s")
            time.sleep(wait)
            with _state_lock:
                now = time.monotonic()
                ready = [s for s in slots if s.cooldown_until <= now]

        for slot in ready:  # Groq first, Gemini second
            try:
                response = slot.model.invoke(prompt_value)
                with _state_lock:
                    slot.consecutive_rate_limits = 0
                return response
            except Exception as e:
                last_error = e
                with _state_lock:
                    if _is_rate_limit(e):
                        slot.consecutive_rate_limits += 1
                        cooldown = min(COOLDOWN_CAP_SECONDS,
                                       COOLDOWN_BASE_SECONDS * 2 ** (slot.consecutive_rate_limits - 1))
                        kind = "rate-limited"
                    else:
                        cooldown = OTHER_ERROR_COOLDOWN_SECONDS
                        kind = type(e).__name__
                    slot.cooldown_until = time.monotonic() + cooldown
                print(f"[llm] {slot.name} {kind} -> cooling {cooldown:.0f}s, trying next provider")

    raise AllProvidersExhausted(f"All providers failed after {max_rounds} round(s): {last_error}")


def get_extraction_llm(max_rounds: int | None = None):
    """Cooldown-aware Groq -> Gemini router for every plain prompt | llm | parser chain.
    max_rounds=1 means exactly: try Groq, then Gemini, then fail. Higher values let the router
    wait out a rate-limit cooldown and try again (good for big batch jobs)."""
    rounds = max_rounds or MAX_ROUNDS

    def _call(prompt_value):
        return _failover_invoke(prompt_value, rounds)

    return RunnableLambda(_call)

