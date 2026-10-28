# Aarthik Gyan V4

V4 adds a browser application on top of the frozen V3 GraphRAG backend. It does
not replace the ingestion pipeline, the LangGraph workflow, the MCP tool
boundaries, the risk rules, or the PDF report writer. The new code is an adapter
plus a separate React frontend.

- `api/` — FastAPI routes and read-only graph adapters
- `frontend/` — React + TypeScript + Vite review desk
- `benchmark/` — reproducible GraphRAG vs plain-vector-RAG harness

V3 files (`main.py`, `analyze.py`, `workflow/`, `agent/`, `retrieval/`,
`graph/`, `risk/`, `reports/`, `mcp_server/`, `ingestion/`, `config.py`, and the
existing tests) are unchanged.

## Why a thin adapter

`config.py` validates credentials at import time, and `graph/` / `vectorstore/`
clients connect at import time. Importing V3 eagerly would make the API
impossible to start or health-check when a database is down. The API therefore:

1. Keeps its own settings in `api/settings.py` and never imports `config`.
2. Imports V3 modules lazily inside request handlers and background jobs.
3. Reuses `main.ingest`, `workflow.workflow.build_workflow`, and LangGraph
   `Command(resume=...)` instead of duplicating orchestration.

## Requirements

- Python 3.12 with the V3 backend configured (`.env`, Neo4j, Qdrant, LLM keys)
- Node.js 20+ and npm
- The V3 MCP server running on `127.0.0.1:8000` for analysis runs

The API runs on **port 8001** because the V3 MCP server already binds
`127.0.0.1:8000`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-api-dev.txt

npm --prefix frontend install
```

If V3 dependencies are already installed in a shared environment, a venv
created with `--system-site-packages` also works. The launcher will fall back to
a complete interpreter automatically; `./start.sh --install` only installs the
frontend packages.

## Run

### One command

```bash
./start.sh
```

The launcher starts the V3 MCP server, the API, and the Vite dev server in one
terminal, prefixes each log stream, waits for readiness, opens
`http://localhost:5173`, and stops all three on **Ctrl+C**. Per-service logs are
also written to `.run/logs/`.

Useful options:

```bash
./start.sh --install    # install frontend dependencies first if missing
./start.sh --force      # stop existing listeners on ports 8000/8001/5173
./start.sh --no-open    # do not open the browser
./start.sh --help
```

The launcher picks the first Python interpreter that has the complete V3 + V4
dependency set: `$PYTHON` if set, then `.venv/bin/python`, then
`/opt/anaconda3/envs/ai/bin/python`, then `python3`/`python`. If your venv is
missing packages, either install them or point the launcher at a complete
environment:

```bash
PYTHON=/opt/anaconda3/envs/ai/bin/python ./start.sh
```

### Manual run

Terminal 1 — MCP server (required for analyses):

```bash
python -m mcp_server.server
```

Terminal 2 — API:

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Terminal 3 — frontend dev server:

```bash
npm --prefix frontend run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8001`.

### Fresh start from an empty graph

`./start.sh` does not seed or demo any data. After a fresh Neo4j/Qdrant reset,
open the **Upload** page, choose a PDF, and wait for the ingestion job to reach
`completed`. The document then appears on **Overview** and in the analysis
document picker. Until then the UI shows empty states rather than errors.

For a single-origin production-style run:

```bash
npm --prefix frontend run build
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

`api/main.py` serves `frontend/dist` when it exists, including an SPA fallback.
It never serves files outside that directory.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health/live` | Process liveness; no database calls |
| `GET` | `/api/health/ready` | Neo4j and Qdrant connectivity; `503` when degraded |
| `GET` | `/api/documents` | Document registry from Neo4j |
| `GET` | `/api/documents/{hash}` | One registry entry |
| `GET` | `/api/documents/{hash}/companies` | Companies mentioned by that document |
| `GET` | `/api/documents/{hash}/search` | Scoped Qdrant evidence search |
| `POST` | `/api/documents` | Validate and store a PDF, then start ingestion |
| `GET` | `/api/jobs` | In-process ingestion jobs |
| `GET` | `/api/jobs/{id}` | One ingestion job |
| `GET` | `/api/companies` | Company summaries |
| `GET` | `/api/companies/{id}` | One company |
| `GET` | `/api/companies/{id}/dashboard` | Company, assessments, documents, totals |
| `GET` | `/api/companies/{id}/assessments` | Assessment ledger |
| `GET` | `/api/companies/{id}/graph?depth=1` | Bounded neighbourhood for Cytoscape |
| `GET` | `/api/analyses` | Process-local analysis sessions |
| `POST` | `/api/analyses` | Start the V3 workflow in the background |
| `GET` | `/api/analyses/{id}` | Real workflow/session state |
| `POST` | `/api/analyses/{id}/review` | Resume the LangGraph interrupt |
| `GET` | `/api/analyses/{id}/report` | Download the V3 PDF, if generated |

Interactive docs are at `/api/docs`; the OpenAPI document is at
`/api/openapi.json`.

Errors use one shape:

```json
{"error": {"code": "validation_error", "message": "Request validation failed.", "details": []}}
```

Validation errors do not echo submitted values, so private filenames are not
reflected back.

## User journeys

1. **Overview** — real document/company/assessment counts, service readiness,
   latest assessment ledger, and links into each workspace.
2. **Upload** — PDF-only validation, magic-byte check, size limit, SHA-256
   content hash, then a background V3 `ingest` job.
3. **Ingestion progress** — polls `/api/jobs/{id}` and reports the real queue,
   running, completed, or failed state.
4. **Analysis setup** — choose a `completed`/`partial` document, then only the
   companies that document actually mentions. The first company is the same
   highest-degree default that `analyze.py` uses.
5. **Review workspace** — polls the real session, shows ratios, analyst
   findings, source evidence, and the HITL card. Approval is shown only after
   the backend returns an approval record or a new interrupt.
6. **Results and report** — final score, comparison with the system score,
   review trail, and the generated PDF download.

### Human-in-the-loop semantics

`POST /api/analyses` and `POST /api/analyses/{id}/review` launch the workflow as
an asyncio task and return immediately. The browser polls
`GET /api/analyses/{id}` until the session reaches `awaiting_review`,
`completed`, or `failed`.

The LangGraph `MemorySaver` checkpoint, analysis sessions, and ingestion jobs
are **process-local**. They are lost when the API process restarts. Run one API
worker; do not put this adapter behind multiple workers without adding a shared
session store and checkpointer.

For overrides, the UI sends `risk_level` only when the analyst explicitly
chooses a level. Leaving **Auto from ratios** selected lets
`workflow.review.apply_override` recalculate the level and notes from the
corrected ratios, exactly like V3.

## Tests and checks

Run these from the repository root:

```bash
.venv/bin/pytest -q api/tests benchmark/tests
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Actual results from this working tree:

- Backend/benchmark tests: **19 passed**
- Frontend typecheck: **passed**
- Frontend production build: **passed**
- Build warning: the main JS chunk is about **772 kB** because Cytoscape is
  statically imported. This is a warning, not a failure; route-level lazy
  loading is the next performance step.
- Runtime smoke test on port `8001`: `/api/health/live` `200`,
  `/api/health/ready` `200` (Neo4j and Qdrant connected), `/` SPA `200`,
  `/api/docs` `200`, `/api/openapi.json` `200`, unknown `/api/nope` `404`.
- Launcher end-to-end: `./start.sh` started MCP on `8000`, API on `8001`, and
  Vite on `5173`; all readiness checks returned `200`, logs were prefixed per
  service, and the shutdown trap released all three ports.
- Fresh-state check after the Neo4j/Qdrant reset: `/api/documents` and
  `/api/companies` both returned `[]` before any upload.

No ingestion or analysis was executed during verification. Those paths write to
Neo4j/Qdrant and call live LLMs, so they remain operator-run with real
credentials.

## Benchmark

See `benchmark/README.md`. The harness uses the real V3 router and vector store,
generates questions read-only from the operator's own graph, and writes results
only from actual runs. No benchmark numbers are claimed in this repository
until the operator runs it.

```bash
python -m benchmark.generate_questions --count 50
python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --answer
```

## Security notes

- No API keys or secrets are read by the frontend or stored in browser storage.
  The only browser-persisted value is the reviewer display name.
- Uploads are PDF-only, size-limited, SHA-256 named, and stored under
  `data/uploads` (git-ignored).
- Report downloads resolve inside `reports/output`; path traversal is rejected.
- The graph explorer is read-only. The only writes are the existing V3
  ingestion and workflow paths.
- There is no authentication in this version. Put it behind your normal access
  control before exposing it beyond localhost.

## Limitations

- Sessions, jobs, and checkpoints are in memory and single-process.
- One ingestion runs at a time via a process lock.
- Ingestion job progress is coarse; `main.ingest` does not emit per-batch
  progress events to the adapter.
- The API does not add a persistent queue, retries, or multi-tenant isolation.
- The benchmark requires live Neo4j/Qdrant/LLM credentials and is intentionally
  not executed or shipped with private data.

## Packaging

The deliverable ZIP excludes `.env`, `.venv`, caches, `node_modules`,
`frontend/dist`, private `documents/`, `reports/output/`, `data/`, `.run/`, and
benchmark questions/results. The command used for the deliverable builds the
archive from the project root with explicit exclusions:

```bash
zip -r aarthik-gyan-v4.zip . \
  -x '.env' '.env.*' '.venv/*' '*/__pycache__/*' '*.pyc' '.pytest_cache/*' \
     '.extraction_cache/*' 'documents/*' 'reports/output/*' 'data/*' '.run/*' \
     'frontend/node_modules/*' 'frontend/dist/*' \
     'benchmark/questions.jsonl' 'benchmark/results/*' '*.zip' '.git/*'
```

Always inspect `unzip -l aarthik-gyan-v4.zip` before sharing the archive.
