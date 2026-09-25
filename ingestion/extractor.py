from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from config import GROQ_API_KEY

from schemas.entities import ExtractionResult
from prompts.extraction_prompt import EXTRACTION_PROMPT
from ingestion.batching import batch_chunks, format_batch_for_prompt

parser = PydanticOutputParser(pydantic_object=ExtractionResult)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def extract_entities_from_batch(batch: list[str]) -> ExtractionResult:
    # model = ChatGoogleGenerativeAI(model="gemini-flash-latest")
    model = ChatGroq(model="qwen/qwen3.8-27b",temperature=0)
    prompt = PromptTemplate(
        template=EXTRACTION_PROMPT,
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | model | parser
    batch_text = format_batch_for_prompt(batch)
    try:
        return chain.invoke({"text": batch_text})
    except Exception as e:
        print(f"[extractor] Error processing batch of {len(batch)} chunks: {e}")
        return ExtractionResult(entities=[], relationships=[])


def extract_entities_from_document(chunks: list[str]) -> ExtractionResult:
    batches = batch_chunks(chunks)
    print(f"[extractor] {len(chunks)} chunks grouped into {len(batches)} batch(es).")

    all_entities = {}
    all_relationships = []

    for i, batch in enumerate(batches, 1):
        print(f"[extractor] Processing batch {i}/{len(batches)} ({len(batch)} chunks)...")
        result = extract_entities_from_batch(batch)
        for entity in result.entities:
            all_entities[entity.id] = entity  
        all_relationships.extend(result.relationships)

    return ExtractionResult(
        entities=list(all_entities.values()),
        relationships=all_relationships,
    )