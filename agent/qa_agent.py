import json
from langchain_google_genai import ChatGoogleGenerativeAI
from config import GOOGLE_API_KEY
from graph.neo4j_client import neo4j_client
from langchain_core.prompts import PromptTemplate

from prompts.cypher_generation_prompt import CYPHER_GEN_PROMPT
from prompts.answer_prompt import ANSWER_PROMPT
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def generate_cypher(question: str) -> str:
    model = ChatGoogleGenerativeAI(model="gemini-flash-latest")
    prompt=PromptTemplate(template=CYPHER_GEN_PROMPT,input_variables=['question'])
    chain=prompt | model | StrOutputParser()
    response = chain.invoke({"question": question})
    return response.strip().removeprefix("```cypher").removeprefix("```").removesuffix("```").strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def answer_question(question: str) -> str:
    model = ChatGoogleGenerativeAI(model="gemini-flash-latest")
    cypher = generate_cypher(question)
    print(f"[agent] Generated Cypher:\n{cypher}\n")
    try:
        results = neo4j_client.run_query(cypher)
    except Exception as e:
        return f"Query failed: {e}\nGenerated Cypher was:\n{cypher}"

    prompt=PromptTemplate(template=ANSWER_PROMPT,input_variables=['question','results'])
    chain=prompt | model | StrOutputParser()
    response = chain.invoke({"question": question, "results": json.dumps(results, indent=2)})
    return response.strip()