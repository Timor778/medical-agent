from __future__ import annotations

from typing import Any, Iterable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from medical_agent.config import get_settings
from medical_agent.prompts import (
    ANSWER_PROMPT,
    FALLBACK_PROMPT,
    REWRITE_QUERY_PROMPT,
    SYSTEM_ROLE,
    UNDERSTAND_PROMPT,
)
from medical_agent.schemas import QueryRewriteResult, UnderstandResult
from medical_agent.services.llm_service import invoke_text, parse_json_object, stream_text
from medical_agent.services.retrieval_service import LocalRagTool, RetrievalBundle, WebSearchTool

from .state import DebugTrace, MedicalAgentState


local_rag_tool = LocalRagTool()
web_search_tool = WebSearchTool()
settings = get_settings()


def _append_debug(
    state: MedicalAgentState,
    *,
    node: str,
    summary: str,
    edge: str,
    next_node: str,
    reset: bool = False,
) -> list[DebugTrace]:
    previous = [] if reset else list(state.get("debug_steps", []))
    previous.append(
        {
            "index": len(previous) + 1,
            "node": node,
            "summary": summary,
            "edge": edge,
            "next_node": next_node,
        }
    )
    return previous


def _extract_user_query(state: MedicalAgentState) -> str:
    last_message = state["messages"][-1]
    content = getattr(last_message, "content", "")
    if isinstance(content, str):
        return content
    return str(content)


def _format_bundle(bundle: RetrievalBundle) -> str:
    return f"检索摘要：{bundle.summary}\n\n{bundle.snippets}".strip()


def build_answer_messages(state: MedicalAgentState, *, fallback: bool = False) -> list[BaseMessage]:
    prompt = FALLBACK_PROMPT if fallback else ANSWER_PROMPT
    source_text = "\n".join(state.get("sources", [])) or "无"
    return [
        SystemMessage(content=SYSTEM_ROLE),
        SystemMessage(content=prompt),
        HumanMessage(
            content=(
                f"用户问题：{state['user_query']}\n"
                f"意图总结：{state['intent_summary']}\n"
                f"风险等级：{state['triage_level']}\n"
                f"检索模式：{state.get('retrieval_mode', '-')}\n"
                f"搜索词：{state.get('search_query', '-')}\n"
                f"检索结果：\n{state.get('search_results', '无')}\n\n"
                f"来源列表：\n{source_text}"
            )
        ),
    ]


def stream_final_answer(state: MedicalAgentState, *, fallback: bool = False) -> Iterable[str]:
    return stream_text(build_answer_messages(state, fallback=fallback))


def _finalize_answer_state(state: MedicalAgentState, answer: str, *, fallback: bool = False) -> dict[str, Any]:
    node = "fallback" if fallback else "answer"
    summary = "联网不可用，输出保守医疗建议" if fallback else "基于检索结果生成最终医疗回答"
    route = "fallback" if fallback else "completed"
    return {
        "final_answer": answer,
        "route": route,
        "debug_steps": _append_debug(
            state,
            node=node,
            summary=summary,
            edge="to_end",
            next_node="end",
        ),
        "messages": [AIMessage(content=answer)],
    }


def understand_node(state: MedicalAgentState) -> dict[str, Any]:
    user_query = _extract_user_query(state)
    response = invoke_text(
        [
            SystemMessage(content=SYSTEM_ROLE),
            SystemMessage(content=UNDERSTAND_PROMPT),
            HumanMessage(content=user_query),
        ]
    )
    parsed = UnderstandResult.model_validate(parse_json_object(response))
    next_node = "clarify" if parsed.needs_clarification else "rag"
    return {
        "user_query": user_query,
        "intent_summary": parsed.intent_summary,
        "search_query": parsed.search_query,
        "triage_level": parsed.triage_level,
        "needs_clarification": parsed.needs_clarification,
        "clarification_question": parsed.clarification_question,
        "route": next_node,
        "search_attempts": state.get("search_attempts", 0),
        "debug_steps": _append_debug(
            state,
            node="understand",
            summary=f"识别意图并完成分诊，风险等级 {parsed.triage_level}",
            edge=f"route={next_node}",
            next_node=next_node,
            reset=True,
        ),
    }


def clarify_node(state: MedicalAgentState) -> dict[str, Any]:
    question = state.get("clarification_question") or "请补充更具体的症状、持续时间和适用人群信息。"
    return {
        "final_answer": question,
        "route": "clarify",
        "debug_steps": _append_debug(
            state,
            node="clarify",
            summary="信息不足，向用户发起补充提问",
            edge="to_end",
            next_node="end",
        ),
        "messages": [AIMessage(content=question)],
    }


def rag_node(state: MedicalAgentState) -> dict[str, Any]:
    bundle = local_rag_tool.retrieve(state["search_query"])
    next_node = "answer" if bundle.success else "search"
    summary = (
        f"本地 RAG 命中 {bundle.hit_count} 条资料，优先使用本地知识回答"
        if bundle.success
        else "本地 RAG 未命中足够资料，转入联网检索"
    )
    return {
        "search_results": _format_bundle(bundle),
        "sources": bundle.sources,
        "retrieval_mode": bundle.mode,
        "retrieval_hits": bundle.hit_count,
        "route": next_node,
        "debug_steps": _append_debug(
            state,
            node="rag",
            summary=summary,
            edge=f"route={next_node}",
            next_node=next_node,
        ),
    }


def search_node(state: MedicalAgentState) -> dict[str, Any]:
    attempts = state.get("search_attempts", 0) + 1
    bundle = web_search_tool.retrieve(state["search_query"])

    if bundle.success:
        next_node = "answer"
        summary = f"第 {attempts} 次联网检索完成，命中 {bundle.hit_count} 个来源"
    else:
        max_attempts = settings.max_search_attempts
        next_node = "rewrite" if attempts < max_attempts else "fallback"
        summary = f"第 {attempts} 次联网检索结果不足，下一步 {next_node}"

    return {
        "search_attempts": attempts,
        "search_results": _format_bundle(bundle),
        "sources": bundle.sources,
        "retrieval_mode": bundle.mode,
        "retrieval_hits": bundle.hit_count,
        "route": next_node,
        "debug_steps": _append_debug(
            state,
            node="search",
            summary=summary,
            edge=f"route={next_node}",
            next_node=next_node,
        ),
    }


def rewrite_query_node(state: MedicalAgentState) -> dict[str, Any]:
    response = invoke_text(
        [
            SystemMessage(content=SYSTEM_ROLE),
            SystemMessage(content=REWRITE_QUERY_PROMPT),
            HumanMessage(
                content=(
                    f"用户问题：{state['user_query']}\n"
                    f"当前意图总结：{state['intent_summary']}\n"
                    f"上一轮搜索词：{state['search_query']}\n"
                    f"上一轮检索结果：{state.get('search_results', '无')}"
                )
            ),
        ]
    )
    parsed = QueryRewriteResult.model_validate(parse_json_object(response))
    return {
        "search_query": parsed.search_query,
        "search_rewrite_reason": parsed.reason,
        "route": "search",
        "debug_steps": _append_debug(
            state,
            node="rewrite",
            summary=f"已重写搜索词：{parsed.reason}",
            edge="retry_search",
            next_node="search",
        ),
    }


def answer_node(state: MedicalAgentState) -> dict[str, Any]:
    answer = "".join(stream_final_answer(state))
    return _finalize_answer_state(state, answer, fallback=False)


def fallback_answer_node(state: MedicalAgentState) -> dict[str, Any]:
    answer = "".join(stream_final_answer(state, fallback=True))
    return _finalize_answer_state(state, answer, fallback=True)
