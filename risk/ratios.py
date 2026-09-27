from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from schemas.risk import FinancialMetrics, metrics_parser, RiskScore
from prompts import METRICS_EXTRACTION_PROMPT


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def extract_financial_metrics(text: str, company_hint: str) -> FinancialMetrics:
    model = ChatGroq(model="qwen/qwen3-32b", temperature=0)
    prompt = PromptTemplate(
        template=METRICS_EXTRACTION_PROMPT,
        input_variables=["text"],
        partial_variables={"format_instructions": metrics_parser.get_format_instructions()},
    )
    chain = prompt | model | metrics_parser
    try:
        result = chain.invoke({"text": text})
        if not result.company_name:
            result.company_name = company_hint
        return result
    except Exception as e:
        print(f"[ratios] Metrics extraction failed: {e}")
        return FinancialMetrics(company_name=company_hint)


def compute_risk_score(company_id: str, metrics: FinancialMetrics) -> RiskScore:
    """Pure arithmetic, rule-based thresholds — deliberately no ML/LLM here.
    Easy to explain, easy to audit, easy to justify in an interview."""
    notes = []
    debt_to_equity = None
    current_ratio = None
    net_margin = None
    risk_points = 0
    known_ratios = 0

    if metrics.total_debt is not None and metrics.total_equity:
        debt_to_equity = round(metrics.total_debt / metrics.total_equity, 2)
        known_ratios += 1
        if debt_to_equity > 2.0:
            risk_points += 2
            notes.append(f"High debt-to-equity ratio ({debt_to_equity}) — over 2.0 is considered leveraged.")
        elif debt_to_equity > 1.0:
            risk_points += 1
            notes.append(f"Moderate debt-to-equity ratio ({debt_to_equity}).")
        else:
            notes.append(f"Healthy debt-to-equity ratio ({debt_to_equity}).")

    if metrics.current_assets is not None and metrics.current_liabilities:
        current_ratio = round(metrics.current_assets / metrics.current_liabilities, 2)
        known_ratios += 1
        if current_ratio < 1.0:
            risk_points += 2
            notes.append(f"Current ratio below 1.0 ({current_ratio}) — potential short-term liquidity risk.")
        elif current_ratio < 1.5:
            risk_points += 1
            notes.append(f"Current ratio somewhat tight ({current_ratio}).")
        else:
            notes.append(f"Adequate current ratio ({current_ratio}).")

    if metrics.net_income is not None and metrics.revenue:
        net_margin = round(metrics.net_income / metrics.revenue, 3)
        known_ratios += 1
        if net_margin < 0:
            risk_points += 2
            notes.append(f"Negative net margin ({net_margin}) — company reported a loss.")
        elif net_margin < 0.05:
            risk_points += 1
            notes.append(f"Thin net margin ({net_margin}).")
        else:
            notes.append(f"Reasonable net margin ({net_margin}).")

    if known_ratios == 0:
        risk_level = "UNKNOWN"
        notes.append("Not enough numeric data extracted to compute any ratio.")
    elif risk_points >= 4:
        risk_level = "HIGH"
    elif risk_points >= 2:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return RiskScore(
        company_id=company_id,
        debt_to_equity=debt_to_equity,
        current_ratio=current_ratio,
        net_margin=net_margin,
        risk_level=risk_level,
        notes=notes,
    )