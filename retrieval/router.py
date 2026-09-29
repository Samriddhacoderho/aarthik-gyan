from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential

from prompts.retrieval_routing_prompt import ROUTING_PROMPT
from retrieval.graph_retrieval import retrieve_from_graph
from retrieval.vector_retriever import retrieve_from_vector
from config import GEMINI_MODEL, GROQ_MODEL


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def classify_question(question: str) -> str:
    # model = ChatGroq(model=GROQ_MODEL, temperature=0)
    model = ChatGoogleGenerativeAI(model=GEMINI_MODEL)
    prompt = PromptTemplate(template=ROUTING_PROMPT, input_variables=["question"])
    chain = prompt | model | StrOutputParser()
    response = chain.invoke({"question": question}).strip().upper()
    if response not in ("GRAPH", "VECTOR", "BOTH"):
        print(f"[router] Unexpected routing response '{response}', defaulting to BOTH.")
        return "BOTH"
    return response


def route_question(question: str) -> list[dict]:
    """Returns a list of retrieval results — one dict per source actually queried."""
    route = classify_question(question)
    print(f"[router] Routed question to: {route}")

    results = []
    if route in ("GRAPH", "BOTH"):
        results.append(retrieve_from_graph(question))
    if route in ("VECTOR", "BOTH"):
        results.append(retrieve_from_vector(question))
    return results