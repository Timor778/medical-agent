from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class DebugTrace(TypedDict):
    index: int
    node: str
    summary: str
    edge: str
    next_node: str


class MedicalAgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    intent_summary: str
    search_query: str
    triage_level: Literal["低", "中", "高", "紧急"]
    needs_clarification: bool
    clarification_question: str
    search_results: str
    sources: list[str]
    final_answer: str
    route: str
    search_attempts: int
    search_rewrite_reason: str
    debug_steps: list[DebugTrace]
