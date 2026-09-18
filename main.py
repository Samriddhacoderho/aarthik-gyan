from ingestion.pdf_parser import extract_text_from_pdf, chunk_text
from ingestion.extractor import extract_entities_from_chunks
from graph.writer import write_extraction_to_graph
from graph.neo4j_client import neo4j_client
from agent.qa_agent import answer_question


def ingest(file_path: str):
    print(f"[main] Reading {file_path}...")
    docs = extract_text_from_pdf(file_path)
    chunks = chunk_text(docs)
    print(f"[main] Split into {len(chunks)} chunks.")

    result = extract_entities_from_chunks(chunks)
    print(f"[main] Extracted {len(result.entities)} entities, {len(result.relationships)} relationships.")

    write_extraction_to_graph(result)
    print("[main] Ingestion complete.")


def ask(question: str):
    print(f"\n[main] Q: {question}")
    answer = answer_question(question)
    print(f"[main] A: {answer}\n")


if __name__ == "__main__":
    neo4j_client.verify_connection()

    # Step 1: ingest a document once
    ingest("/Users/suhritsatyal/Desktop/2026/aarthikgyaan/documents/Sample-Financial-Statements-1.pdf")

    # Step 2: query the graph
    ask("Summarize the financial statements in the document.")

    neo4j_client.close()