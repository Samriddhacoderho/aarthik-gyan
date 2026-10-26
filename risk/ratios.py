from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from llm.provider import get_extraction_llm
from schemas.risk import FinancialMetrics, metrics_parser, RiskScore
from prompts.metrics_extraction_prompt import METRICS_EXTRACTION_PROMPT
from config import GEMINI_MODEL, GROQ_MODEL
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
from llm.provider import get_extraction_llm, AllProvidersExhausted


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5),
       retry=retry_if_not_exception_type(AllProvidersExhausted), reraise=True)
def extract_financial_metrics(text: str, company_hint: str, analyst_hint: str | None = None) -> FinancialMetrics:
    prompt = PromptTemplate(
        template=METRICS_EXTRACTION_PROMPT,
        input_variables=["text", "analyst_hint"],
        partial_variables={"format_instructions": metrics_parser.get_format_instructions()},
    )
    chain = prompt | get_extraction_llm() | metrics_parser
    try:
        result = chain.invoke({"text": text, "analyst_hint": analyst_hint or "None provided."})
        if not result.company_name:
            result.company_name = company_hint
        return result
    except AllProvidersExhausted:
        raise   # both LLMs failed: a failed call must fail loudly, not become an empty score
    except Exception as e:  # e.g. unparseable output
        print(f"[ratios] Metrics extraction failed: {e}")
        return FinancialMetrics(company_name=company_hint)


def score_from_ratios(company_id: str, debt_to_equity: float | None, current_ratio: float | None,
                      net_margin: float | None) -> RiskScore:
    """The rules, and only the rules: ratios in, risk level + human-readable notes out.
    Used by the automatic score AND by the analyst override, so both always follow the same thresholds."""
    notes = []
    risk_points = 0
    known_ratios = 0

    if debt_to_equity is not None:
        known_ratios += 1
        if debt_to_equity > 2.0:
            risk_points += 2
            notes.append(f"High debt-to-equity ratio ({debt_to_equity}) — over 2.0 is considered leveraged.")
        elif debt_to_equity > 1.0:
            risk_points += 1
            notes.append(f"Moderate debt-to-equity ratio ({debt_to_equity}).")
        else:
            notes.append(f"Healthy debt-to-equity ratio ({debt_to_equity}).")

    if current_ratio is not None:
        known_ratios += 1
        if current_ratio < 1.0:
            risk_points += 2
            notes.append(f"Current ratio below 1.0 ({current_ratio}) — potential short-term liquidity risk.")
        elif current_ratio < 1.5:
            risk_points += 1
            notes.append(f"Current ratio somewhat tight ({current_ratio}).")
        else:
            notes.append(f"Adequate current ratio ({current_ratio}).")

    if net_margin is not None:
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


def compute_risk_score(company_id: str, metrics: FinancialMetrics) -> RiskScore:
    """Pure arithmetic, rule-based thresholds — deliberately no ML/LLM here.
    Easy to explain, easy to audit, easy to justify in an interview."""
    debt_to_equity = None
    current_ratio = None
    net_margin = None

    if metrics.total_debt is not None and metrics.total_equity:
        debt_to_equity = round(metrics.total_debt / metrics.total_equity, 2)

    if metrics.current_assets is not None and metrics.current_liabilities:
        current_ratio = round(metrics.current_assets / metrics.current_liabilities, 2)

    if metrics.net_income is not None and metrics.revenue:
        net_margin = round(metrics.net_income / metrics.revenue, 3)

    return score_from_ratios(company_id, debt_to_equity, current_ratio, net_margin)