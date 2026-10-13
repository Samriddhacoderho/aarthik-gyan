from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm.provider import get_extraction_llm
from prompts.retrieval_routing_prompt import ROUTING_PROMPT
from retrieval.graph_retrieval import retrieve_from_graph
from retrieval.vector_retriever import retrieve_from_vector


def classify_question(question: str) -> str:
    prompt = PromptTemplate(template=ROUTING_PROMPT, input_variables=["question"])
    chain = prompt | get_extraction_llm(max_rounds=1) | StrOutputParser()
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