from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from llm.provider import get_llm
from schemas.entities import ExtractionResult, EntityResolutionResult,parser_entity_resolution as parser
from prompts.entity_resolution_prompt import ENTITY_RESOLUTION_PROMPT



@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=2, max=15))
def _classify_duplicates(entity_list_text: str) -> EntityResolutionResult:
    prompt = PromptTemplate(
        template=ENTITY_RESOLUTION_PROMPT,
        input_variables=["entities"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | get_llm() | parser
    return chain.invoke({"entities": entity_list_text})


def resolve_entities(result: ExtractionResult) -> ExtractionResult:
    """One extra LLM pass over the full entity list (not per-chunk) to merge
    duplicates like tesla/tesla_inc/company_main into one canonical id, then
    rewrites relationships to point at canonical ids."""
    if len(result.entities) < 2:
        return result

    entity_list_text = "\n".join(f"- id: {e.id}, name: {e.name}, type: {e.type}" for e in result.entities)

    try:
        resolution = _classify_duplicates(entity_list_text)
    except Exception as e:
        print(f"[entity_resolution] Failed, skipping dedup this run: {e}")
        return result

    alias_to_canonical = {}
    for group in resolution.groups:
        for alias in group.aliases:
            alias_to_canonical[alias] = group.canonical_id

    if not alias_to_canonical:
        print("[entity_resolution] No duplicates found.")
        return result

    print(f"[entity_resolution] Merging {len(alias_to_canonical)} alias(es) into canonical entities.")

    merged_entities = {}
    for entity in result.entities:
        canonical_id = alias_to_canonical.get(entity.id, entity.id) #entity.id=tesla -->cannonical_id=tesla_1
        if canonical_id not in merged_entities:
            entity.id = canonical_id
            merged_entities[canonical_id] = entity
        # if canonical already exists, we just drop this duplicate entity object

    for rel in result.relationships:
        rel.source_id = alias_to_canonical.get(rel.source_id, rel.source_id)
        rel.target_id = alias_to_canonical.get(rel.target_id, rel.target_id)

    return ExtractionResult(entities=list(merged_entities.values()), relationships=result.relationships)