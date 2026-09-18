from langchain_google_genai import ChatGoogleGenerativeAI
from prompts.extraction_prompt import EXTRACTION_PROMPT
from langchain_core.prompts import PromptTemplate
from schemas.entities import ExtractionResult, parser
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def extract_entities_from_chunk(chunk):
    '''Extracts entities and relationships from a list of text chunks using an LLM and the defined prompt. Returns a list of ExtractionResult objects.'''
    model = ChatGoogleGenerativeAI(model="gemini-flash-latest")
    prompt=PromptTemplate(
        template=EXTRACTION_PROMPT,
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    chain=prompt | model | parser
    try:
        result=chain.invoke({"text": chunk.page_content})
        return result
    except Exception as e:
        print(f"Error processing chunk: {e}")
        return ExtractionResult(entities=[],relationships=[])

def extract_entities_from_chunks(chunks):
    '''Extracts entities and relationships from a list of text chunks using an LLM and the defined prompt. Returns a list of ExtractionResult objects.'''
    all_entities = {}
    all_relationships = []    
    for i,chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}")
        result=extract_entities_from_chunk(chunk)
        for entity in result.entities:
            all_entities[entity.id] = entity
        all_relationships.extend(result.relationships)
        
    return ExtractionResult(
        entities=list(all_entities.values()),
        relationships=all_relationships,
    )
    
