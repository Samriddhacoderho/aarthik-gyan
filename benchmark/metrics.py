from __future__ import annotations

import math
import re
from typing import Any, Iterable

_WORD = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase and reduce to alphanumeric tokens separated by single spaces."""

    return " ".join(_WORD.findall((text or "").lower()))


def _contains(haystack: str, needle: str) -> bool:
    """Whole-token containment, so '1' does not match inside '10'."""

    candidate = normalize(needle)
    if not candidate:
        return False
    if candidate == haystack:
        return True
    return f" {candidate} " in f" {haystack} "


def evidence_recall(evidence: Iterable[str], contexts: Iterable[str]) -> float:
    items = [item for item in evidence if item and item.strip()]
    if not items:
        return 0.0
    haystack = normalize(" \n ".join(contexts))
    found = sum(1 for item in items if _contains(haystack, item))
    return found / len(items)


def retrieval_hit(evidence: Iterable[str], contexts: Iterable[str]) -> bool:
    return evidence_recall(evidence, contexts) > 0.0


def answer_correct(predicted: str | None, answer: str, aliases: Iterable[str] = ()) -> bool:
    """Conservative correctness check.

    A prediction is correct when a gold answer (or a supplied alias) appears as a
    whole token sequence. Numeric answers therefore match only exact tokens.
    This is deliberately strict: a benchmark must not award credit for a
    coincidental substring.
    """

    if not predicted or not predicted.strip():
        return False
    haystack = normalize(predicted)
    candidates = [answer, *aliases]
    for candidate in candidates:
        if candidate and _contains(haystack, candidate):
            return True
    return False


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def flatten_retrieval(value: Any) -> list[str]:
    """Turn arbitrary graph/vector retrieval output into text used for evidence matching."""

    out: list[str] = []

    def walk(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            for key, nested in item.items():
                if key in {"cypher", "source"}:
                    # The generated query is useful provenance, but it is not retrieved evidence.
                    continue
                walk(nested)
        elif isinstance(item, (list, tuple, set)):
            for nested in item:
                walk(nested)
        else:
            out.append(str(item))

    walk(value)
    return out


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate raw records without inventing missing measurements."""

    summary: dict[str, Any] = {}
    systems = sorted({record["system"] for record in records})
    for system in systems:
        rows = [record for record in records if record["system"] == system]
        ok = [row for row in rows if not row.get("error")]
        latencies = [float(row["latency_ms"]) for row in ok if row.get("latency_ms") is not None]
        answer_latencies = [
            float(row["answer_latency_ms"])
            for row in ok
            if row.get("answer_latency_ms") is not None
        ]
        answered = [row for row in ok if row.get("answer_correct") is not None]
        judged = [row for row in ok if row.get("hallucination") is not None]

        summary[system] = {
            "questions": len(rows),
            "successful_retrievals": len(ok),
            "errors": len(rows) - len(ok),
            "evidence_recall_mean": _mean([row["evidence_recall"] for row in ok]),
            "retrieval_hit_rate": _mean([1.0 if row["retrieval_hit"] else 0.0 for row in ok]),
            "retrieval_latency_ms_mean": _mean(latencies),
            "retrieval_latency_ms_p50": percentile(latencies, 0.50),
            "retrieval_latency_ms_p95": percentile(latencies, 0.95),
            "answer_accuracy": _mean(
                [1.0 if row["answer_correct"] else 0.0 for row in answered]
            ),
            "answered": len(answered),
            "answer_latency_ms_mean": _mean(answer_latencies),
            "answer_latency_ms_p50": percentile(answer_latencies, 0.50),
            "hallucination_rate": _mean(
                [1.0 if row["hallucination"] else 0.0 for row in judged]
            ),
            "judged": len(judged),
            "by_question_type": _by_type(ok),
        }
    return summary


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _by_type(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted({row["question_type"] for row in rows}):
        subset = [row for row in rows if row["question_type"] == key]
        result[key] = {
            "questions": len(subset),
            "evidence_recall_mean": _mean([row["evidence_recall"] for row in subset]),
            "retrieval_hit_rate": _mean(
                [1.0 if row["retrieval_hit"] else 0.0 for row in subset]
            ),
        }
    return result
