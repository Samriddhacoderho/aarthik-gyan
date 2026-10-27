# Aarthik Gyan

Aarthik Gyan is a Python-based financial intelligence and knowledge graph
application. It ingests financial PDF documents, extracts and resolves entities,
stores structured knowledge in Neo4j, indexes document chunks in Qdrant, and
answers questions through routed graph and semantic retrieval. Version 3 adds
parallel extraction, provider fallback, an auditable LangGraph workflow with
human review, PDF reporting, and an MCP server.

> **Status:** Version 3.0 implementation complete; production hardening and
> broader testing remain ongoing.

## What Is Achieved

The current implementation provides the following end-to-end workflow:

1. Load text from financial PDF documents.
2. Split documents into overlapping chunks.
3. Group chunks into batches for LLM extraction.
4. Extract validated financial entities and relationships with Pydantic output schemas.
5. Deduplicate extracted entities across batches using stable IDs.
6. Track documents by SHA-256 hash to skip duplicate ingestion.
7. Register document metadata and ingestion status in Neo4j.
8. Merge entities and relationships into the Neo4j knowledge graph.
9. Generate embeddings for chunks and index them in Qdrant.
10. Route questions to graph retrieval, vector retrieval, or both.
11. Generate a final natural-language answer from the retrieved results.
12. Extract financial metrics, calculate risk ratios, and write company risk scores back to Neo4j.
13. Retry LLM operations with exponential backoff for transient failures.
14. Run extraction batches concurrently with bounded workers, rate limiting,
	caching, and retry handling.
15. Resolve duplicate or equivalent entities before graph persistence.
16. Use configurable Gemini/Groq providers with fallback handling.
17. Run an Auditor -> Quant -> Human-in-the-Loop -> Writer workflow with
	checkpointing and iterative review.
18. Generate approved financial risk reports as PDF files.
19. Expose graph, retrieval, and risk operations through a FastMCP HTTP server.

The sample documents currently included in the repository are:

- `documents/Sample-Financial-Statements-1.pdf`
- `documents/NASDAQ_TSLA_2025.pdf`

## Architecture

```text
PDF document
	|
	v
Text extraction and chunking
	|
	v
Batched entity and relationship extraction
	|
	+-----------------------> Neo4j graph
	|                           - entities and relationships
	|                           - document metadata
	|                           - company risk scores
	v
Embedding generation -------> Qdrant vector index
								- chunk text and metadata

User question
	|
	v
LLM retrieval router
	|
	+--> Graph retrieval
	+--> Vector retrieval
	+--> Both
	|
	v
Answer generation

Risk analysis workflow:

Auditor -> Quant -> Human review -> Writer -> PDF report and Neo4j update
```

## Retrieval Modes

The retrieval router classifies each question as `GRAPH`, `VECTOR`, or `BOTH`.
Graph retrieval handles structured entity and relationship questions, vector
retrieval finds relevant source passages, and `BOTH` combines the two. An
unexpected router response defaults to `BOTH`.

## Supported Graph Schema

All graph nodes use the `Entity` label and contain:

- `id`: stable lowercase snake-case identifier
- `name`: human-readable entity name
- `type`: entity category
- `description`: optional context from the source document

Supported entity types are `Company`, `Executive`, `Subsidiary`, `RiskFactor`,
and `Auditor`.

Supported relationship types are `OWNS`, `OWES_DEBT_TO`, `SUPPLIES_TO`,
`AUDITED_BY`, `EMPLOYS`, `FLAGGED_FOR`, and `SUBSIDIARY_OF`. Relationships can
also contain an optional `detail` field for supporting facts such as amounts or
dates.

Company nodes can additionally receive `risk_level`, `debt_to_equity`,
`current_ratio`, `net_margin`, `risk_notes`, and `risk_scored_at` fields from
the risk-analysis workflow.

## Project Structure

```text
.
├── agent/
│   ├── __init__.py
│   └── qa_agent.py             # Question answering and Cypher generation
├── documents/                  # Sample PDF inputs
├── graph/
│   ├── __init__.py
│   ├── neo4j_client.py         # Neo4j driver wrapper
│   └── writer.py               # Entity and relationship MERGE operations
├── ingestion/
│   ├── __init__.py
│   ├── batching.py             # Chunk batching helpers
│   ├── batch_runner.py          # Parallel batch execution and retries
│   ├── document_registry.py    # Hash and ingestion-status tracking
│   ├── entity_resolution.py    # Entity deduplication and resolution
│   ├── extractor_shared.py     # Shared extraction logic
│   ├── extractor.py            # Batched LLM extraction
│   └── pdf_parser.py           # PDF loading and chunking
├── llm/
│   ├── provider.py              # Provider selection and fallback
│   ├── rate_limiter.py          # Bounded extraction concurrency
│   └── text_utils.py            # LLM response cleanup
├── prompts/                    # Extraction, Cypher, and answer prompts
├── retrieval/
│   ├── graph_retrieval.py      # Neo4j retrieval
│   ├── router.py               # GRAPH/VECTOR/BOTH routing
│   └── vector_retriever.py     # Semantic retrieval
├── risk/
│   ├── metrics_retriever.py     # Context retrieval for metrics
│   ├── ratios.py               # Metric extraction and ratio calculation
│   └── risk_agent.py           # Risk scoring and graph persistence
├── reports/
│   └── pdf_builder.py           # Approved risk-report PDF generation
├── schemas/
│   ├── __init__.py
│   ├── entities.py             # Entity and relationship models
│   └── risk.py                 # Financial metric and risk models
├── vectorstore/
│   ├── embedder.py             # Hugging Face embeddings
│   ├── indexer.py              # Qdrant indexing and search
│   └── qdrant_client.py        # Qdrant connection and collection setup
├── workflow/
│   ├── nodes/                   # Auditor, quant, HITL, and writer nodes
│   ├── mcp_client.py            # Per-node MCP allow-lists and toolbox
│   ├── scoped_tools.py          # The one document-locked tool the auditor LLM sees
│   ├── state.py                 # Workflow state schema
│   └── workflow.py              # LangGraph workflow definition
├── mcp_server/
│   ├── server.py                # FastMCP HTTP server
│   └── tools/                   # Graph, retrieval, and risk tools
├── tests/
│   └── test_mcp_scoping.py      # Offline test of the MCP wiring
├── analyze.py                   # Interactive risk-analysis workflow
├── config.py                   # Environment-backed configuration
├── main.py                     # Ingestion and question-answering entry point
├── requirements.txt
└── .env.example
```

## Prerequisites

- Python 3.10 or newer
- A Neo4j Aura instance or reachable Neo4j database
- A Google Gemini API key
- A Groq API key
- A Qdrant instance, local or hosted
- A Hugging Face token for the configured embedding provider
- Node.js or an MCP-compatible client if using the MCP tools
- Access to the sample PDF files, or your own financial PDFs

## Setup

1. Create and activate a virtual environment:

	 ```bash
	 python -m venv .venv
	 source .venv/bin/activate
	 ```

2. Install the pinned dependencies:

	 ```bash
	 pip install -r requirements.txt
	 ```

3. Copy the environment template and fill in your credentials:

	 ```bash
	 cp .env.example .env
	 ```

	 Required values are `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`,
	 `GOOGLE_API_KEY`, `GROQ_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, and
	 `HUGGINGFACEHUB_API_TOKEN`. Do not commit `.env` or real credentials.

4. Run the current demo entry point:

	 ```bash
	 python main.py
	 ```

The entry point verifies Neo4j and Qdrant connectivity, skips a document if its
hash was already registered, ingests the configured PDF, runs parallel
extraction and entity resolution, indexes its chunks, calculates risk scores,
and asks a question using routed retrieval.

To run the human-reviewed risk workflow:

```bash
python analyze.py
```

To start the MCP server:

```bash
python -m mcp_server.server
```

It listens on `http://127.0.0.1:8000` using FastMCP HTTP transport. Restart it after
any change to the files in `mcp_server/` (the workflow checks that the tools it needs exist).

### Which node may use which MCP tool

Each workflow node has its own allow-list in `workflow/mcp_client.py`
(`NODE_TOOL_ALLOWLIST`); a call to any other tool raises `PermissionError`.

| Node | Allowed tools | Notes |
| --- | --- | --- |
| auditor | `get_company_profile`, `get_connected_entities`, `retrieve_footnote_context` | The first two are called by code. The LLM gets only one wrapper tool, `search_this_document(query)`, locked to the current document. No risk scores are visible. |
| quant | `get_debt_ratios`, `calculate_graph_centrality`, `retrieve_footnote_context`, `save_risk_assessment` | All called by code, none by the LLM. |

`retrieve_footnote_context` requires a `document_hash` (it can no longer search all documents).

### Offline test for the MCP wiring

```bash
python tests/test_mcp_scoping.py
```

Needs no API keys, Neo4j or Qdrant: it starts the real MCP server with fake databases and
checks the allow-lists, the document lock and the quant flow.

## Configuration

`config.py` validates Neo4j, Google, Groq, and Qdrant configuration at import
time. The default Qdrant collection is `arthikgyaan_chunks`. The configured
embedding model is `all-MiniLM-L6-v2` with an embedding dimension of `384`.

The extraction path currently uses Groq, while answer generation and retrieval
routing use Gemini. Provider selection and fallback behavior are centralized in
`llm/provider.py`. Extraction uses up to three workers and caches completed
batches under `.extraction_cache`.

## Dependencies

`requirements.txt` contains the project’s direct runtime dependencies. The main
external packages used by the source are Neo4j, Pydantic, python-dotenv,
LangChain integrations, Gemini and Groq providers, Hugging Face embeddings,
Qdrant, and tenacity.

When adding an import, add its PyPI package to `requirements.txt` and verify the
clean-environment setup before committing.

## Current Limitations

- PDF extraction currently focuses on text and does not extract tables or images.
- The application is operated through `main.py`; there is no CLI, API, or web UI.
- Retrieval routing and answer generation are LLM-driven and can produce
	incorrect classifications or answers.
- Risk scores depend on metrics extracted from document text and are not
	professional financial advice.
- Qdrant must be reachable before the application starts.
- Source provenance is stored for vector chunks but is not yet fully attached
	to every graph entity and relationship.
- Human review is currently an interactive terminal workflow.
- The MCP server binds to localhost by default and still needs production
  authentication and deployment configuration.
- Automated tests, migrations, and observability are still incomplete.

## Progress Tracked In Git

| Commit | Milestone |
| --- | --- | --- |
| `447a3f7` | Version 1.0 graph traversal, entity extraction, graph writing, prompts, sample PDFs, and question answering completed. |
| `892932a` | README documentation updated. |
| `e638016` | Requirements manifest updated for the expanding application. |
| `fd8d3fd` | Version 2 document hashing and document metadata registration added to avoid repeat ingestion. |
| `022f912` | Version 2 chunk batching implementation added. |
| `657e50a` | Qdrant vector indexing and retrieval work added. |
| `c9d594b` | Version 2 final testing milestone recorded. |
| `daf1980` | Version 2 implementation completed. |
| `d594175` | README updated before the Version 3 work. |
| `f08db39` | Version 3 parallel batch-request work started. |
| `9fced56` | Continued Version 3 workflow development. |
| `38e0f3a` | Version 3.1 testing milestone recorded. |
| `f498854` | Circular dependency fixes completed. |
| `07a7e5e` | Version 3.1 implementation completed. |
| `f6689c8` | Version 3.2 development started. |
| `7bbdcd9` | Version 3.2 daily progress milestone. |
| `b510e79` | Version 3.2 implementation completed. |
| `aa9a82d` | Version 3.0 full implementation completed; testing remained. |
| `06f48be` | Version 3 fixes applied. |
| `2bd0ca9` | Additional Version 3 fixes applied. |
| `52e81ce` | Version 3 fully functioning milestone. |
| `f3f79c1` | Final cleanup before Version 3 completion. |

## Next Development Priorities

1. Add automated tests for the parallel batch runner, entity resolution,
   workflow routing, MCP tools, and report generation.
2. Add document provenance to graph entities and relationships.
3. Add authentication and deployment guidance for the MCP server.
4. Improve table extraction and financial metric normalization.
5. Add query safety controls, observability, and production configuration.

## Maintainer

**Samriddha Raj Satyal**