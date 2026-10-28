# AGENTS.md

## Project shape

- Treat the V3 GraphRAG backend as frozen: `main.py`, `analyze.py`, `workflow/`, `agent/`, `retrieval/`, `graph/`, `risk/`, `reports/`, `mcp_server/`, `ingestion/`, and `config.py`.
- V4 is a thin adapter plus a separate UI: `api/` (FastAPI), `frontend/` (React + Vite), and `benchmark/`.
- V4 work lives on branch `frontend-v4`; `main` currently points at V3.
- Reuse V3 entrypoints (`main.ingest`, `workflow.workflow.build_workflow`, LangGraph `Command(resume=...)`) instead of duplicating orchestration. Do not refactor V3 unless explicitly asked.

## Setup and run

- Use Python 3.12 and Node.js 20+. All Python dependencies (V3, V4, and pytest) are in `requirements.txt`; there are no `requirements-api*.txt` files.
- `cp .env.example .env` and fill the Neo4j, Qdrant, Google/Groq, and Hugging Face values. `config.py` validates them at import time.
- `./start.sh` starts MCP on `8000`, API on `8001`, and Vite on `5173`, writes prefixed logs to `.run/logs/`, and stops all three on Ctrl+C. Use `--no-open` in headless runs.
- `start.sh` auto-installs frontend dependencies when `frontend/node_modules/.bin/vite` is missing; `--install` is retained only as a compatibility no-op. `--force` kills whatever owns ports `8000`/`8001`/`5173`; ask before using it.
- Keep the API on `8001`: `mcp_server/server.py` hardcodes `8000`, and `frontend/vite.config.ts` proxies `/api` to `8001`.
- `npm --prefix frontend run build` creates `frontend/dist`; when it exists, the API serves the SPA. Otherwise use the Vite dev server.

## Verification

- `.venv/bin/python -m pytest -q api/tests benchmark/tests`
- Single test: `.venv/bin/python -m pytest -q api/tests/test_health.py::test_live_health_does_not_require_database`
- `npm --prefix frontend run typecheck`
- `npm --prefix frontend run build`
- `.venv/bin/python tests/test_mcp_scoping.py` — offline MCP integration test; it binds port `8123` and needs no API keys.
- There is no lint or CI configuration. The checks above are the verification path.
- Routine tests must not perform live ingestion, analysis, or benchmark runs: those write to Neo4j/Qdrant, call LLMs, and benchmark outputs contain private entity names.

## Benchmarking

- The harness in `benchmark/` talks to Neo4j, Qdrant, and the LLM provider through V3 modules (`retrieval.router.route_question`, `vectorstore.indexer.search_chunks`, `llm.provider`). It never calls the API or MCP, so `./start.sh` is not needed — only a filled `.env` and reachable services.
- Order of operations: `python -m benchmark.generate_questions --count 50`, then `python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --answer`. Add `--judge` for the LLM hallucination rate; it implies `--answer`.
- Smoke-test with `--limit 5` and a distinct `--output` (for example `benchmark/results/smoke.json`). Both scripts refuse to overwrite an existing file without `--force`.
- The graph path makes several LLM calls per question (routing, Cypher generation, answer), so free-tier keys rate-limit quickly. The smoke run is not optional.
- The generator refuses to pad a small graph: lower `--count` or ingest a richer document instead of weakening the ambiguity filters. Not every question type is reachable on a given graph, so by-type reports can contain gaps.
- Outputs are `benchmark/questions.jsonl` plus `benchmark/results/latest.json` and `latest.md`. They are gitignored and contain private entity names: never print or commit them. The harness is read-only toward Neo4j and writes no assessments.
- Answer accuracy is strict whole-token matching against the gold answer, so it reads low even for correct paraphrases. Treat evidence recall and retrieval hit rate as the primary metrics.

## Architecture constraints

- API settings live in `api/settings.py`. Do not import `config`, `graph.neo4j_client`, or `vectorstore.qdrant_client` at API module import time: `config` raises on missing environment variables, and the database clients connect or create indexes at import. Keep V3 imports lazy inside handlers and background jobs so health checks work when databases are down.
- Analysis sessions (`api/services/analysis_service.py`), ingestion jobs (`api/services/ingestion_service.py`), and LangGraph `MemorySaver` checkpoints are process-local. Run one API worker; restarting the API loses them.
- Uploads must start with `%PDF-`, default to a 25 MB limit, and are stored under `data/uploads/<sha256>/<sanitized-name>`. Report downloads are confined to `reports/output`.
- Graph depth templates use `.replace("{depth}", str(depth))`; `.format()` breaks on Cypher map braces.
- For overrides, omit `risk_level` for “Auto from ratios” and send it only when the analyst explicitly chooses a level. `workflow.review.apply_override` then recalculates the level from the corrected ratios.
- The Qdrant collection is `arthikgyaan_chunks` with 384-dimensional embeddings.
- Ingestion progress callbacks are optional and flow `main.ingest` → `ingestion.extractor` → `ingestion.batch_runner`. Keep `on_progress=None` working so the V3 CLI path is unchanged.
- Document deletion lives in `api/services/document_service.py`. It removes Qdrant points first, then Neo4j data, and deletes only entities no other Document mentions. It leaves `.extraction_cache` intact so a re-upload can reuse completed batches.
- Retry (`POST /api/documents/{hash}/retry`) only accepts `partial`/`failed` documents with a stored PDF under `data/uploads/<hash>/`. It calls `main.ingest`, which skips only `completed` documents and loads cached batches automatically.
- Deletion takes the ingestion lock; retry refuses while an ingestion is active. Active jobs for the same document are rejected with HTTP 409.
- Document Q&A lives in `api/services/qa_service.py` and calls the frozen `agent.qa_agent.answer_question`. Retrieval is global (graph plus vector), so the endpoint only checks that the document is `completed`/`partial`; do not add a document-scoped retriever without changing V3.
- The UI at `/documents/:documentHash/ask` (`frontend/src/pages/AskPage.tsx`) is the browser surface for that Q&A round; it is reached from the documents registry and the finished job card.
- Frontend copy is client-facing. Keep version and internal vocabulary out of `frontend/src`: no V3/V4 labels, `Neo4j`, `Qdrant`, `LangGraph`, `MCP`, `FastAPI`, "process-local", `SHA-256`, or `data/uploads`. Say "graph database", "evidence index", "review checkpoint", "service", and "reference #" instead. Those terms belong in `README.md` and this file, not in the product UI.

## Gotchas

- `python main.py` hardcodes `documents/Brightwater_Industrial_Systems_FY2025_Annual_Report.pdf`. `documents/` is gitignored and absent in a fresh clone, so `main.py` fails there. Use the UI upload or deliberately change/pass the path. `analyze.py` accepts an optional filename argument but defaults to Brightwater.
- The launcher tries `.venv`, then `/opt/anaconda3/envs/ai/bin/python`, then `python3`/`python`. Check the `Using Python:` line if packages appear to be missing.
- `README.md` is the single unified document. Do not recreate `V4_README.md` or the removed `requirements-api*.txt` files.
- Never print or commit `.env`, `data/uploads`, `.extraction_cache`, `reports/output`, `benchmark/questions.jsonl`, or `benchmark/results/`. They are gitignored and may contain private documents or entity names.
- There is no authentication or multi-tenant isolation; keep the application on localhost unless access control is added.
