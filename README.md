# Aarthik Gyan

Aarthik Gyan is a Python-based financial knowledge platform designed to extract, structure, and organize information from financial documents.

The project combines PDF processing, information extraction, structured data models, and a Neo4j graph database to build a foundation for a searchable financial knowledge graph.

> **Status:** Early development — Version 1.0 codebase

## Overview

Aarthik Gyan is organized around a modular ingestion and graph-processing pipeline:

1. Parse financial documents such as PDFs.
2. Extract relevant entities and relationships.
3. Validate structured data using Pydantic schemas.
4. Store knowledge in a Neo4j graph database.
5. Use agent-based components for quality assurance and future intelligent processing.

## Project Structure

```text
.
├── agent/
│   ├── __init__.py
│   └── qa_agent.py
├── graph/
│   ├── __init__.py
│   ├── neo4j_client.py
│   └── writer.py
├── ingestion/
│   ├── __init__.py
│   ├── extractor.py
│   └── pdf_parser.py
├── schemas/
│   ├── __init__.py
│   └── entities.py
├── config.py
├── main.py
├── requirements.txt
└── .gitignore
