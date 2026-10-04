from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, GROQ_MODEL,GEMINI_MODEL

from llm.provider import get_llm
from schemas.entities import ExtractionResult, parser_extraction as parser
from prompts.extraction_prompt import EXTRACTION_PROMPT
from ingestion.batching import format_batch_for_prompt

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def extract_entities_from_batch(batch: list[str]) -> ExtractionResult:
    # model = ChatGoogleGenerativeAI(model=GEMINI_MODEL)
    model = ChatGroq(model=GROQ_MODEL,temperature=0)
    prompt = PromptTemplate(
        template=EXTRACTION_PROMPT,
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | get_llm() | parser
    batch_text = format_batch_for_prompt(batch)
    return chain.invoke({"text": batch_text})