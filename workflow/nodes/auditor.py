import re
from langgraph.prebuilt import create_react_agent

from llm.provider import get_llm
from llm.text_utils import strip_think
from workflow.mcp_client import node_toolbox
from workflow.scoped_tools import make_document_search_tool
from workflow.state import GraphState
from prompts.auditor_prompt import AUDITOR_SYSTEM_PROMPT

MAX_CONNECTIONS_IN_PROMPT = 20    # keeps the prompt small (free-tier token limits)


def _format_profile(profile) -> str:
    if not isinstance(profile, dict) or "error" in profile:
        return "(no profile found in the graph)"
    return (f"name: {profile.get('name')}\n"
            f"description: {profile.get('description') or 'n/a'}\n"
            f"direct relationships in the graph: {profile.get('relationship_count', 0)}")


def _format_connections(entities: list[dict]) -> str:
    if not entities:
        return "(no connected entities found)"
    lines = [f"- {e.get('name')} [{e.get('type')}] via {' > '.join(e.get('relationship_path') or [])}"
             for e in entities[:MAX_CONNECTIONS_IN_PROMPT]]
    if len(entities) > MAX_CONNECTIONS_IN_PROMPT:
        lines.append(f"(+ {len(entities) - MAX_CONNECTIONS_IN_PROMPT} more not shown)")
    return "\n".join(lines)


async def auditor_node(state: GraphState) -> dict:
    print(f"[auditor] Investigating {state['company_name']}...")

    async with node_toolbox("auditor") as tools:
        profile = await tools.call("get_company_profile", {"company_id": state["company_id"]})
        connections = await tools.call("get_connected_entities", {"company_id": state["company_id"], "hops": 2})

        search_tool = make_document_search_tool(tools, state["document_hash"])
        agent = create_react_agent(get_llm(), [search_tool])

        prompt = AUDITOR_SYSTEM_PROMPT.format(
            company_name=state["company_name"], company_id=state["company_id"],
            profile_block=_format_profile(profile), connections_block=_format_connections(connections),
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"recursion_limit": 12},
        )

    text = strip_think(result["messages"][-1].text)
    findings = [re.sub(r"^[\-\*\u2022\s]+", "", line).strip() for line in text.split("\n") if line.strip()]
    if not findings:
        findings = ["The auditor produced no findings (the model returned an empty answer)."]

    print(f"[auditor] {len(findings)} finding(s) surfaced.")
    return {"auditor_findings": findings}
