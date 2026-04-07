from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import answer_node, clarify_node, fallback_answer_node, rewrite_query_node, search_node, understand_node
from .routing import route_after_search, route_after_understand
from .state import MedicalAgentState


def create_medical_agent():
    workflow = StateGraph(MedicalAgentState)
    workflow.add_node("understand", understand_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("search", search_node)
    workflow.add_node("rewrite", rewrite_query_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("fallback", fallback_answer_node)

    workflow.add_edge(START, "understand")
    workflow.add_conditional_edges(
        "understand",
        route_after_understand,
        {"clarify": "clarify", "search": "search"},
    )
    workflow.add_conditional_edges(
        "search",
        route_after_search,
        {"rewrite": "rewrite", "fallback": "fallback", "answer": "answer"},
    )
    workflow.add_edge("rewrite", "search")
    workflow.add_edge("clarify", END)
    workflow.add_edge("answer", END)
    workflow.add_edge("fallback", END)

    return workflow.compile(checkpointer=InMemorySaver())
