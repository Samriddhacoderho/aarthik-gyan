# Aarthik Gyan

Aarthik Gyan is a financial document intelligence system for turning annual
reports and other financial PDFs into searchable evidence, a connected
knowledge graph, explainable risk scores, and analyst-reviewed PDF reports.

The project combines:

- PDF parsing and chunking
- LLM-assisted entity, relationship, and financial-metric extraction
- Neo4j for entities, relationships, documents, and assessment history
- Qdrant for semantic search over source passages
- graph, vector, and hybrid question answering
- deterministic financial-ratio scoring
- a human-in-the-loop analysis workflow
- a FastAPI service and React browser application
- an MCP server for scoped graph, retrieval, and risk tools

The application is intended for local development and review. It does not
include authentication or multi-tenant isolation, so keep it on a trusted
machine or add access control before exposing it to a network.

## How it works

### Document ingestion

1. A PDF is validated and stored under a hash-based upload directory.
2. Text is extracted and split into overlapping chunks.
3. Chunks are processed in batches for structured entity and relationship
   extraction.
4. Failed batches are retried once. A document with permanently failed batches
   is recorded as `partial`; completed batches are cached for later retries.
5. Entities are resolved and written to Neo4j.
6. Chunks are embedded and indexed in Qdrant.
7. The primary company is identified and an initial risk assessment is created
   when enough financial information is available.

### Retrieval and questions

Questions are routed to one or both retrieval paths:

- **Graph retrieval** answers structural questions about companies, ownership,
  debt, subsidiaries, executives, auditors, and other relationships.
- **Vector retrieval** finds relevant source passages and disclosures.
- **Hybrid retrieval** combines graph facts with document evidence.

The document assistant uses the existing retrieval and answer-generation
pipeline. Evidence search can also be called directly from the API.

### Risk analysis and review

The analysis workflow:

```text
document + company
        |
        v
Auditor findings
        |
        v
Deterministic ratio calculation
        |
        v
Human review: approve, override, or request a bounded re-run
        |
        v
Persisted assessment and PDF report
```

The score is calculated from debt-to-equity, current ratio, and net margin.
LLMs help extract metrics and write findings, but the ratio arithmetic and risk
thresholds are explicit in [`risk/ratios.py`](risk/ratios.py). Analyst overrides
use the same scoring rules as automatic scores.

## Architecture

```text
                         +----------------------+
                         | React + Vite browser |
                         +----------+-----------+
                                    |
                              HTTP / JSON
                                    |
                         +----------v-----------+
                         | FastAPI application  |
                         +----+-------------+---+
                              |             |
                        background jobs      | MCP client
                              |             |
             +----------------v--+      +---v----------------+
             | ingestion service |      | scoped MCP tools   |
             +---------+----------+      +--------------------+
                       |
              +--------+---------+
              |                  |
       +------v------+    +------v------+
       | Neo4j graph |    | Qdrant      |
       | facts/audit |    | embeddings  |
       +-------------+    +-------------+
```

The terminal entrypoints use the same ingestion, retrieval, scoring, workflow,
and report-building modules as the browser application. The API keeps imports
of database and LLM clients lazy so that liveness and API documentation can
start even when external services are unavailable.

Detailed diagrams are in:

- [`architecture_diagram/main.mermaid.md`](architecture_diagram/main.mermaid.md)
- [`architecture_diagram/analyze.mermaid.md`](architecture_diagram/analyze.mermaid.md)
- [`architecture_diagram/main.py.drawio`](architecture_diagram/main.py.drawio)
- [`architecture_diagram/analyze.py.drawio`](architecture_diagram/analyze.py.drawio)

## Requirements

- Python 3.12 recommended
- Node.js 20 or newer and npm
- Neo4j database or Neo4j Aura
- Qdrant instance
- Groq API key
- Google Gemini API key
- Hugging Face token for the embedding provider

Python packages for the backend, API, ingestion, embeddings, MCP server, PDF
reports, and tests are listed in [`requirements.txt`](requirements.txt).

## Configuration

Create a local environment file:

```bash
cp .env.example .env
```

Set these values in `.env`:

| Variable | Purpose |
| --- | --- |
| `NEO4J_URI` | Neo4j connection URI |
| `NEO4J_USERNAME` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |
| `GROQ_API_KEY` | Primary LLM provider |
| `GOOGLE_API_KEY` | Fallback LLM provider |
| `QDRANT_URL` | Qdrant URL; defaults to `http://localhost:6333` in code |
| `QDRANT_API_KEY` | Qdrant API key |
| `HUGGINGFACEHUB_API_TOKEN` | Token used by the embedding stack when required |

Do not commit `.env`, credentials, uploaded PDFs, extraction caches, or
generated reports.

The API also accepts these optional settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed browser origins |
| `API_UPLOAD_DIR` | `data/uploads` | PDF upload directory |
| `API_REPORT_DIR` | `reports/output` | Generated report directory |
| `API_MAX_UPLOAD_MB` | `25` | Maximum PDF size |
| `API_GRAPH_MAX_NODES` | `220` | Graph response node limit |
| `API_GRAPH_MAX_EDGES` | `400` | Graph response edge limit |

## Quick start

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# edit .env with Neo4j, Qdrant, and LLM credentials
./start.sh
```

The launcher:

1. checks `.env`, Python dependencies, Node.js, npm, and required ports
2. installs frontend packages if `frontend/node_modules` is missing
3. starts the MCP server on `127.0.0.1:8000`
4. starts the API on `127.0.0.1:8001`
5. starts the Vite frontend on `127.0.0.1:5173`
6. waits for service readiness and opens the browser

Use `./start.sh --no-open` in headless environments. Logs are written to
`.run/logs/`. Use `./start.sh --force` only when you have confirmed that
existing listeners on ports `8000`, `8001`, or `5173` can be stopped.

The launcher also supports:

```bash
PYTHON=/path/to/python ./start.sh
./start.sh --help
```

### Run services manually

If the single-command launcher is not suitable:

```bash
# Terminal 1
python -m mcp_server.server

# Terminal 2
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001

# Terminal 3
npm --prefix frontend run dev
```

Open <http://localhost:5173>. The Vite configuration proxies `/api` requests
to the API on port `8001`.

For a single-origin local build:

```bash
npm --prefix frontend run build
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

When `frontend/dist/index.html` exists, the API serves the built frontend.

## Using the browser application

The browser application provides these areas:

- **Overview**: document, company, graph, assessment, and service status
- **Documents**: upload PDFs, monitor batch progress, retry partial or failed
  ingestion, delete documents, and open document questions
- **Analysis setup**: select an ingested document, company, reviewer, and
  iteration limit
- **Review workspace**: inspect auditor findings, ratios, evidence, and review
  history; approve, override, or request a re-run
- **Results**: compare system and analyst decisions and download the generated
  PDF report
- **Companies**: inspect dashboards, assessment history, and company graph
  context
- **Graph**: explore a bounded company neighborhood
- **Document assistant**: ask questions about a document using indexed evidence

Start with **Documents**, upload a financial PDF, and wait for ingestion to
reach `completed` or `partial`. Then choose a company and document from
**Analysis**. A partial document can be analyzed, but missing extraction
batches may reduce the available evidence.

The API documentation is available at
<http://localhost:8001/api/docs>, with the OpenAPI document at
<http://localhost:8001/api/openapi.json>.

## API reference

All application routes are under `/api`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health/live` | Process liveness without database calls |
| `GET` | `/health/ready` | Neo4j and Qdrant readiness checks |
| `GET` | `/documents` | List registered documents |
| `POST` | `/documents` | Validate, store, and queue a PDF for ingestion |
| `GET` | `/documents/{hash}` | Get one document |
| `DELETE` | `/documents/{hash}` | Remove document data and its upload |
| `POST` | `/documents/{hash}/retry` | Retry a partial or failed document |
| `GET` | `/documents/{hash}/companies` | List companies mentioned in a document |
| `GET` | `/documents/{hash}/search` | Search document evidence in Qdrant |
| `POST` | `/documents/{hash}/ask` | Ask a question about a document |
| `GET` | `/jobs` | List in-process ingestion jobs |
| `GET` | `/jobs/{id}` | Get ingestion progress and batch status |
| `GET` | `/companies` | List companies |
| `GET` | `/companies/{id}` | Get a company summary |
| `GET` | `/companies/{id}/dashboard` | Get company dashboard data |
| `GET` | `/companies/{id}/assessments` | Get assessment history |
| `GET` | `/companies/{id}/graph?depth=1` | Get a bounded company graph |
| `GET` | `/analyses` | List in-process analysis sessions |
| `POST` | `/analyses` | Start a reviewed risk analysis |
| `GET` | `/analyses/{id}` | Get analysis state |
| `POST` | `/analyses/{id}/review` | Submit an analyst decision |
| `GET` | `/analyses/{id}/report` | Download the generated PDF |

Uploads must begin with the PDF magic bytes `%PDF-` and are limited to 25 MB
by default. Uploads are stored at
`data/uploads/<sha256>/<sanitized-filename>`. API errors use a consistent
shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": []
  }
}
```

## Command-line workflows

### Ingest a PDF and ask a question

[`main.py`](main.py) contains the ingestion and question-answering entrypoint.
The callable workflow can also be used from a Python shell:

```python
from main import ask, ingest

ingest("path/to/report.pdf")
ask("What are the main financial risks disclosed in this report?")
```

The script's default example path is
`documents/Brightwater_Industrial_Systems_FY2025_Annual_Report.pdf`. Supply a
real PDF or use the browser upload flow if that file is not present.

### Run the reviewed risk workflow

```bash
python analyze.py path/to/report.pdf
```

The workflow identifies the primary company for the selected ingested
document, gathers auditor findings, computes the transparent ratio score,
pauses for analyst input, persists the decision, and builds a PDF report.

### Run the MCP server

```bash
python -m mcp_server.server
```

The server listens on `127.0.0.1:8000` and exposes graph, retrieval, and risk
tools. Workflow nodes receive explicit tool allow-lists; a node attempting to
call a tool outside its boundary is rejected.

## Data and persistence

- **Neo4j** stores `Document` and `Entity` nodes, `RELATION` edges, document
  mentions, risk assessments, and review history.
- **Qdrant** stores document chunks using the `arthikgyaan_chunks` collection
  and 384-dimensional embeddings.
- **`.extraction_cache/`** stores completed extraction batches so retries do
  not repeat successful LLM calls.
- **`data/uploads/`** stores uploaded PDFs by SHA-256 hash.
- **`reports/output/`** stores generated PDF reports.
- Analysis sessions and LangGraph checkpoints are process-local. Restarting
  the API loses active in-memory sessions, although persisted graph records
  remain.

Document deletion removes the document's Qdrant points and Neo4j data,
including unshared entities and document-owned relationships. It preserves
entities still referenced by other documents and leaves extraction caches
available for a future re-upload.

## Project layout

```text
.
├── agent/                 # Question answering and Cypher generation
├── api/                   # FastAPI app, routes, schemas, and services
├── architecture_diagram/ # Mermaid and Draw.io diagrams
├── benchmark/             # Graph retrieval versus vector retrieval harness
├── frontend/              # React, TypeScript, and Vite application
├── graph/                 # Neo4j client, queries, and graph writer
├── ingestion/             # PDF parsing, batching, extraction, and resolution
├── llm/                  # Provider fallback, rate limiting, and text helpers
├── mcp_server/            # FastMCP server and registered tools
├── prompts/               # Extraction, routing, audit, and report prompts
├── reports/               # PDF report generation
├── retrieval/             # Graph, vector, and routed retrieval
├── risk/                  # Metric retrieval, ratios, and risk scoring
├── schemas/               # Pydantic data models
├── vectorstore/           # Embedding and Qdrant indexing
├── workflow/              # LangGraph analysis and human review
├── analyze.py             # Reviewed analysis entrypoint
├── config.py              # External-service configuration
├── main.py                # Ingestion and question-answering entrypoint
├── requirements.txt       # Python dependencies
└── start.sh               # Local service launcher
```

## Testing and checks

Run the focused backend and benchmark suites:

```bash
.venv/bin/python -m pytest -q api/tests benchmark/tests
```

Run the offline MCP scoping integration test:

```bash
.venv/bin/python tests/test_mcp_scoping.py
```

Check the frontend:

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

The routine tests do not perform live ingestion, analysis, or benchmark runs.
Those operations write to Neo4j/Qdrant and call external LLM services.

## Benchmarking retrieval

The benchmark harness compares the real graph/hybrid retrieval path with the
plain vector path using questions generated from the operator's own graph. It
does not ship questions, answers, entity names, or results.

See [`benchmark/README.md`](benchmark/README.md) for the full workflow:

```bash
python -m benchmark.generate_questions --count 50 --output benchmark/questions.jsonl
python -m benchmark.run_benchmark --dataset benchmark/questions.jsonl
```

Generated questions and results remain local and are git-ignored.

## Operational limitations

- External Neo4j, Qdrant, and LLM services must be reachable for ingestion,
  retrieval, and analysis.
- Analysis sessions and active ingestion jobs are held in process memory.
- There is no authentication, authorization, or tenant isolation.
- The graph explorer is bounded and read-only; writes occur through ingestion
  and analysis workflows.
- Risk scores are explainable rule-based indicators, not investment advice or
  a substitute for professional financial review.
- LLM extraction can fail or return incomplete metrics; inspect document status,
  evidence, and review history before relying on a report.

## License

This project is MIT licensed.

Copyright (c) 2026 Samriddha Raj Satyal.

