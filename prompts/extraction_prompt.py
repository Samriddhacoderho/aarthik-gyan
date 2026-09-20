EXTRACTION_PROMPT = """You are a financial document analyst. You will be given several excerpts
(labeled CHUNK 1, CHUNK 2, etc.) from the SAME financial/annual report. Extract entities and
relationships found across ALL the chunks below, treating them as one continuous document.

Only extract entities of type: Company, Executive, Subsidiary, RiskFactor, Auditor.
Only extract relationships of type: OWNS, OWES_DEBT_TO, SUPPLIES_TO, AUDITED_BY, EMPLOYS, FLAGGED_FOR, SUBSIDIARY_OF.

Rules:
- Every relationship's source_id and target_id MUST match an id in the entities list.
- Use short lowercase_snake_case ids. If the same entity appears in multiple chunks, use the
  SAME id for it — do not create duplicates.
- If nothing relevant is found in a chunk, that's fine — just don't invent entities.

{format_instructions}

Document excerpts:
---
{text}
---
"""