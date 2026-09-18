import hashlib
from graph.neo4j_client import neo4j_client

CHECK_DOCUMENT_QUERY = """
MATCH (d:Document {hash: $hash})
RETURN d.status AS status, d.filename AS filename, d.ingested_at AS ingested_at
"""

REGISTER_DOCUMENT_QUERY = """
MERGE (d:Document {hash: $hash})
SET d.filename = $filename,
    d.status = $status,
    d.ingested_at = datetime(),
    d.entity_count = $entity_count,
    d.relationship_count = $relationship_count
RETURN d
"""

MARK_FAILED_QUERY = """
MERGE (d:Document {hash: $hash})
SET d.filename = $filename,
    d.status = 'failed',
    d.ingested_at = datetime()
RETURN d
"""


def compute_file_hash(file_path: str) -> str:
    """SHA-256 of file contents. Content-based, not filename-based. so renaming a file doesn't trigger a re-ingest, but editing it does."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_already_ingested(file_hash: str) -> bool:
    """Returns True only if a prior run completed successfully. A 'failed' or missing record means we should (re)process it."""
    results = neo4j_client.run_query(CHECK_DOCUMENT_QUERY, {"hash": file_hash})
    if not results:
        return False
    return results[0]["status"] == "completed"


def get_document_record(file_hash: str) -> dict | None:
    results = neo4j_client.run_query(CHECK_DOCUMENT_QUERY, {"hash": file_hash})
    return results[0] if results else None


def register_document(file_hash: str, filename: str, entity_count: int, relationship_count: int):
    neo4j_client.run_query(REGISTER_DOCUMENT_QUERY, {
        "hash": file_hash,
        "filename": filename,
        "status": "completed",
        "entity_count": entity_count,
        "relationship_count": relationship_count,
    })
    print(f"[registry] Registered '{filename}' as completed ({entity_count} entities, {relationship_count} relationships).")


def mark_document_failed(file_hash: str, filename: str):
    neo4j_client.run_query(MARK_FAILED_QUERY, {"hash": file_hash, "filename": filename})
    print(f"[registry] Marked '{filename}' as failed — it will be retried on next run.")