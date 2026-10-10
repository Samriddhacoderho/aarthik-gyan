from langchain.agents import create_agent
from llm.provider import get_llm
from workflow.mcp_client import get_mcp_tools
from workflow.state import GraphState
from prompts.auditor_prompt import AUDITOR_SYSTEM_PROMPT


def auditor_node(state: GraphState) -> dict:
    print(f"[auditor] Investigating {state['company_name']}...")
    tools = get_mcp_tools()
    agent = create_agent(get_llm(), tools)

    prompt = AUDITOR_SYSTEM_PROMPT.format(
        company_name=state["company_name"], company_id=state["company_id"]
    )
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})

    final_message = result["messages"][-1].content
    findings = [line.strip("- ").strip() for line in final_message.split("\n") if line.strip()]

    print(f"[auditor] {len(findings)} finding(s) surfaced.")
    return {"auditor_findings": findings}