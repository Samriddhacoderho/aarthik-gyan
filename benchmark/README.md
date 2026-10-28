# GraphRAG vs plain-vector-RAG benchmark

This is a live, reproducible harness. It ships no questions, answers, entity
names, or results. Everything is generated and measured on the operator's own
graph, and every number in the report comes from the run that produced it.

## What is compared

| System | Retrieval path |
| --- | --- |
| `graphrag` | The real V3 `retrieval.router.route_question`, which may use Cypher/graph retrieval, vector search, or both |
| `vector` | The real V3 `vectorstore.indexer.search_chunks` with a configurable `--top-k` |

Both systems receive the same question and, when `--answer` is used, the same
V3 `ANSWER_PROMPT` and LLM factory. Retrieval and answering are timed
separately.

## Question generation

`generate_questions.py` reads Neo4j with two read-only queries:

```cypher
MATCH (e:Entity) RETURN e.id, e.name, e.type
MATCH (a:Entity)-[r:RELATION]->(b:Entity) RETURN ...
```

`benchmark/graph_questions.py` then derives deterministic two-hop questions
from the returned graph. No LLM authors the questions or the gold answers.

Question types:

- `common_neighbor` — an entity directly connected to two named entities
- `bridge_path` — the only two-hop path between two entities
- `two_hop_type` — the unique entity of a type exactly two hops away
- `relationship_chain` — follow one relationship type, then another
- `exact_two_hop_count` — count entities of one type at distance two
- `mutual_neighbor_type` — type of the entity linking two others
- `two_hop_relationship_type` — the two relationship types on a unique path

The generator refuses to pad: if the graph cannot produce the requested number
of unambiguous questions, it stops and reports the candidate counts. Lower
`--count` or ingest a richer document.

Questions, answers, and evidence stay on the operator's machine. They are
git-ignored (`benchmark/questions.jsonl`, `benchmark/results/`).

## Run

From the repository root, with the V3 `.env` and live Neo4j/Qdrant:

```bash
# 1. Generate ~50 questions (read-only)
python -m benchmark.generate_questions --count 50 --output benchmark/questions.jsonl

# 2. Retrieval-only comparison
python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl

# 3. Add answer accuracy
python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --answer

# 4. Add an LLM hallucination judge
python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --answer --judge

# Quick smoke run on the first five questions
python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --limit 5
```

Useful flags:

- `--systems graphrag,vector` — choose systems (default: both)
- `--top-k 8` — vector retrieval depth (default: 8)
- `--output benchmark/results/latest.json` — raw JSON destination
- `--force` — overwrite an existing output file

The runner refuses to overwrite results unless `--force` is passed.

## Outputs

- `benchmark/results/latest.json` — metadata, aggregate summary, and every
  per-question record
- `benchmark/results/latest.md` — the same summary as a Markdown table

The Markdown report includes evidence recall overall and by question type.

## Metrics

| Metric | Definition |
| --- | --- |
| Evidence recall | Fraction of a question's gold evidence strings found in retrieved context |
| Retrieval hit | At least one gold evidence string was retrieved |
| Answer accuracy | Strict whole-token match against the gold answer or a supplied alias |
| Hallucination rate | Share of answers an LLM judge marks as unsupported by retrieved evidence |
| Retrieval latency | Wall-clock milliseconds per retrieval call, with p50/p95 |
| Answer latency | Wall-clock milliseconds per answer generation (JSON only) |

Matching is deliberately conservative. `1` does not match inside `10`, and
there is no fuzzy credit. If a metric was not measured, the report shows
`n/a`; it is never filled with an assumed value.

## Tests

The pure parts are tested without a database or LLM:

```bash
pytest -q benchmark/tests
```

These tests cover normalization, evidence recall, strict answer matching,
retrieval flattening, deterministic question generation, refusal to pad a small
graph, and the guarantee that summaries do not invent unmeasured metrics.

## Limitations

- Answer accuracy is token matching, not semantic grading. Use `--judge` for a
  second, LLM-based view of support, and read the per-question records.
- The judge is itself an LLM and can be wrong; its reason is stored for audit.
- Cypher generation for the GraphRAG path is model-dependent, as it is in V3.
- Latency includes live network and model time and will vary between runs.
- The harness is read-only toward Neo4j; it does not write assessments.
