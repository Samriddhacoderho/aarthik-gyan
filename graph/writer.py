from graph.neo4j_client import neo4j_client
from schemas.entities import ExtractionResult

WRITE_ENTITIES_QUERY = """
MATCH (d:Document {hash: $document_hash})
UNWIND $entities AS ent
MERGE (e:Entity {id: ent.id})
SET e.name = ent.name, e.type = ent.type, e.description = ent.description
MERGE (d)-[:MENTIONS]->(e)
"""

WRITE_RELATIONSHIPS_QUERY = """
UNWIND $relationships AS rel
MATCH (a:Entity {id: rel.source_id})
MATCH (b:Entity {id: rel.target_id})
MERGE (a)-[r:RELATION {type: rel.type}]->(b)
SET r.detail = rel.detail, r.source_document = $document_hash
"""


def write_extraction_to_graph(result: ExtractionResult, document_hash: str):
    entities = [e.model_dump() for e in result.entities]
    relationships = [r.model_dump() for r in result.relationships]

    if entities:
        neo4j_client.run_query(WRITE_ENTITIES_QUERY, {"document_hash": document_hash, "entities": entities})
        print(f"[writer] Merged {len(entities)} entities.")

    if relationships:
        neo4j_client.run_query(WRITE_RELATIONSHIPS_QUERY, {"document_hash": document_hash, "relationships": relationships})
        print(f"[writer] Merged up to {len(relationships)} relationships "
              f"(any pointing at a missing entity id are skipped).")