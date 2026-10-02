from graph.neo4j_client import neo4j_client
from schemas.entities import ExtractionResult

MERGE_ENTITY_QUERY = """
MERGE (e:Entity {id: $id})
SET e.name = $name, e.type = $type, e.description = $description
WITH e
MATCH (d:Document {hash: $document_hash})
MERGE (d)-[:MENTIONS]->(e)
RETURN e
"""

MERGE_RELATIONSHIP_QUERY = """
MATCH (a:Entity {id: $source_id})
MATCH (b:Entity {id: $target_id})
MERGE (a)-[r:RELATION {type: $type}]->(b)
SET r.detail = $detail,
    r.source_document = $document_hash
RETURN r
"""


def write_extraction_to_graph(result: ExtractionResult, document_hash: str):
    for entity in result.entities:
        params = entity.model_dump()
        params["document_hash"] = document_hash
        neo4j_client.run_query(MERGE_ENTITY_QUERY, params)
        print(f"[writer] Merged entity: {entity.id} ({entity.type})")

    for rel in result.relationships:
        try:
            params = rel.model_dump()
            params["document_hash"] = document_hash
            neo4j_client.run_query(MERGE_RELATIONSHIP_QUERY, params)
            print(f"[writer] Merged relationship: {rel.source_id} -{rel.type}-> {rel.target_id}")
        except Exception as e:
            print(f"[writer] Skipped relationship {rel.source_id}->{rel.target_id}: {e}")