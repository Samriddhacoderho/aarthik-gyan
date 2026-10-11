from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            max_connection_lifetime=180,         
            liveness_check_timeout=30,         
            keep_alive=True,
            connection_timeout=30,
            connection_acquisition_timeout=60,
            max_transaction_retry_time=60,       
        )

    def close(self):
        self.driver.close()

    def run_query(self, query: str, parameters: dict | None = None) -> list[dict]:
        records, _, _ = self.driver.execute_query(query, parameters or {})
        return [record.data() for record in records]

    def verify_connection(self):
        self.driver.verify_connectivity()
        print("[neo4j] Connected to Aura successfully.")


neo4j_client = Neo4jClient()