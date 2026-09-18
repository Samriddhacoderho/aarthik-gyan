from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def run_query(self, query: str, parameters: dict | None = None) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def verify_connection(self):
        self.driver.verify_connectivity()
        print("[neo4j] Connected to Aura successfully.")


neo4j_client = Neo4jClient()