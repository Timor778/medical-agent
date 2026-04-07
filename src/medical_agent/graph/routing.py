from __future__ import annotations

from langgraph.graph import END

from .state import MedicalAgentState


def route_after_understand(state: MedicalAgentState) -> str:
    # understand 节点会把 route 写进状态，这里只负责按照 route 选边。
    return "clarify" if state.get("route") == "clarify" else "search"


def route_after_search(state: MedicalAgentState) -> str:
    # search 节点之后有三条可能路径: rewrite / fallback / answer。
    route = state.get("route")
    if route == "rewrite":
        return "rewrite"
    if route == "fallback":
        return "fallback"
    return "answer"


ROUTE_FROM_ANSWER = {"answer": END, "fallback": END, "clarify": END}
