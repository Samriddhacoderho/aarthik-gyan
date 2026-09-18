CYPHER_GEN_PROMPT = """Given the user's question, generate a Cypher query for a Neo4j graph
with this structure:
- Nodes: (:Entity {{id, name, type, description}})
- Edges: (:Entity)-[:RELATION {{type, detail}}]->(:Entity)

Question: {question}

Return ONLY the Cypher query, no markdown fences, no explanation.
Use MATCH with up to 2 hops. Always RETURN readable fields (names, types, relation types, details).
"""