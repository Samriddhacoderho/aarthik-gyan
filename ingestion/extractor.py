from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, GROQ_MODEL,GEMINI_MODEL

from schemas.entities import ExtractionResult, parser_extraction as parser
from prompts.extraction_prompt import EXTRACTION_PROMPT
from ingestion.batching import batch_chunks, format_batch_for_prompt
from ingestion.batching import batch_chunks
from ingestion.batch_runner import run_batches_parallel, retry_failed_batches



@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def extract_entities_from_batch(batch: list[str]) -> ExtractionResult:
    # model = ChatGoogleGenerativeAI(model=GEMINI_MODEL)
    model = ChatGroq(model=GROQ_MODEL,temperature=0)
    prompt = PromptTemplate(
        template=EXTRACTION_PROMPT,
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | model | parser
    batch_text = format_batch_for_prompt(batch)
    return chain.invoke({"text": batch_text})


def extract_entities_from_document(chunks: list[str]) -> tuple[ExtractionResult, list[dict]]:
    """Batches, extracts in parallel, retries failures once, merges results.
    Returns (merged_result, permanently_failed_batches) — caller decides how
    to treat a document with some permanently failed batches (V3.1: mark as
    'partial' in the registry rather than silently calling it 'completed')."""


    batches = batch_chunks(chunks)
    print(f"[extractor] {len(chunks)} chunks grouped into {len(batches)} batch(es).")

    results, failures = run_batches_parallel(batches)
    retried_results, still_failing = retry_failed_batches(failures, max_retries=1)
    results.extend(retried_results)

    all_entities = {}
    all_relationships = []
    for result in results:
        for entity in result.entities:
            all_entities[entity.id] = entity
        all_relationships.extend(result.relationships)

    merged = ExtractionResult(entities=list(all_entities.values()), relationships=all_relationships)
    return merged, still_failing