from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    type: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    type: str
    detail: str | None = None


@dataclass(frozen=True)
class BenchmarkQuestion:
    id: str
    question: str
    answer: str
    answer_aliases: tuple[str, ...]
    evidence: tuple[str, ...]
    hops: int
    question_type: str

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "answer_aliases": list(self.answer_aliases),
            "evidence": list(self.evidence),
            "hops": self.hops,
            "question_type": self.question_type,
        }


@dataclass
class RetrievalRecord:
    question_id: str
    question_type: str
    system: str
    hops: int
    latency_ms: float
    evidence_recall: float
    retrieval_hit: bool
    contexts: list[str] = field(default_factory=list)
    answer: str | None = None
    answer_correct: bool | None = None
    answer_latency_ms: float | None = None
    hallucination: bool | None = None
    hallucination_reason: str | None = None
    error: str | None = None
