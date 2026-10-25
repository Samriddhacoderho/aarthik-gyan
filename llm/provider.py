
import threading
import time
import math
import random
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableLambda

from config import GROQ_MODEL, GEMINI_MODEL, LLM_TIMEOUT_SECONDS


_chain = None
_lock = threading.Lock()


def get_llm():
    """Groq first, Gemini fallback using LangChain's built-in fallback."""
    global _chain

    if _chain is None:
        with _lock:
            if _chain is None:
                primary = ChatGroq(
                    model=GROQ_MODEL,
                    temperature=0,
                    timeout=LLM_TIMEOUT_SECONDS,
                    max_retries=0,
                )

                fallback = ChatGoogleGenerativeAI(
                    model=GEMINI_MODEL,
                    temperature=0,
                    timeout=LLM_TIMEOUT_SECONDS,
                    max_retries=1,
                )

                _chain = primary.with_fallbacks([fallback])
                print(
                    f"[llm] Provider chain ready: "
                    f"{GROQ_MODEL} -> {GEMINI_MODEL}"
                )

    return _chain


# ---- Cooldown configuration (seconds) ---------------------------------------

COOLDOWN_BASE_SECONDS = 15
COOLDOWN_CAP_SECONDS = 60
OTHER_ERROR_COOLDOWN_SECONDS = 10

SERVER_ERROR_RETRY_SECONDS = 2.0
SERVER_ERROR_JITTER_SECONDS = 1.0

RETRY_DELAY_MIN_SECONDS = 0.5
RETRY_DELAY_MAX_SECONDS = 120.0
PROVIDER_DELAY_MARGIN_SECONDS = 0.5

WAKE_JITTER_SECONDS = 0.5
TOTAL_TIME_BUDGET_SECONDS = 180
MAX_ROUNDS = 3

_state_lock = threading.Lock()
_slots = None


class AllProvidersExhausted(Exception):
    """Raised when the provider router cannot obtain a successful response."""
    pass


class _ProviderSlot:
    def __init__(self, name, model):
        self.name = name
        self.model = model
        self.cooldown_until = 0.0
        self.consecutive_rate_limits = 0


def _get_slots():
    """Initialize the shared Groq/Gemini extraction providers once."""
    global _slots

    if _slots is None:
        with _lock:
            if _slots is None:
                groq = ChatGroq(
                    model=GROQ_MODEL,
                    temperature=0,
                    timeout=LLM_TIMEOUT_SECONDS,
                    max_retries=0,
                )

                gemini = ChatGoogleGenerativeAI(
                    model=GEMINI_MODEL,
                    temperature=0,
                    timeout=LLM_TIMEOUT_SECONDS,
                    max_retries=0,
                )

                # List order defines provider priority.
                _slots = [
                    _ProviderSlot("groq", groq),
                    _ProviderSlot("gemini", gemini),
                ]

                print(
                    f"[llm] Extraction router ready: "
                    f"{GROQ_MODEL} -> {GEMINI_MODEL}"
                )

    return _slots


# ---- Error classification ----------------------------------------------------

_SERVER_ERROR_CODES = {500, 502, 503, 504}

_RATE_LIMIT_WORDS = (
    "429",
    "rate limit",
    "rate_limit",
    "resource_exhausted",
    "quota",
)

_SERVER_ERROR_WORDS = (
    "unavailable",
    "overloaded",
    "high demand",
)


def _error_chain(error: BaseException, limit: int = 5) -> list:
    """Inspect the original error and exceptions wrapping it."""
    chain = []
    seen = set()
    current = error

    while (
        current is not None
        and id(current) not in seen
        and len(chain) < limit
    ):
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__

    return chain


def _status_code(error: BaseException) -> int | None:
    """Extract a numeric HTTP status from an exception or its response."""
    for err in _error_chain(error):
        response = getattr(err, "response", None)

        candidates = (
            getattr(err, "status_code", None),
            getattr(err, "code", None),
            getattr(response, "status_code", None),
        )

        for candidate in candidates:
            if (
                isinstance(candidate, int)
                and not isinstance(candidate, bool)
                and 100 <= candidate <= 599
            ):
                return candidate

    return None


def _classify_error(error: BaseException) -> str:
    """Classify errors as rate limits, server errors, or other errors."""
    status = _status_code(error)

    if status == 429:
        return "rate"

    if status in _SERVER_ERROR_CODES:
        return "server"

    text = str(error).lower()

    if any(word in text for word in _RATE_LIMIT_WORDS):
        return "rate"

    if any(word in text for word in _SERVER_ERROR_WORDS):
        return "server"

    return "other"


# ---- Provider retry-delay parsing ------------------------------------------

_UNIT_SECONDS = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
}

_DURATION_PART = re.compile(
    r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)(?![a-z])",
    re.IGNORECASE,
)

_RETRY_TEXT = re.compile(
    r"(?:try again|retry[\s_-]?delay|retry[\s_-]?after|retry)"
    r"\D{0,20}?"
    r"((?:\d+(?:\.\d+)?\s*(?:ms|h|m|s)(?![a-z])\s*)+)",
    re.IGNORECASE,
)

_RETRY_KEYS = {"retrydelay", "retry_delay"}


def _parse_duration(text: str) -> float | None:
    """Parse durations such as 21.5s, 1m30.5s, or 850ms."""
    parts = _DURATION_PART.findall(text or "")

    if not parts:
        return None

    return sum(
        float(number) * _UNIT_SECONDS[unit.lower()]
        for number, unit in parts
    )


def _sanitize_delay(value) -> float | None:
    """Validate and clamp a delay to the configured range."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(seconds) or seconds <= 0:
        return None

    return min(
        max(seconds, RETRY_DELAY_MIN_SECONDS),
        RETRY_DELAY_MAX_SECONDS,
    )


def _delay_from_headers(error) -> float | None:
    """Read Retry-After or Retry-After-Ms from an error."""
    response = getattr(error, "response", None)

    headers = (
        getattr(response, "headers", None)
        or getattr(error, "headers", None)
    )

    if not headers:
        return None

    try:
        lowered = {
            str(key).lower(): value
            for key, value in headers.items()
        }
    except Exception:
        return None

    if "retry-after-ms" in lowered:
        try:
            return float(lowered["retry-after-ms"]) / 1000.0
        except (TypeError, ValueError):
            pass

    value = lowered.get("retry-after")

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    try:
        when = parsedate_to_datetime(str(value))

        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)

        return (
            when - datetime.now(timezone.utc)
        ).total_seconds()

    except Exception:
        return None


def _value_to_seconds(value) -> float | None:
    """Convert structured retry-delay values into seconds."""
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return _parse_duration(value)

    if isinstance(value, dict) and "seconds" in value:
        try:
            return (
                float(value["seconds"])
                + float(value.get("nanos", 0)) / 1e9
            )
        except (TypeError, ValueError):
            return None

    return None


def _search_structured(obj, depth: int = 0) -> float | None:
    """Find retryDelay fields in nested provider error details."""
    if depth > 6:
        return None

    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in _RETRY_KEYS:
                seconds = _sanitize_delay(
                    _value_to_seconds(value)
                )

                if seconds is not None:
                    return seconds

        children = list(obj.values())

    elif isinstance(obj, (list, tuple)):
        children = list(obj)

    else:
        return None

    for child in children:
        seconds = _search_structured(child, depth + 1)

        if seconds is not None:
            return seconds

    return None


def _extract_retry_delay(
    error: BaseException,
) -> float | None:
    """Extract a provider retry hint from headers, details, or message text."""
    for err in _error_chain(error):
        try:
            seconds = _sanitize_delay(
                _delay_from_headers(err)
            )

            if seconds is None:
                for attribute in ("details", "body"):
                    seconds = _search_structured(
                        getattr(err, attribute, None)
                    )

                    if seconds is not None:
                        break

            if seconds is None:
                match = _RETRY_TEXT.search(str(err))

                if match:
                    seconds = _sanitize_delay(
                        _parse_duration(match.group(1))
                    )

            if seconds is not None:
                return seconds

        except Exception:
            # An unusual error object must not break failover.
            continue

    return None


# ---- Shared cooldown management --------------------------------------------


def _record_failure(
    slot: _ProviderSlot,
    error: BaseException,
) -> None:
    """Apply a shared cooldown after a provider failure."""
    kind = _classify_error(error)
    hint = _extract_retry_delay(error)

    with _state_lock:
        now = time.monotonic()
        already_cooling = slot.cooldown_until > now

        source = (
            "provider-specified"
            if hint is not None
            else "fallback"
        )

        if kind == "rate":
            # Concurrent failures should not each escalate the counter.
            if not already_cooling:
                slot.consecutive_rate_limits += 1

            if hint is not None:
                cooldown = (
                    hint + PROVIDER_DELAY_MARGIN_SECONDS
                )
            else:
                exponent = max(
                    slot.consecutive_rate_limits, 1
                ) - 1

                cooldown = min(
                    COOLDOWN_CAP_SECONDS,
                    COOLDOWN_BASE_SECONDS * 2 ** exponent,
                )

            label = "rate-limited"

        elif kind == "server":
            if hint is not None:
                cooldown = (
                    hint + PROVIDER_DELAY_MARGIN_SECONDS
                )
            else:
                cooldown = (
                    SERVER_ERROR_RETRY_SECONDS
                    + random.uniform(
                        0.0,
                        SERVER_ERROR_JITTER_SECONDS,
                    )
                )
                source = "short retry + jitter"

            label = "server error"

        else:
            cooldown = OTHER_ERROR_COOLDOWN_SECONDS
            source = "fallback"
            label = type(error).__name__

        # Never shorten a cooldown another thread already set.
        slot.cooldown_until = max(
            slot.cooldown_until,
            now + cooldown,
        )

    print(
        f"[llm] {slot.name} {label} -> "
        f"cooling {cooldown:.1f}s ({source}), "
        f"trying next provider"
    )


# ---- Groq -> Gemini failover router ----------------------------------------


def _failover_invoke(
    prompt_value,
    max_rounds: int = MAX_ROUNDS,
):
    """Invoke providers in priority order with shared cooldowns.

    Waiting for cooldowns does not consume a round. The total time budget
    limits waiting; a running request may still last up to its own timeout.
    """
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")

    slots = _get_slots()
    deadline = (
        time.monotonic() + TOTAL_TIME_BUDGET_SECONDS
    )

    rounds_used = 0
    last_error = None

    while rounds_used < max_rounds:
        with _state_lock:
            now = time.monotonic()

            ready = [
                slot
                for slot in slots
                if slot.cooldown_until <= now
            ]

            earliest = min(
                slot.cooldown_until for slot in slots
            )

        if now >= deadline:
            raise AllProvidersExhausted(
                f"Time budget of "
                f"{TOTAL_TIME_BUDGET_SECONDS}s used up. "
                f"Last error: {last_error}"
            )

        if not ready:
            # Waiting for cooldowns does not consume a round.
            wait = (
                earliest - now
                + random.uniform(0.0, WAKE_JITTER_SECONDS)
            )

            if now + wait > deadline:
                raise AllProvidersExhausted(
                    "Providers are cooling down longer than "
                    f"the {TOTAL_TIME_BUDGET_SECONDS}s budget "
                    f"allows. Last error: {last_error}"
                )

            print(
                "[llm] all providers cooling down; "
                f"waiting {wait:.1f}s"
            )

            time.sleep(wait)
            continue

        attempted = False

        # Preserve priority: Groq first, Gemini second.
        for slot in ready:
            with _state_lock:
                if (
                    slot.cooldown_until
                    > time.monotonic()
                ):
                    # Another thread may have cooled this provider.
                    continue

            attempted = True

            try:
                response = slot.model.invoke(prompt_value)

                with _state_lock:
                    slot.consecutive_rate_limits = 0

                return response

            except Exception as error:
                last_error = error
                _record_failure(slot, error)

        if attempted:
            rounds_used += 1

    raise AllProvidersExhausted(
        f"All providers failed after {max_rounds} "
        f"round(s): {last_error}"
    )


def get_extraction_llm(
    max_rounds: int | None = None,
):
    """Return a cooldown-aware Groq -> Gemini runnable.

    max_rounds=1 permits one round of real provider attempts.
    Larger values permit more rounds, subject to the time budget.
    """
    rounds = (
        max_rounds
        if max_rounds is not None
        else MAX_ROUNDS
    )

    if rounds < 1:
        raise ValueError("max_rounds must be at least 1")

    def _call(prompt_value):
        return _failover_invoke(
            prompt_value,
            rounds,
        )

    return RunnableLambda(_call)
