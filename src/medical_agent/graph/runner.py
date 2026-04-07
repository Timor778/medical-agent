from __future__ import annotations

import time
from collections.abc import Iterable

from langchain_core.messages import HumanMessage

from medical_agent.schemas import ConsultationResponse, DebugStep
from medical_agent.services.llm_service import current_llm_profile
from medical_agent.services.session_store import get_session_store

from .nodes import (
    _finalize_answer_state,
    answer_node,
    clarify_node,
    fallback_answer_node,
    rag_node,
    rewrite_query_node,
    search_node,
    stream_final_answer,
    understand_node,
)
from .routing import route_after_rag, route_after_search, route_after_understand
from .state import MedicalAgentState


session_store = get_session_store()


def _build_runtime_mermaid(debug_steps: list[dict]) -> str:
    lines = ["flowchart LR", "    start_node([开始])", "    finish_node([结束])"]
    node_ids = []

    for step in debug_steps:
        node_id = f"node_{step['index']}_{step['node']}"
        node_ids.append(node_id)
        label = f"{step['node']}<br/>{step['summary']}"
        lines.append(f'    {node_id}["{label}"]')

    if not node_ids:
        lines.append("    start_node --> finish_node")
        return "\n".join(lines)

    lines.append(f"    start_node --> {node_ids[0]}")
    for index, step in enumerate(debug_steps):
        current_id = node_ids[index]
        if index < len(debug_steps) - 1:
            next_id = node_ids[index + 1]
            lines.append(f"    {current_id} -->|{step['edge']}| {next_id}")
        else:
            lines.append(f"    {current_id} -->|{step['edge']}| finish_node")
    return "\n".join(lines)


def _error_event(*, code: str, message: str, stage: str) -> dict:
    return {
        "event": "error",
        "data": {
            "code": code,
            "message": message,
            "stage": stage,
        },
    }


def _get_history(thread_id: str) -> list:
    return session_store.load_history(thread_id)


def _save_history(thread_id: str, question: str, answer: str) -> None:
    session_store.append_exchange(thread_id, question, answer)


def _initial_state(question: str, thread_id: str) -> MedicalAgentState:
    return {
        "messages": _get_history(thread_id) + [HumanMessage(content=question)],
        "search_attempts": 0,
        "sources": [],
        "debug_steps": [],
    }


def _run_pre_answer(state: MedicalAgentState) -> tuple[MedicalAgentState, str]:
    state.update(understand_node(state))
    route = route_after_understand(state)
    if route == "clarify":
        state.update(clarify_node(state))
        return state, "clarify"

    state.update(rag_node(state))
    route = route_after_rag(state)
    if route == "answer":
        return state, "answer"

    while True:
        state.update(search_node(state))
        route = route_after_search(state)
        if route == "rewrite":
            state.update(rewrite_query_node(state))
            continue
        return state, route


def _build_response(state: MedicalAgentState, question: str, elapsed_ms: int) -> ConsultationResponse:
    debug_steps = [DebugStep.model_validate(step) for step in state.get("debug_steps", [])]
    llm_profile = current_llm_profile()
    return ConsultationResponse(
        question=question,
        answer=state.get("final_answer", ""),
        triage_level=state.get("triage_level", "中"),
        intent_summary=state.get("intent_summary", ""),
        rewritten_query=state.get("search_query", ""),
        sources=state.get("sources", []),
        search_attempts=state.get("search_attempts", 0),
        route=state.get("route", "completed"),
        debug_steps=debug_steps,
        debug_mermaid=_build_runtime_mermaid([step.model_dump() for step in debug_steps]),
        elapsed_ms=elapsed_ms,
        retrieval_mode=state.get("retrieval_mode", "-"),
        llm_provider=llm_profile["provider"],
        llm_model_id=llm_profile["model_id"],
    )


def run_consultation(question: str, thread_id: str) -> ConsultationResponse:
    started_at = time.perf_counter()
    state = _initial_state(question, thread_id)
    state, terminal = _run_pre_answer(state)

    if terminal == "clarify":
        pass
    elif terminal == "fallback":
        state.update(fallback_answer_node(state))
    else:
        state.update(answer_node(state))

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    _save_history(thread_id, question, state.get("final_answer", ""))
    return _build_response(state, question, elapsed_ms)


def stream_consultation(question: str, thread_id: str) -> Iterable[dict]:
    started_at = time.perf_counter()
    chunks: list[str] = []
    state: MedicalAgentState | None = None

    try:
        state = _initial_state(question, thread_id)
        state, terminal = _run_pre_answer(state)
        yield {"event": "status", "data": {"message": "正在分析问题并执行问诊流程..."}}

        if terminal == "clarify":
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            _save_history(thread_id, question, state.get("final_answer", ""))
            yield {"event": "done", "data": _build_response(state, question, elapsed_ms).model_dump()}
            return

        fallback = terminal == "fallback"
        for token in stream_final_answer(state, fallback=fallback):
            chunks.append(token)
            yield {"event": "answer_chunk", "data": {"chunk": token}}

        final_answer = "".join(chunks)
        state.update(_finalize_answer_state(state, final_answer, fallback=fallback))
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        _save_history(thread_id, question, final_answer)
        yield {"event": "done", "data": _build_response(state, question, elapsed_ms).model_dump()}
    except Exception as exc:
        stage = "stream_answer" if chunks else "graph_execution"
        if state is not None and chunks:
            state["final_answer"] = "".join(chunks)
        yield _error_event(
            code="STREAM_FAILED",
            message=f"问诊过程中出现异常：{exc}",
            stage=stage,
        )
