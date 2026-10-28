"""Run the GraphRAG vs plain-vector-RAG benchmark.

The harness never invents results. If no dataset exists it stops and explains
how to generate one. Retrieval calls go through the real V3 components:

    GraphRAG : retrieval.router.route_question
    Vector   : vectorstore.indexer.search_chunks

Answer generation reuses the same ANSWER_PROMPT and model factory as
``agent.qa_agent`` so both systems are compared with one answering policy.

Examples:
    python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --limit 5
    python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --answer
    python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --answer --judge
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from benchmark.metrics import (
    answer_correct,
    evidence_recall,
    flatten_retrieval,
    retrieval_hit,
    summarize,
)
from benchmark.models import RetrievalRecord

DEFAULT_DATASET = Path("benchmark/questions.jsonl")
DEFAULT_OUTPUT = Path("benchmark/results/latest.json")

JUDGE_PROMPT = """You are a strict evaluation judge. Decide whether the ANSWER is fully supported
by the RETRIEVED EVIDENCE. Do not use outside knowledge.

Return ONLY a JSON object with this shape:
{{"supported": true or false, "reason": "one sentence"}}

QUESTION:
{question}

RETRIEVED EVIDENCE:
{evidence}

ANSWER:
{answer}
"""


def load_dataset(path: Path, limit: int | None) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {path}\n"
            "Generate a read-only dataset from the live graph first:\n"
            "  python -m benchmark.generate_questions --count 50"
        )
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON") from exc
            if not row.get("question") or not row.get("answer") or not row.get("evidence"):
                raise ValueError(
                    f"{path}:{line_number} needs question, answer and evidence fields"
                )
            row.setdefault("id", f"q{line_number:03d}")
            row.setdefault("answer_aliases", [])
            row.setdefault("hops", 2)
            row.setdefault("question_type", "unknown")
            rows.append(row)
    if not rows:
        raise ValueError(f"Dataset {path} is empty.")
    return rows[:limit] if limit else rows


def build_graphrag_retriever() -> Callable[[str], Any]:
    from retrieval.router import route_question

    return route_question


def build_vector_retriever(top_k: int) -> Callable[[str], Any]:
    from vectorstore.indexer import search_chunks

    def retrieve(question: str) -> dict[str, Any]:
        return {"source": "vector", "results": search_chunks(question, top_k=top_k)}

    return retrieve


def answer_with_results(question: str, results: Any) -> str:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate

    from llm.provider import get_extraction_llm
    from prompts.answer_prompt import ANSWER_PROMPT

    prompt = PromptTemplate(template=ANSWER_PROMPT, input_variables=["question", "results"])
    chain = prompt | get_extraction_llm(max_rounds=1) | StrOutputParser()
    return chain.invoke(
        {"question": question, "results": json.dumps(results, indent=2, default=str)}
    ).strip()


def judge_answer(question: str, answer: str, contexts: list[str]) -> tuple[bool, str]:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate

    from llm.provider import get_extraction_llm

    prompt = PromptTemplate(
        template=JUDGE_PROMPT,
        input_variables=["question", "evidence", "answer"],
    )
    chain = prompt | get_extraction_llm(max_rounds=1) | StrOutputParser()
    raw = chain.invoke(
        {
            "question": question,
            "evidence": "\n\n".join(contexts)[:12000],
            "answer": answer,
        }
    ).strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise ValueError("Judge did not return JSON")
    parsed = json.loads(match.group(0))
    supported = parsed.get("supported")
    if not isinstance(supported, bool):
        raise ValueError("Judge JSON has no boolean 'supported' field")
    return (not supported), str(parsed.get("reason") or "")


def _truncate(contexts: list[str], limit: int = 1600) -> list[str]:
    return [text if len(text) <= limit else text[:limit] + "…" for text in contexts]


def run(args: argparse.Namespace) -> tuple[dict[str, Any], list[RetrievalRecord]]:
    rows = load_dataset(args.dataset, args.limit)
    systems = [item.strip() for item in args.systems.split(",") if item.strip()]
    unknown = set(systems) - {"graphrag", "vector"}
    if unknown:
        raise ValueError(f"Unknown systems: {sorted(unknown)}")

    retrievers: dict[str, Callable[[str], Any]] = {}
    if "graphrag" in systems:
        retrievers["graphrag"] = build_graphrag_retriever()
    if "vector" in systems:
        retrievers["vector"] = build_vector_retriever(args.top_k)

    records: list[RetrievalRecord] = []
    for row in rows:
        for system in systems:
            record = RetrievalRecord(
                question_id=row["id"],
                question_type=row["question_type"],
                system=system,
                hops=int(row["hops"]),
                latency_ms=0.0,
                evidence_recall=0.0,
                retrieval_hit=False,
            )
            try:
                started = time.perf_counter()
                raw_results = retrievers[system](row["question"])
                record.latency_ms = (time.perf_counter() - started) * 1000
                contexts = flatten_retrieval(raw_results)
                record.contexts = _truncate(contexts)
                record.evidence_recall = evidence_recall(row["evidence"], contexts)
                record.retrieval_hit = retrieval_hit(row["evidence"], contexts)

                if args.answer:
                    started = time.perf_counter()
                    record.answer = answer_with_results(row["question"], raw_results)
                    record.answer_latency_ms = (time.perf_counter() - started) * 1000
                    record.answer_correct = answer_correct(
                        record.answer,
                        row["answer"],
                        row.get("answer_aliases") or [],
                    )
                    if args.judge:
                        hallucination, reason = judge_answer(
                            row["question"], record.answer, contexts
                        )
                        record.hallucination = hallucination
                        record.hallucination_reason = reason
            except Exception as exc:
                record.error = f"{type(exc).__name__}: {exc}"
            records.append(record)
            print(
                f"[{record.question_id}] {system}: recall={record.evidence_recall:.2f} "
                f"hit={record.retrieval_hit} "
                + (f"correct={record.answer_correct} " if args.answer else "")
                + (f"error={record.error}" if record.error else "")
            )

    summary = summarize([record.__dict__ for record in records])
    payload = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset": str(args.dataset),
            "questions": len(rows),
            "systems": systems,
            "top_k_vector": args.top_k,
            "answers_generated": bool(args.answer),
            "hallucination_judged": bool(args.judge),
            "note": (
                "Retrieval uses the real V3 router/vector store. Answer generation reuses "
                "the V3 ANSWER_PROMPT and model factory. Any missing metric means it was "
                "not measured in this run."
            ),
        },
        "summary": summary,
        "records": [record.__dict__ for record in records],
    }
    return payload, records


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    metadata = payload["metadata"]
    lines = [
        "# Aarthik Gyan GraphRAG benchmark",
        "",
        f"- Run at: `{metadata['generated_at']}`",
        f"- Dataset: `{metadata['dataset']}` ({metadata['questions']} questions)",
        f"- Systems: {', '.join(metadata['systems'])}",
        f"- Vector top-k: {metadata['top_k_vector']}",
        f"- Answers generated: {metadata['answers_generated']}",
        f"- Hallucination judged: {metadata['hallucination_judged']}",
        "",
        f"> {metadata['note']}",
        "",
        "## Summary",
        "",
        "| System | Questions | Errors | Evidence recall | Retrieval hit | Answer accuracy | Hallucination rate | Retrieval p50 (ms) | Retrieval p95 (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for system in metadata["systems"]:
        summary = payload["summary"].get(system, {})
        lines.append(
            "| {system} | {questions} | {errors} | {recall} | {hit} | {accuracy} | {hallucination} | {p50} | {p95} |".format(
                system=system,
                questions=summary.get("questions", 0),
                errors=summary.get("errors", 0),
                recall=_fmt(summary.get("evidence_recall_mean")),
                hit=_fmt(summary.get("retrieval_hit_rate")),
                accuracy=_fmt(summary.get("answer_accuracy")),
                hallucination=_fmt(summary.get("hallucination_rate")),
                p50=_fmt(summary.get("retrieval_latency_ms_p50")),
                p95=_fmt(summary.get("retrieval_latency_ms_p95")),
            )
        )

    lines.extend(["", "## Evidence recall by question type", ""])
    question_types = sorted(
        {
            key
            for system in metadata["systems"]
            for key in payload["summary"].get(system, {}).get("by_question_type", {})
        }
    )
    lines.append("| Question type | " + " | ".join(metadata["systems"]) + " |")
    lines.append("| --- | " + " | ".join("---:" for _ in metadata["systems"]) + " |")
    for question_type in question_types:
        cells = []
        for system in metadata["systems"]:
            bucket = (
                payload["summary"]
                .get(system, {})
                .get("by_question_type", {})
                .get(question_type)
            )
            cells.append(_fmt(bucket.get("evidence_recall_mean")) if bucket else "n/a")
        lines.append(f"| {question_type} | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Metric definitions",
            "",
            "- **Evidence recall**: fraction of each question's gold evidence strings found in the retrieved context.",
            "- **Retrieval hit**: at least one gold evidence string was retrieved.",
            "- **Answer accuracy**: strict whole-token match against a gold answer or alias; not an LLM judgement.",
            "- **Hallucination rate**: share of answers an LLM judge marks as unsupported by the retrieved evidence. It is `n/a` unless `--judge` was used.",
            "- **Latency**: wall-clock time per retrieval call; answer latency is recorded separately in the JSON.",
            "",
            "This report contains measurements from the run above only. It is not a claim about unmeasured data.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--systems", default="graphrag,vector")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N questions")
    parser.add_argument("--answer", action="store_true", help="Generate answers and measure correctness")
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Ask an LLM judge whether answers are supported (implies --answer)",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="Overwrite the result files")
    args = parser.parse_args()

    if args.judge:
        args.answer = True
    if args.output.exists() and not args.force:
        print(
            f"Refusing to overwrite {args.output}. Pass --force or choose another --output.",
            file=sys.stderr,
        )
        return 1
    if args.limit is not None and args.limit < 1:
        print("--limit must be positive.", file=sys.stderr)
        return 1
    if args.top_k < 1:
        print("--top-k must be positive.", file=sys.stderr)
        return 1

    try:
        payload, _ = run(args)
    except Exception as exc:
        print(f"Benchmark did not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")

    print()
    print(f"Raw results: {args.output}")
    print(f"Markdown report: {markdown_path}")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
