from agent.qa_agent import answer_question
from ingestion.pdf_parser import extract_text_from_pdf, chunk_text
from ingestion.extractor import extract_entities_from_document
from ingestion.entity_resolution import resolve_entities
from ingestion.document_registry import (compute_file_hash, is_already_ingested, register_document,register_partial_document, mark_document_failed)
from graph.neo4j_client import neo4j_client
from graph.writer import write_extraction_to_graph
from vectorstore.indexer import index_chunks
from vectorstore.qdrant_client import vector_store_client
from risk.risk_agent import run_risk_agent

CREATE_DOCUMENT_NODE_QUERY = """
MERGE (d:Document {hash: $hash})
SET d.filename = $filename, d.status = 'processing'
RETURN d
"""

def pick_primary_company(result):
    """The company the document is about is the Company entity with the most relationships."""
    companies = {e.id: e for e in result.entities if e.type == "Company"}
    counts = {cid: 0 for cid in companies}
    for r in result.relationships:
        if r.source_id in counts: counts[r.source_id] += 1
        if r.target_id in counts: counts[r.target_id] += 1
    return companies[max(counts, key=counts.get)] if counts else None

def _report(on_progress, event: dict):
    """Progress callbacks are optional and must never interrupt ingestion."""
    if on_progress is None:
        return
    try:
        on_progress(event)
    except Exception:
        pass


def ingest(file_path: str, on_progress=None):
    file_hash = compute_file_hash(file_path)
    filename = file_path.split("/")[-1]

    if is_already_ingested(file_hash):
        print(f"[main] '{filename}' already ingested — skipping.")
        return

    neo4j_client.run_query(CREATE_DOCUMENT_NODE_QUERY, {"hash": file_hash, "filename": filename})

    _report(on_progress, {"event": "stage", "stage": "reading"})
    print(f"[main] Reading {file_path}...")
    docs = extract_text_from_pdf(file_path)
    chunks = chunk_text(docs)
    print(f"[main] Split into {len(chunks)} chunks.")

    try:
        _report(on_progress, {"event": "stage", "stage": "extracting"})
        result, failed_batches = extract_entities_from_document(chunks, on_progress=on_progress)
        print(f"[main] Extracted {len(result.entities)} entities, {len(result.relationships)} relationships "
              f"({len(failed_batches)} batch(es) permanently failed).")

        result = resolve_entities(result)
        print(f"[main] After dedup: {len(result.entities)} entities.")

        _report(on_progress, {"event": "stage", "stage": "writing"})
        write_extraction_to_graph(result, file_hash)
        _report(on_progress, {"event": "stage", "stage": "indexing"})
        index_chunks(chunks, filename, file_hash)

        primary = pick_primary_company(result)
        if primary:
            _report(on_progress, {"event": "stage", "stage": "risk"})
            run_risk_agent(primary.id, primary.name, file_hash)

        if failed_batches:
            register_partial_document(file_hash, filename, len(result.entities), len(result.relationships), len(failed_batches))
        else:
            register_document(file_hash, filename, len(result.entities), len(result.relationships))

        _report(on_progress, {"event": "stage", "stage": "done"})
        print("[main] Ingestion complete.")
    except Exception as e:
        print(f"[main] Ingestion failed: {e}")
        try:
            mark_document_failed(file_hash, filename)
        except Exception as registry_error:
            print(f"[main] Also could not mark document failed: {registry_error}")
        raise


def ask(question: str):
    print(f"\n[main] Q: {question}")
    answer = answer_question(question)
    print(f"[main] A: {answer}\n")


if __name__ == "__main__":
    neo4j_client.verify_connection()
    vector_store_client.verify_connection()
    
    ingest("documents/Brightwater_Industrial_Systems_FY2025_Annual_Report.pdf")
    ask("Summary of the document")

    neo4j_client.close()









