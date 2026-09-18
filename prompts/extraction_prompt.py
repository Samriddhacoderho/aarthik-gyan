EXTRACTION_PROMPT = """You are a financial document analyst. Extract entities and relationships
from the following excerpt of a financial/annual report.

Only extract entities of type: Company, Executive, Subsidiary, RiskFactor, Auditor.
Only extract relationships of type: OWNS, OWES_DEBT_TO, SUPPLIES_TO, AUDITED_BY, EMPLOYS, FLAGGED_FOR, SUBSIDIARY_OF.

Rules:
- Every relationship's source_id and target_id MUST match an id in the entities list.
- Use short lowercase_snake_case ids, consistent across chunks if the same entity reappears.
- If nothing relevant is found, return empty lists.

Return ONLY valid JSON matching this schema, no markdown fences, no commentary:
{format_instructions}

Document excerpt:
---
{text}
---
"""