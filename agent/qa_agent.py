import json
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm.provider import get_extraction_llm
from prompts.answer_prompt import ANSWER_PROMPT
from retrieval.router import route_question


def answer_question(question: str) -> str:
    retrieval_results = route_question(question)

    prompt = PromptTemplate(template=ANSWER_PROMPT, input_variables=["question", "results"])
    chain = prompt | get_extraction_llm(max_rounds=1) | StrOutputParser()
    response = chain.invoke({
        "question": question,
        "results": json.dumps(retrieval_results, indent=2, default=str),
    })
    return response.strip()