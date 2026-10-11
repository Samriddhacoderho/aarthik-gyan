from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_not_exception_type
from langchain_core.prompts import PromptTemplate

from llm.provider import get_extraction_llm, AllProvidersExhausted
from schemas.entities import ExtractionResult, parser_extraction as parser
from prompts.extraction_prompt import EXTRACTION_PROMPT
from ingestion.batching import format_batch_for_prompt


@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(1),
    retry=retry_if_not_exception_type(AllProvidersExhausted),  
    reraise=True,
)
def extract_entities_from_batch(batch: list[str]) -> ExtractionResult:
    prompt = PromptTemplate(
        template=EXTRACTION_PROMPT,
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | get_extraction_llm() | parser
    return chain.invoke({"text": format_batch_for_prompt(batch)})