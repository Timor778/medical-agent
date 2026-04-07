from __future__ import annotations

from .state import MedicalAgentState


def route_after_understand(state: MedicalAgentState) -> str:
    return "clarify" if state.get("route") == "clarify" else "rag"


def route_after_rag(state: MedicalAgentState) -> str:
    return "answer" if state.get("route") == "answer" else "search"


def route_after_search(state: MedicalAgentState) -> str:
    route = state.get("route")
    if route == "rewrite":
        return "rewrite"
    if route == "fallback":
        return "fallback"
    return "answer"
