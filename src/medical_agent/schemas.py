from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TriageLevel = Literal["低", "中", "高", "紧急"]


class DebugStep(BaseModel):
    index: int
    node: str
    summary: str
    edge: str
    next_node: str


class ConsultationRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户输入的医疗问题")
    thread_id: str = Field(default="default-thread", description="会话线程 ID")


class ConsultationResponse(BaseModel):
    question: str
    answer: str
    triage_level: TriageLevel
    intent_summary: str
    rewritten_query: str
    sources: list[str]
    search_attempts: int
    route: str
    debug_steps: list[DebugStep]
    debug_mermaid: str


class UnderstandResult(BaseModel):
    intent_summary: str
    search_query: str
    triage_level: TriageLevel
    needs_clarification: bool = False
    clarification_question: str = ""


class QueryRewriteResult(BaseModel):
    search_query: str
    reason: str
