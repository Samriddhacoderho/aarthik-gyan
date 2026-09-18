from graph.neo4j_client import neo4j_client
from schemas.entities import ExtractionResult

MERGE_ENTITY_QUERY = """
MERGE (e:Entity {id: $id})
SET e.name = $name, e.type = $type, e.description = $description
RETURN e
"""

MERGE_RELATIONSHIP_QUERY = """
MATCH (a:Entity {id: $source_id})
MATCH (b:Entity {id: $target_id})
MERGE (a)-[r:RELATION {type: $type}]->(b)
SET r.detail = $detail
RETURN r
"""


def write_extraction_to_graph(result: ExtractionResult):
    for entity in result.entities:
        neo4j_client.run_query(MERGE_ENTITY_QUERY, entity.model_dump())
        print(f"[writer] Merged entity: {entity.id} ({entity.type})")

    for rel in result.relationships:
        try:
            neo4j_client.run_query(MERGE_RELATIONSHIP_QUERY, rel.model_dump())
            print(f"[writer] Merged relationship: {rel.source_id} -{rel.type}-> {rel.target_id}")
        except Exception as e:
            print(f"[writer] Skipped relationship {rel.source_id}->{rel.target_id}: {e}")