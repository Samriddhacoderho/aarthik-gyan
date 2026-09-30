ENTITY_RESOLUTION_PROMPT = """You are deduplicating entities extracted from a single financial document.
Below is a list of entity ids and names. Some of them refer to the SAME real-world entity
(e.g. "tesla", "tesla_inc", "company_main" might all mean the same company).

Group entities that refer to the same real-world thing. Pick the clearest/most specific id as
the canonical_id (prefer a proper name-based id like 'tesla_inc' over a generic one like 'company').
Only group entities of the SAME type (don't merge a Company with an Executive, for example).
If an entity has no duplicates, don't include it in any group — leave it out entirely.

{format_instructions}

Entities:
{entities}
"""