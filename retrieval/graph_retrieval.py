from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential

from graph.neo4j_client import neo4j_client
from prompts.cypher_generation_prompt import CYPHER_GEN_PROMPT


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def generate_cypher(question: str) -> str:
    model = ChatGroq(model="qwen/qwen3-32b", temperature=0)
    prompt = PromptTemplate(template=CYPHER_GEN_PROMPT, input_variables=["question"])
    chain = prompt | model | StrOutputParser()
    response = chain.invoke({"question": question})
    return response.strip().removeprefix("```cypher").removeprefix("```").removesuffix("```").strip()


def retrieve_from_graph(question: str) -> dict:
    cypher = generate_cypher(question)
    try:
        results = neo4j_client.run_query(cypher)
        return {"source": "graph", "cypher": cypher, "results": results}
    except Exception as e:
        return {"source": "graph", "cypher": cypher, "results": [], "error": str(e)}