# Aarthik Gyan

Aarthik Gyan is a Python-based financial intelligence and knowledge graph
application. It ingests financial PDF documents, extracts structured entities
and relationships, stores them in Neo4j, indexes document chunks in Qdrant, and
answers questions using routed graph and semantic retrieval.

> **Status:** Version 2.0 implementation complete; final testing and continued
> improvements are in progress.

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
│   ├── document_registry.py    # Hash and ingestion-status tracking
│   ├── extractor.py            # Batched LLM extraction
│   └── pdf_parser.py           # PDF loading and chunking
├── prompts/                    # Extraction, Cypher, and answer prompts
├── retrieval/
│   ├── graph_retrieval.py      # Neo4j retrieval
│   ├── router.py               # GRAPH/VECTOR/BOTH routing
│   └── vector_retriever.py     # Semantic retrieval
├── risk/
│   ├── ratios.py               # Metric extraction and ratio calculation
│   └── risk_agent.py           # Risk scoring and graph persistence
├── schemas/
│   ├── __init__.py
│   ├── entities.py             # Entity and relationship models
│   └── risk.py                 # Financial metric and risk models
├── vectorstore/
│   ├── embedder.py             # Hugging Face embeddings
│   ├── indexer.py              # Qdrant indexing and search
│   └── qdrant_client.py        # Qdrant connection and collection setup
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
hash was already registered, ingests `documents/NASDAQ_TSLA_2025.pdf`, indexes
its chunks, calculates risk scores for extracted companies, and asks a question
using routed retrieval. Change the document path and question in `main.py` to
process another file.

## Configuration

`config.py` validates Neo4j, Google, Groq, and Qdrant configuration at import
time. The default Qdrant collection is `arthikgyaan_chunks`. The configured
embedding model is `all-MiniLM-L6-v2` with an embedding dimension of `384`.

The extraction path currently uses Groq, while answer generation and retrieval
routing use Gemini. Provider selection can be changed in the relevant modules.

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
- Automated tests, migrations, observability, and production deployment
	configuration are still incomplete.

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

## Next Development Priorities

1. Add automated tests for parsing, batching, schema validation, deduplication,
   retrieval routing, and risk calculations.
2. Add document provenance to graph entities and relationships.
3. Improve table extraction and financial metric normalization.
4. Add query safety controls and stronger validation for generated Cypher.
5. Replace hard-coded demo settings with a CLI or API interface.
6. Add observability, deployment documentation, and production configuration.

## Maintainer

**Samriddha Raj Satyal**