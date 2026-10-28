"""Document lifecycle operations that span Neo4j, Qdrant, and stored uploads.

Deletion is intentionally conservative:

* Relationships are removed only when they were last written by this document
  (``RELATION.source_document``). V3 stores one global edge per
  ``(source, type, target)`` triple, so a shared edge cannot be attributed to
  multiple documents.
* Entities are removed only when no other Document still mentions them.
* The content-addressed extraction cache is left alone. It is keyed by chunk
  text, so a later re-upload of the same PDF can still avoid LLM calls.
"""

from __future__ import annotations

import re
import shutil

from api.errors import ApiError, service_unavailable
from api.schemas import DeleteDocumentResponse
from api.services import ingestion_service
from api.settings import settings


_SHA256 = re.compile(r"[0-9a-f]{64}")


def _delete_graph_tx(tx, document_hash: str) -> dict[str, int]:
    relationships = tx.run(
        "MATCH ()-[r:RELATION]->() WHERE r.source_document = $hash RETURN count(r) AS count",
        hash=document_hash,
    ).single()["count"]
    tx.run(
        "MATCH ()-[r:RELATION]->() WHERE r.source_document = $hash DELETE r",
        hash=document_hash,
    )

    assessments = tx.run(
        """
        MATCH (d:Document {hash: $hash})<-[:BASED_ON]-(a:RiskAssessment)
        RETURN count(DISTINCT a) AS count
        """,
        hash=document_hash,
    ).single()["count"]
    tx.run(
        """
        MATCH (d:Document {hash: $hash})<-[:BASED_ON]-(a:RiskAssessment)-[:HAS_REVIEW]->(ev:ReviewEvent)
        DETACH DELETE ev
        """,
        hash=document_hash,
    )
    tx.run(
        """
        MATCH (d:Document {hash: $hash})<-[:BASED_ON]-(a:RiskAssessment)
        DETACH DELETE a
        """,
        hash=document_hash,
    )

    entities = tx.run(
        """
        MATCH (d:Document {hash: $hash})-[:MENTIONS]->(e:Entity)
        WITH DISTINCT d, e
        WHERE NOT EXISTS {
            MATCH (other:Document)-[:MENTIONS]->(e)
            WHERE other <> d
        }
        RETURN count(e) AS count
        """,
        hash=document_hash,
    ).single()["count"]
    tx.run(
        """
        MATCH (d:Document {hash: $hash})-[:MENTIONS]->(e:Entity)
        WITH DISTINCT d, e
        WHERE NOT EXISTS {
            MATCH (other:Document)-[:MENTIONS]->(e)
            WHERE other <> d
        }
        DETACH DELETE e
        """,
        hash=document_hash,
    )

    documents = tx.run(
        "MATCH (d:Document {hash: $hash}) RETURN count(d) AS count",
        hash=document_hash,
    ).single()["count"]
    tx.run("MATCH (d:Document {hash: $hash}) DETACH DELETE d", hash=document_hash)

    return {
        "entities": int(entities or 0),
        "relationships": int(relationships or 0),
        "assessments": int(assessments or 0),
        "documents": int(documents or 0),
    }


def _delete_graph(document_hash: str) -> dict[str, int]:
    try:
        from graph.neo4j_client import neo4j_client
    except Exception as exc:
        raise service_unavailable("Neo4j") from exc

    try:
        with neo4j_client.driver.session() as session:
            return session.execute_write(_delete_graph_tx, document_hash)
    except Exception as exc:
        raise service_unavailable("Neo4j") from exc


def _delete_qdrant_points(document_hash: str) -> int:
    try:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        from config import QDRANT_COLLECTION
        from vectorstore.qdrant_client import vector_store_client
    except Exception as exc:
        raise service_unavailable("Qdrant") from exc

    point_filter = Filter(
        must=[FieldCondition(key="document_hash", match=MatchValue(value=document_hash))]
    )
    try:
        count = vector_store_client.client.count(
            collection_name=QDRANT_COLLECTION,
            count_filter=point_filter,
            exact=True,
        ).count
        vector_store_client.client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=FilterSelector(filter=point_filter),
        )
        return int(count)
    except Exception as exc:
        raise service_unavailable("Qdrant") from exc


def _remove_upload(document_hash: str) -> bool:
    if not _SHA256.fullmatch(document_hash):
        return False
    root = settings.upload_path.resolve()
    target = (settings.upload_path / document_hash).resolve()
    if not target.is_dir() or not target.is_relative_to(root):
        return False
    try:
        shutil.rmtree(target)
    except OSError:
        return False
    return True


def _mark_failed_best_effort(document_hash: str) -> None:
    """If graph deletion fails after vectors were removed, make retry possible."""
    try:
        from graph.neo4j_client import neo4j_client

        neo4j_client.run_query(
            "MATCH (d:Document {hash: $hash}) "
            "SET d.status = 'failed', d.failed_batch_count = null RETURN d",
            {"hash": document_hash},
        )
    except Exception:
        pass


def delete_document(document_hash: str) -> DeleteDocumentResponse:
    """Remove a document from Neo4j and Qdrant, then delete its stored PDF."""
    from api.services.graph_service import get_document

    document = get_document(document_hash)
    if ingestion_service.active_job_for_hash(document_hash) is not None:
        raise ApiError(
            409,
            "ingestion_in_progress",
            "An ingestion job is running for this document. Try again when it finishes.",
        )

    with ingestion_service.ingestion_lock():
        # Re-check inside the lock: a retry/upload job could have been created
        # between the first check and acquiring the lock.
        if ingestion_service.active_job_for_hash(document_hash) is not None:
            raise ApiError(
                409,
                "ingestion_in_progress",
                "An ingestion job is running for this document. Try again when it finishes.",
            )

        # Delete vectors first: if Neo4j then fails, the document is still
        # listed and can be retried/re-ingested instead of leaving invisible
        # chunks behind in Qdrant.
        deleted_points = _delete_qdrant_points(document_hash)
        try:
            deleted = _delete_graph(document_hash)
        except Exception:
            _mark_failed_best_effort(document_hash)
            raise
        upload_removed = _remove_upload(document_hash)
        ingestion_service.forget_jobs(document_hash)

    return DeleteDocumentResponse(
        document_hash=document_hash,
        filename=document.filename,
        deleted_entities=deleted["entities"],
        deleted_relationships=deleted["relationships"],
        deleted_assessments=deleted["assessments"],
        deleted_points=deleted_points,
        upload_removed=upload_removed,
    )
