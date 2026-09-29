from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential

from graph.neo4j_client import neo4j_client
from prompts.cypher_generation_prompt import CYPHER_GEN_PROMPT
from config import GEMINI_MODEL, GROQ_MODEL


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def generate_cypher(question: str) -> str:
    # model = ChatGroq(model=GROQ_MODEL, temperature=0)
    model = ChatGoogleGenerativeAI(model=GEMINI_MODEL)
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