import re
from langgraph.prebuilt import create_react_agent

from llm.provider import get_llm
from llm.text_utils import strip_think
from workflow.mcp_client import get_mcp_tools
from workflow.state import GraphState
from prompts.auditor_prompt import AUDITOR_SYSTEM_PROMPT


async def auditor_node(state: GraphState) -> dict:
    print(f"[auditor] Investigating {state['company_name']}...")
    tools = await get_mcp_tools()
    agent = create_react_agent(get_llm(), tools)

    prompt = AUDITOR_SYSTEM_PROMPT.format(
        company_name=state["company_name"], company_id=state["company_id"]
    )
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": 25},
    )

    text = strip_think(result["messages"][-1].text)
    findings = [re.sub(r"^[\-\*\u2022\s]+", "", line).strip() for line in text.split("\n") if line.strip()]
    if not findings:
        findings = ["The auditor produced no findings (the model returned an empty answer)."]

    print(f"[auditor] {len(findings)} finding(s) surfaced.")
    return {"auditor_findings": findings}