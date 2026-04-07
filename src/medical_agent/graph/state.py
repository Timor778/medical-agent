from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class DebugTrace(TypedDict):
    # 单步调试轨迹，供前端可视化“本次实际走过的节点”。
    index: int
    node: str
    summary: str
    edge: str
    next_node: str


class MedicalAgentState(TypedDict, total=False):
    # LangGraph 的状态对象，本质上就是节点间共享的数据字典。
    # total=False 表示字段可以被各节点逐步补全，而不是一次性全部给齐。
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
