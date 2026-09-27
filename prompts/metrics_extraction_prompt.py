METRICS_EXTRACTION_PROMPT = """You are a financial analyst. Extract the following numeric figures
from the financial statement text below. If a figure is not present, leave it null — do NOT guess
or estimate. Strip currency symbols and commas; return plain numbers.

{format_instructions}

Financial statement text:
---
{text}
---
"""