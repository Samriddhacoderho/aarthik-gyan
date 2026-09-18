# Aarthik Gyan

Aarthik Gyan is a Python-based financial knowledge graph application. It turns
financial PDF documents into structured entities and relationships, stores them
in Neo4j, and answers questions by translating natural language into Cypher
queries over the graph.

> **Status:** Version 1.0 implementation complete; active development continues.

## What Is Working

The current codebase implements an end-to-end graph RAG prototype:

1. Load text from PDF documents with PyMuPDF/LangChain PDF tooling.
2. Split documents into overlapping chunks for LLM processing.
3. Extract typed entities and relationships with Gemini and Pydantic validation.
4. Deduplicate entities across chunks using stable entity IDs.
5. Merge entities and relationships into a Neo4j graph.
6. Generate up-to-two-hop Cypher queries from user questions.
7. Use graph results to produce concise financial answers.
8. Retry transient LLM operations up to three times with exponential backoff.

The v1.0 sample documents currently included in the repository are:

- `documents/Sample-Financial-Statements-1.pdf`
- `documents/NASDAQ_TSLA_2025.pdf`

## Architecture

```text
PDF document
		|
		v
pdf_parser.py  ->  chunked document text
		|
		v
extractor.py   ->  ExtractionResult (entities + relationships)
		|
		v
writer.py      ->  Neo4j Entity nodes and RELATION edges
		|
		v
qa_agent.py    ->  question -> Cypher -> graph results -> answer
```

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
│   ├── extractor.py            # Gemini extraction and deduplication
│   └── pdf_parser.py           # PDF loading and chunking
├── prompts/                    # Extraction, Cypher, and answer prompts
├── schemas/
│   ├── __init__.py
│   └── entities.py             # Pydantic graph models
├── config.py                   # Environment-backed configuration
├── main.py                     # Ingestion and question-answering entry point
├── requirements.txt
└── .env.example
```

## Prerequisites

- Python 3.10 or newer
- A Neo4j Aura instance or reachable Neo4j database
- A Google Gemini API key
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

	 Required values are `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and
	 `GOOGLE_API_KEY`. Do not commit `.env` or real credentials.

4. Run the current demo entry point:

	 ```bash
	 python main.py
	 ```

The entry point verifies Neo4j connectivity, ingests the sample financial
statement, then asks a graph question. Change the PDF path and question in
`main.py` to process a different document.

## Configuration And Dependency Note

`config.py` validates the required environment variables at import time. The
current source also imports LangChain integration packages and `tenacity`; the
dependency manifest should be kept synchronized with those imports before
distributing or deploying the project. This is a known follow-up item for the
next development pass.

## Current Limitations

- PDF extraction currently focuses on text and does not extract tables or images.
- The demo workflow is configured directly in `main.py` rather than exposed as
	a CLI or service.
- Cypher generation is LLM-driven and currently limited to queries of up to two
	graph hops.
- There are no automated tests, graph migrations, or observability dashboards
	yet.
- Source-document provenance is not stored on nodes or relationships.

## Progress Tracked In Git

| Commit | Date | Milestone |
| --- | --- | --- |
| `c8bbab2` | 2026-09-17 | Created the initial v1.0 project structure and core modules. |
| `776f561` | 2026-09-17 | Added the first project README and documented the intended pipeline. |
| `19eb630` | 2026-09-17 | Added the `.env.example` configuration template. |
| `447a3f7` | 2026-09-18 | Completed the v1.0 graph traversal, entity extraction, graph writing, prompts, sample PDFs, and question-answering flow. |

## Next Development Priorities

1. Finish and test the Neo4j writer workflow.
2. Synchronize `requirements.txt` with all runtime imports.
3. Add automated tests for parsing, schema validation, deduplication, and graph writes.
4. Add document provenance and source metadata to the graph.
5. Replace hard-coded demo settings with a CLI or API interface.
6. Improve table extraction, query safety, and production error handling.

## Maintainer

**Samriddha Raj Satyal**