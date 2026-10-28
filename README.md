# Aarthik Gyan

Aarthik Gyan is a financial document intelligence system for extracting,
exploring, and reviewing financial risk from PDF reports. It combines a Neo4j
knowledge graph, Qdrant semantic search, deterministic financial ratios, and a
human-reviewed multi-agent workflow. V4 adds a browser application and FastAPI
adapter on top of the V3 GraphRAG backend.

> **Status:** V4 is a working local application. It provides a React review
> desk, document upload and ingestion, graph exploration, human-in-the-loop
> analysis, and PDF report downloads. It is not production-hardened and has no
> built-in authentication.

## What the application does

1. Ingests financial PDFs and splits their text into overlapping chunks.
2. Extracts structured entities, relationships, and financial metrics with
   Pydantic schemas and LLM providers.
3. Resolves duplicate entities and stores the resulting graph in Neo4j.
4. Embeds document chunks and indexes them in Qdrant.
5. Routes questions to graph retrieval, vector retrieval, or hybrid retrieval.
6. Calculates transparent, rule-based financial ratios and risk levels.
7. Runs a LangGraph workflow with Auditor, Quant, human-review, and Writer
   nodes.
8. Persists assessments, review history, and approval metadata to Neo4j.
9. Generates a structured PDF risk report.
10. Exposes the system through both terminal entry points and a browser UI.

Risk calculations remain deterministic and inspectable. LLMs are used for
document extraction, retrieval routing, findings, and report writing rather
than for silently replacing the financial rules.

## Architecture

### Ingestion and retrieval

```text
PDF
  |
  v
Text extraction -> chunking -> concurrent structured extraction
                                      |
                         entity resolution and document registry
                                      |
                  +-------------------+-------------------+
                  v                                       v
              Neo4j                                  Qdrant
       entities, relationships,                  embedded chunks,
       documents, risk assessments                document metadata

Question -> LLM router -> graph retrieval and/or vector retrieval
                         -> answer generation
```

### Reviewed risk analysis

```text
resolve document and company
             |
             v
Auditor -> Quant -> Human review
                       | approve
                       | override -> review again
                       | re-run  -> Quant (bounded iterations)
                       v
                    Writer
                       |
          +------------+------------+
          v                         v
      Neo4j audit trail        PDF risk report
```

The detailed diagrams are available in
[`architecture_diagram/main.mermaid.md`](architecture_diagram/main.mermaid.md)
and
[`architecture_diagram/analyze.mermaid.md`](architecture_diagram/analyze.mermaid.md).
Editable Draw.io versions are stored beside them.

### Why the V4 API is a thin adapter

The V3 backend validates configuration and initializes some database clients at
import time. The V4 API avoids importing those modules eagerly so that it can
start and expose health checks even when Neo4j or Qdrant is unavailable. It:

1. Keeps API settings in [`api/settings.py`](api/settings.py).
2. Imports V3 modules lazily inside request handlers and background jobs.
3. Reuses `main.ingest`, `workflow.workflow.build_workflow`, and LangGraph
   `Command(resume=...)` instead of duplicating orchestration.

V3 backend modules remain the source of truth for ingestion, retrieval, risk
rules, workflow behavior, MCP boundaries, and report generation.

## Graph and retrieval model

Neo4j uses the `Entity` label with stable lowercase snake-case identifiers.
Supported entity categories include `Company`, `Executive`, `Subsidiary`,
`RiskFactor`, and `Auditor`. Relationships include `OWNS`, `OWES_DEBT_TO`,
`SUPPLIES_TO`, `AUDITED_BY`, `EMPLOYS`, `FLAGGED_FOR`, and `SUBSIDIARY_OF`.

Company risk assessments can include:

- `risk_level`
- `debt_to_equity`
- `current_ratio`
- `net_margin`
- `risk_notes`
- final analyst decision and approval metadata

The retrieval router classifies questions as `GRAPH`, `VECTOR`, or `BOTH`.
Graph retrieval is suited to structural questions such as ownership and debt
relationships. Vector retrieval is suited to fuzzy language and source
passages such as disclosed risks. Hybrid retrieval combines both kinds of
evidence.

## MCP tool boundaries

Per-node tool allow-lists are defined in
[`workflow/mcp_client.py`](workflow/mcp_client.py). Calls to tools outside a
node's allow-list raise `PermissionError`.

| Node | Allowed tools | Responsibility |
| --- | --- | --- |
| Auditor | `get_company_profile`, `get_connected_entities`, `retrieve_footnote_context` | Build an evidence-based audit view |
| Quant | `get_debt_ratios`, `calculate_graph_centrality`, `retrieve_footnote_context`, `save_risk_assessment` | Calculate and persist the system-generated assessment |
| Writer | Workflow persistence and report-building operations | Persist the approved decision and build the PDF |

Source-context retrieval requires the document hash. This prevents the Auditor
and Quant nodes from silently searching unrelated documents.

## Project structure

```text
.
├── agent/                 # Question answering and Cypher generation
├── api/                   # FastAPI adapter, routes, schemas, and services
├── benchmark/             # GraphRAG versus plain-vector-RAG harness
├── documents/             # Sample financial PDFs
├── frontend/              # React, TypeScript, and Vite review desk
├── graph/                 # Neo4j client, queries, and graph writers
├── ingestion/             # PDF parsing, batching, extraction, and resolution
├── llm/                   # Provider fallback, rate limiting, text utilities
├── mcp_server/            # FastMCP server and graph/retrieval/risk tools
├── prompts/               # Extraction, routing, audit, and report prompts
├── reports/               # PDF report builder and generated output
├── retrieval/             # Graph, vector, and routed retrieval
├── risk/                  # Metric retrieval, ratios, and risk scoring
├── schemas/               # Pydantic entity, audit, risk, and report models
├── vectorstore/           # Embeddings, Qdrant client, and indexing
├── workflow/              # LangGraph state, nodes, review, and MCP sessions
├── architecture_diagram/  # Mermaid and Draw.io architecture diagrams
├── analyze.py             # Human-reviewed risk-analysis entry point
├── config.py              # V3 environment-backed configuration
├── main.py                # Ingestion and question-answering entry point
├── start.sh               # Local V4 launcher
└── requirements.txt       # All Python dependencies
```

## Requirements

- Python 3.12 with the V3 backend configured
- Node.js 20+ and npm
- A reachable Neo4j database or Neo4j Aura instance
- A local or hosted Qdrant instance
- Google Gemini and Groq API keys
- A Hugging Face token for the configured embedding provider
- The V3 MCP server on `127.0.0.1:8000` for browser-based analysis runs

Python 3.10+ is sufficient for the original V3 command-line workflow, but the
V4 API and development dependency set target Python 3.12.

## Quick start

From a new device, run:

1. Clone the repository and enter it:

   ```bash
   git clone https://github.com/Samriddhacoderho/aarthik-gyan.git
   cd aarthik-gyan
   ```

2. Create and activate a Python 3.12 virtual environment:

   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

3. Install all Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   This single file includes the V3 backend, V4 API, ingestion, and test
   dependencies.

4. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

5. Add the required credentials to `.env`. Configure
   `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `GOOGLE_API_KEY`,
   `GROQ_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, and
   `HUGGINGFACEHUB_API_TOKEN` as applicable. Never commit `.env` or real
   credentials.

6. Start the application:

   ```bash
   ./start.sh
   ```

   `start.sh` automatically runs `npm --prefix frontend install` when the
   frontend dependencies are missing, so a separate npm installation step is
   not required.

If `python3.12` is not available on your system, install Python 3.12 first or
use another supported Python interpreter, for example:

```bash
python3 -m venv .venv
```

The launcher requires Node.js 20+ and npm to perform the automatic frontend
installation.

## Installation details

The V4 requirements include the backend dependencies. If using a shared
environment, a venv created with `--system-site-packages` also works.

## Running the V4 browser application

### One command

```bash
./start.sh
```

The launcher starts the V3 MCP server, API, and Vite development server,
prefixes their logs, waits for readiness, opens `http://localhost:5173`, and
stops all three on **Ctrl+C**. Logs are written to `.run/logs/`.

```bash
./start.sh --install    # retained for compatibility; missing dependencies auto-install
./start.sh --force      # stop existing listeners on ports 8000, 8001, 5173
./start.sh --no-open    # do not open the browser
./start.sh --help
```

The API uses port `8001` because the MCP server uses port `8000`. To select a
complete Python environment explicitly:

```bash
PYTHON=/path/to/python ./start.sh
```

### Manual run

Terminal 1 — MCP server:

```bash
python -m mcp_server.server
```

Terminal 2 — API:

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Terminal 3 — frontend:

```bash
npm --prefix frontend run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to
`http://127.0.0.1:8001`.

For a single-origin production-style local run:

```bash
npm --prefix frontend run build
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

When `frontend/dist` exists, [`api/main.py`](api/main.py) serves it with an SPA
fallback and never serves files outside that directory.

### Fresh start from an empty graph

The launcher does not seed demo data. After resetting Neo4j and Qdrant, open
**Upload**, choose a PDF, and wait for ingestion to reach `completed`. The
document then appears in **Overview** and the analysis document picker.

## V4 API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health/live` | Process liveness without database calls |
| `GET` | `/api/health/ready` | Neo4j and Qdrant connectivity |
| `GET` | `/api/documents` | Document registry |
| `GET` | `/api/documents/{hash}` | One document registry entry |
| `GET` | `/api/documents/{hash}/companies` | Companies mentioned by a document |
| `GET` | `/api/documents/{hash}/search` | Scoped Qdrant evidence search |
| `POST` | `/api/documents` | Validate, store, and ingest a PDF |
| `GET` | `/api/jobs` | In-process ingestion jobs |
| `GET` | `/api/jobs/{id}` | One ingestion job |
| `GET` | `/api/companies` | Company summaries |
| `GET` | `/api/companies/{id}` | One company |
| `GET` | `/api/companies/{id}/dashboard` | Company dashboard data |
| `GET` | `/api/companies/{id}/assessments` | Assessment ledger |
| `GET` | `/api/companies/{id}/graph?depth=1` | Bounded graph neighborhood |
| `GET` | `/api/analyses` | Process-local analysis sessions |
| `POST` | `/api/analyses` | Start a background V3 workflow |
| `GET` | `/api/analyses/{id}` | Workflow/session state |
| `POST` | `/api/analyses/{id}/review` | Resume the HITL review |
| `GET` | `/api/analyses/{id}/report` | Download the generated PDF |

Interactive API documentation is available at
`http://localhost:8001/api/docs`; the OpenAPI document is at
`http://localhost:8001/api/openapi.json`.

API errors use one shape:

```json
{"error": {"code": "validation_error", "message": "Request validation failed.", "details": []}}
```

## Browser user journeys

1. **Overview** shows document, company, and assessment counts, service
   readiness, and the latest assessment ledger.
2. **Upload** validates PDF content, magic bytes, size, and SHA-256 hash before
   starting a background ingestion job.
3. **Ingestion progress** polls the real job state and reports queued, running,
   completed, or failed status.
4. **Analysis setup** lets the user choose a completed or partial document and
   one of the companies actually mentioned in it.
5. **Review workspace** shows ratios, analyst findings, source evidence, and
   the HITL decision card.
6. **Results and report** shows the final score, system-score comparison,
   review trail, and PDF download.

The browser polls analysis sessions until they reach `awaiting_review`,
`completed`, or `failed`. The LangGraph `MemorySaver`, analysis sessions, and
ingestion jobs are process-local and are lost when the API restarts. Run one
API worker; multiple workers require a shared session store and checkpointer.

For overrides, the UI sends `risk_level` only when the analyst explicitly
chooses a level. **Auto from ratios** recalculates the level and notes from
corrected ratios using the existing V3 review logic.

## V3 command-line workflows

### Ingest and ask questions

```bash
python main.py
```

This checks Neo4j and Qdrant, skips documents already ingested by SHA-256 hash,
ingests the configured PDF, indexes its chunks, calculates an initial
assessment when possible, and answers a question using routed retrieval.

### Run the reviewed risk workflow

The target document must already have been ingested by `main.py`.

```bash
python analyze.py
```

The terminal workflow asks for the reviewer, runs the Auditor and Quant nodes,
pauses for approval, override, or re-run, and writes the final report to
`reports/output/`.

### Run the MCP server directly

```bash
python -m mcp_server.server
```

The default FastMCP endpoint is `http://127.0.0.1:8000`. It is intended for
local development and must be secured before network deployment.

### Offline MCP wiring test

```bash
python tests/test_mcp_scoping.py
```

This uses fake databases and does not require API keys, Neo4j, or Qdrant. It
verifies tool scoping, document locking, and Quant workflow wiring.

## Tests and checks

```bash
.venv/bin/pytest -q api/tests benchmark/tests
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

The browser and API tests are designed to run without executing live ingestion
or analysis. Those paths write to Neo4j/Qdrant and call live LLMs, so run them
manually with real credentials when needed.

## Benchmark

See [`benchmark/README.md`](benchmark/README.md). The harness uses the real V3
router and vector store, generates questions read-only from the operator's
graph, and writes results only from actual runs. No benchmark numbers are
claimed until the operator runs it.

```bash
python -m benchmark.generate_questions --count 50
python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl --answer
```

## Configuration and operational notes

- The default Qdrant collection is `arthikgyaan_chunks`.
- The default embedding model is `all-MiniLM-L6-v2` with 384 dimensions.
- Extraction uses bounded concurrency and caches completed batches under
  `.extraction_cache`.
- Provider selection and fallback are centralized in
  [`llm/provider.py`](llm/provider.py).
- One ingestion runs at a time through a process lock.
- Risk scores are analytical estimates from document disclosures, not
  professional financial advice.

## Security and limitations

- No API keys or secrets are sent to the frontend or stored in browser storage.
  Only the reviewer display name is persisted by the browser.
- Uploads are PDF-only, size-limited, SHA-256 named, and stored under
  `data/uploads` (git-ignored).
- Report downloads are restricted to `reports/output`; path traversal is
  rejected.
- The graph explorer is read-only. Writes use the existing V3 ingestion and
  workflow paths.
- There is no authentication or multi-tenant isolation. Put the application
  behind appropriate access control before exposing it beyond localhost.
- Sessions, jobs, and checkpoints are in memory and single-process.
- Ingestion progress is coarse because the adapter does not expose per-batch
  progress events.
- PDF extraction does not yet robustly handle tables, images, or complex
  layouts.
- Retrieval, extraction, and report writing depend on LLM output and can be
  incorrect.
- Qdrant must be reachable before the relevant application paths can operate.
- Provenance is stronger for vector chunks than for every graph entity and
  relationship.
- Automated coverage, observability, and production-scale evaluation remain
  incomplete.

## Maintainer

**Samriddha Raj Satyal**
