from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from graph.neo4j_client import neo4j_client
from llm.provider import get_extraction_llm
from prompts.cypher_generation_prompt import CYPHER_GEN_PROMPT


def generate_cypher(question: str) -> str:
    prompt = PromptTemplate(template=CYPHER_GEN_PROMPT, input_variables=["question"])
    chain = prompt | get_extraction_llm(max_rounds=1) | StrOutputParser()
    response = chain.invoke({"question": question})
    return response.strip().removeprefix("```cypher").removeprefix("```").removesuffix("```").strip()


def retrieve_from_graph(question: str) -> dict:
    cypher = generate_cypher(question)
    try:
        results = neo4j_client.run_query(cypher)
        return {"source": "graph", "cypher": cypher, "results": results}
    except Exception as e:
        return {"source": "graph", "cypher": cypher, "results": [], "error": str(e)}