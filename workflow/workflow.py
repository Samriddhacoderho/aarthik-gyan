from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from workflow.state import GraphState
from workflow.nodes.auditor import auditor_node
from workflow.nodes.quant import quant_node
from workflow.nodes.hitl import hitl_node, route_after_hitl
from workflow.nodes.writer import writer_node

_checkpointer = MemorySaver()
_compiled_graph = None


def build_workflow():
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    graph = StateGraph(GraphState)

    graph.add_node("auditor", auditor_node)
    graph.add_node("quant", quant_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("writer", writer_node)

    graph.set_entry_point("auditor")
    graph.add_edge("auditor", "quant")
    graph.add_edge("quant", "hitl")
    graph.add_conditional_edges("hitl", route_after_hitl, {"writer": "writer", "quant": "quant", "hitl": "hitl"})
    graph.add_edge("writer", END)

    _compiled_graph = graph.compile(checkpointer=_checkpointer)
    return _compiled_graph