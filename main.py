from ingestion.pdf_parser import extract_text_from_pdf, chunk_text
from ingestion.extractor import extract_entities_from_document
from ingestion.document_registry import (compute_file_hash, is_already_ingested, register_document, mark_document_failed)
from graph.writer import write_extraction_to_graph
from graph.neo4j_client import neo4j_client
from agent.qa_agent import answer_question


def ingest(file_path: str):
    file_hash = compute_file_hash(file_path)
    filename = file_path.split("/")[-1]

    if is_already_ingested(file_hash):
        print(f"[main] '{filename}' already ingested (hash match):skipping extraction.")
        return

    print(f"[main] Reading {file_path}...")
    text = extract_text_from_pdf(file_path)
    chunks = chunk_text(text)
    print(f"[main] Split into {len(chunks)} chunks.")

    try:
        result = extract_entities_from_document(chunks)
        print(f"[main] Extracted {len(result.entities)} entities, {len(result.relationships)} relationships.")

        write_extraction_to_graph(result)
        register_document(file_hash, filename, len(result.entities), len(result.relationships))
        print("[main] Ingestion complete.")
    except Exception as e:
        print(f"[main] Ingestion failed: {e}")
        mark_document_failed(file_hash, filename)
        raise


def ask(question: str):
    print(f"\n[main] Q: {question}")
    answer = answer_question(question)
    print(f"[main] A: {answer}\n")


if __name__ == "__main__":
    neo4j_client.verify_connection()

    ingest("documents/Sample-Financial-Statements-1.pdf")
    ingest("documents/NASDAQ_TSLA_2025.pdf")

    ask("Compare the net income of all companies and give the count of highest net income")

    neo4j_client.close()