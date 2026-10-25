METRICS_EXTRACTION_PROMPT = """You are a financial analyst. Extract the figures below for the company's
MOST RECENT fiscal year only. Statements often show two years side by side: always use the latest
year's column and ignore prior-year comparatives. Keep figures in the units printed (do not convert).
If a figure is not present, leave it null. Do NOT guess. Strip currency symbols and commas.

Definitions:
- total_debt: interest-bearing borrowings only: current portion of long-term debt plus long-term debt
  (term loans, revolver draws, notes, equipment financing). Exclude accounts payable, accrued expenses,
  lease liabilities, deferred taxes and pension obligations. Only if no debt breakdown exists at all,
  use total liabilities.
- total_equity: total shareholders' / owners' equity.
- current_assets / current_liabilities: the "Total current" lines on the balance sheet.
- revenue / net_income: for the latest fiscal year.

{format_instructions}

Financial statement text:
---
{text}
---
"""