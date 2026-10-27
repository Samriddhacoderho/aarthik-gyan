# Aarthik Gyan

Aarthik Gyan is a financial document intelligence system that combines a
Neo4j knowledge graph, Qdrant semantic search, and a human-reviewed
multi-agent risk-analysis workflow. It ingests financial PDFs, extracts
structured entities and relationships, answers questions with hybrid
GraphRAG retrieval, and produces an auditable PDF risk report.

> **Status:** Version 3.0 is complete. The current application is an
> end-to-end, terminal-operated V3 prototype; production hardening, a user
> interface, and benchmarking are planned for V4.

## What V3 delivers

The completed V3 pipeline is:

1. Ingest a financial PDF and extract text into overlapping chunks.
2. Batch chunks for structured LLM extraction with Pydantic schemas.
3. Run extraction concurrently with bounded workers, rate limiting, caching,
   retries, and provider fallback.
4. Resolve duplicate entities and merge entities, relationships, and document
   metadata into Neo4j.
5. Generate local embeddings and index document chunks in Qdrant.
6. Route questions to graph retrieval, vector retrieval, or hybrid retrieval.
7. Calculate rule-based financial risk scores from extracted metrics and graph
   context.
8. Run a LangGraph `StateGraph` with separate Auditor, Quant, HITL, and Writer
   nodes.
9. Expose graph analytics and retrieval operations through a FastMCP server,
   with per-node tool allow-lists.
10. Pause at a human-review checkpoint so an analyst can approve, override, or
    request a re-run of the risk assessment.
11. Persist the final decision and review history to Neo4j.
12. Generate a structured PDF risk report.

The implementation deliberately keeps the risk calculation transparent:
financial ratios are computed by deterministic rules, while the LLM is used
for document extraction, routing, findings, and report writing.

## Evolution

### V1.0 — One document, one graph, one answer

V1 established the GraphRAG foundation:

- A single PDF was parsed into a small set of structured entities and
  relationships: `Company`, `Executive`, `Subsidiary`, `Debt`, and
  `RiskFactor`.
- Pydantic structured outputs were written to a local Neo4j graph.
- One question-answering agent performed Cypher-based multi-hop retrieval.

V1 intentionally did not include vector search, cross-document comparison,
risk scoring, human review, or PDF reporting. Its purpose was to prove that a
graph could support more useful multi-hop answers than an unstructured
baseline.

### V2.0 — Multiple documents and hybrid retrieval

V2 addressed V1's single-document limitation:

- Multiple reports can be ingested and tracked by content hash.
- Document chunks are embedded and indexed in Qdrant alongside Neo4j.
- A retrieval router selects graph, vector, or combined retrieval.
- A rule-based Quant Risk Agent calculates initial financial risk scores.
- Batch extraction, entity resolution, retries, and provider fallback improve
  ingestion reliability.

V2 remained a one-shot Q&A system. It did not yet provide a persistent risk
report or a human review step.

### V3.0 — Multi-agent analysis with human oversight

V3 turns the system into an accountable analysis pipeline:

- **Auditor Agent:** reviews the selected company's profile, graph
  connections, and document-locked source passages.
- **Quant Agent:** retrieves historical assessments and document metrics,
  calculates ratios and risk levels, and uses graph centrality as context.
- **Human-in-the-loop checkpoint:** an analyst approves the score, overrides
  it with reviewed values, or requests a bounded re-run with an additional
  hint.
- **Executive Writer Agent:** converts the reviewed findings into a report,
  persists approval metadata and review events, and builds the PDF output.
- **FastMCP tools:** graph analytics, retrieval, and risk persistence are
  exposed behind a tool boundary rather than embedded directly in agents.

The review history, final score, override status, and approval metadata are
persisted so the result is traceable rather than just a transient chat answer.

## Architecture

### Ingestion and question answering

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

The detailed flow is documented in
[`architecture_diagram/main.mermaid.md`](architecture_diagram/main.mermaid.md)
and the editable diagram is
[`architecture_diagram/main.py.drawio`](architecture_diagram/main.py.drawio).

### Reviewed risk analysis

```text
resolve ingested document and company
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

The complete node-level flow, including MCP permissions and database access,
is documented in
[`architecture_diagram/analyze.mermaid.md`](architecture_diagram/analyze.mermaid.md)
and
[`architecture_diagram/analyze.py.drawio`](architecture_diagram/analyze.py.drawio).

## Graph and retrieval model

Neo4j uses the `Entity` label with stable lowercase snake-case identifiers.
The supported entity categories include `Company`, `Executive`, `Subsidiary`,
`RiskFactor`, and `Auditor`. Relationships include `OWNS`, `OWES_DEBT_TO`,
`SUPPLIES_TO`, `AUDITED_BY`, `EMPLOYS`, `FLAGGED_FOR`, and
`SUBSIDIARY_OF`.

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
passages such as concerning statements or disclosed risks. Hybrid retrieval
combines both kinds of evidence.

## MCP tool boundaries

The workflow uses per-node allow-lists in
[`workflow/mcp_client.py`](workflow/mcp_client.py). Calls to tools outside a
node's allow-list raise `PermissionError`.

| Node | Allowed tools | Responsibility |
| --- | --- | --- |
| Auditor | `get_company_profile`, `get_connected_entities`, `retrieve_footnote_context` | Build an evidence-based audit view. The LLM receives only the document-locked `search_this_document` wrapper. |
| Quant | `get_debt_ratios`, `calculate_graph_centrality`, `retrieve_footnote_context`, `save_risk_assessment` | Calculate and persist the system-generated risk assessment. |
| Writer | Workflow persistence and report-building operations | Persist the approved decision, review events, and PDF report. |

The document hash is required for source-context retrieval, preventing the
auditor or quant node from silently searching unrelated documents.

## Project structure

```text
.
├── agent/                 # Question answering and Cypher generation
├── documents/             # Sample financial PDFs
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
├── workflow/
│   ├── nodes/             # Auditor, Quant, HITL, and Writer nodes
│   ├── mcp_client.py      # Per-node MCP sessions and allow-lists
│   ├── scoped_tools.py    # Document-locked auditor search tool
│   ├── state.py           # LangGraph workflow state
│   └── workflow.py        # StateGraph definition
├── architecture_diagram/  # Mermaid and Draw.io architecture diagrams
├── analyze.py             # Human-reviewed risk-analysis entry point
├── config.py              # Environment-backed configuration
├── main.py                # Ingestion and question-answering entry point
├── requirements.txt
└── .env.example
```

## Prerequisites

- Python 3.10 or newer
- A reachable Neo4j database or Neo4j Aura instance
- Google Gemini and Groq API keys
- A local or hosted Qdrant instance
- A Hugging Face token for the configured embedding provider
- Node.js or an MCP-compatible client when using MCP tools

## Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create local configuration:

   ```bash
   cp .env.example .env
   ```

   Configure `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`,
   `GOOGLE_API_KEY`, `GROQ_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, and
   `HUGGINGFACEHUB_API_TOKEN` as applicable. Never commit `.env` or real
   credentials.

## Running the application

### Ingest and ask questions

```bash
python main.py
```

This verifies Neo4j and Qdrant connectivity, skips already-completed
documents using their SHA-256 hash, ingests the configured PDF, indexes its
chunks, calculates an initial draft assessment when possible, and answers a
question using routed retrieval.

### Run the reviewed risk workflow

The target document must already have been ingested by `main.py`.

```bash
python analyze.py
```

The terminal workflow asks for the reviewer, runs the Auditor and Quant nodes,
pauses for approval, override, or re-run, and writes the final report to
`reports/output/`.

### Start the MCP server

```bash
python -m mcp_server.server
```

The default FastMCP HTTP endpoint is `http://127.0.0.1:8000`. The server is
intended for local development and must be secured before network deployment.

### Run the offline MCP wiring test

```bash
python tests/test_mcp_scoping.py
```

This test uses fake databases and does not require API keys, Neo4j, or Qdrant.
It verifies tool scoping, document locking, and the quant workflow wiring.

## Configuration and operational notes

- The default Qdrant collection is `arthikgyaan_chunks`.
- The default embedding model is `all-MiniLM-L6-v2` with 384 dimensions.
- Extraction uses bounded concurrency and caches completed batches under
  `.extraction_cache`.
- Provider selection and fallback are centralized in
  [`llm/provider.py`](llm/provider.py).
- Risk scores are analytical estimates derived from document disclosures, not
  professional financial advice.

## Current limitations

- There is no web UI or graph exploration interface; operation is currently
  through terminal entry points.
- Ingestion is manual and one-off rather than an asynchronous background
  pipeline with progress polling.
- PDF extraction focuses on text and does not yet robustly extract tables,
  images, or complex layouts.
- Retrieval routing, extraction, and report writing depend on LLM output and
  can be incorrect.
- Risk scoring is rule-based and depends on metrics successfully extracted
  from source text.
- Qdrant must be reachable before application startup.
- Provenance is stronger for vector chunks than for every graph entity and
  relationship.
- The MCP server has no production authentication or deployment configuration.
- Automated coverage, observability, and production-scale evaluation remain
  incomplete.

## V4 roadmap

V4 is intended to make the system presentable and measurable:

1. Add a React frontend with Cytoscape.js or Vis.js graph visualization.
2. Add a review card for the HITL decision, modeled on the existing terminal
   review flow.
3. Move ingestion to an asynchronous background pipeline with status polling.
4. Benchmark GraphRAG against plain vector RAG on approximately 50 multi-hop
   questions.
5. Measure retrieval accuracy, answer quality, and hallucination rate.
6. Add broader automated tests, observability, authentication, and deployment
   guidance.

The benchmark is the research contribution: it evaluates whether graph-aware
retrieval improves multi-hop financial question answering rather than merely
demonstrating another RAG application.

## Maintainer

**Samriddha Raj Satyal**
