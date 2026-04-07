from __future__ import annotations

from langgraph.graph import END

from .state import MedicalAgentState


def route_after_understand(state: MedicalAgentState) -> str:
    return "clarify" if state.get("route") == "clarify" else "search"


def route_after_search(state: MedicalAgentState) -> str:
    route = state.get("route")
    if route == "rewrite":
        return "rewrite"
    if route == "fallback":
        return "fallback"
    return "answer"


ROUTE_FROM_ANSWER = {"answer": END, "fallback": END, "clarify": END}
