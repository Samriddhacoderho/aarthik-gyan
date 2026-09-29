import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential

from prompts.answer_prompt import ANSWER_PROMPT
from retrieval.router import route_question
from config import GEMINI_MODEL, GROQ_MODEL


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def answer_question(question: str) -> str:
    retrieval_results = route_question(question)

    model = ChatGoogleGenerativeAI(model=GEMINI_MODEL)
    # model = ChatGroq(model=GROQ_MODEL, temperature=0)
    prompt = PromptTemplate(template=ANSWER_PROMPT, input_variables=["question", "results"])
    chain = prompt | model | StrOutputParser()
    response = chain.invoke({
        "question": question,
        "results": json.dumps(retrieval_results, indent=2, default=str),
    })
    return response.strip()

