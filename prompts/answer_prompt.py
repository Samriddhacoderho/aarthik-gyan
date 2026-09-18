ANSWER_PROMPT = """You are a financial risk analyst assistant. Given the graph query results below,
answer the user's question clearly and concisely. If the results are empty, say you found no
relevant relationships in the graph rather than guessing.

Question: {question}

Graph results (JSON):
{results}

Answer:
"""