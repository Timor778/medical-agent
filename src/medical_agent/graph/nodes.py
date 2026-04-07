from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from medical_agent.prompts import (
    ANSWER_PROMPT,
    FALLBACK_PROMPT,
    REWRITE_QUERY_PROMPT,
    SYSTEM_ROLE,
    UNDERSTAND_PROMPT,
)
from medical_agent.schemas import QueryRewriteResult, UnderstandResult
from medical_agent.services.llm_service import build_llm, extract_text, parse_json_object
from medical_agent.services.search_service import MedicalSearchService

from .state import DebugTrace, MedicalAgentState


llm = build_llm()
search_service = MedicalSearchService()


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


def understand_node(state: MedicalAgentState) -> dict[str, Any]:
    user_query = extract_text(state["messages"][-1])
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_ROLE),
            SystemMessage(content=UNDERSTAND_PROMPT),
            HumanMessage(content=user_query),
        ]
    )
    parsed = UnderstandResult.model_validate(parse_json_object(extract_text(response)))
    next_node = "clarify" if parsed.needs_clarification else "search"
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
            summary=f"识别意图并完成分诊，风险等级为 {parsed.triage_level}",
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


def search_node(state: MedicalAgentState) -> dict[str, Any]:
    attempts = state.get("search_attempts", 0) + 1
    try:
        bundle = search_service.search(state["search_query"])
        next_node = "answer"
        summary = f"第 {attempts} 次联网搜索完成，命中 {len(bundle.sources)} 个来源"
        if not bundle.sources and attempts < 2:
            next_node = "rewrite"
            summary = f"第 {attempts} 次联网搜索结果不足，准备重写查询词"
        return {
            "search_attempts": attempts,
            "search_results": f"搜索摘要：{bundle.summary}\n\n{bundle.snippets}".strip(),
            "sources": bundle.sources,
            "route": next_node,
            "debug_steps": _append_debug(
                state,
                node="search",
                summary=summary,
                edge=f"route={next_node}",
                next_node=next_node,
            ),
        }
    except Exception as exc:
        next_node = "rewrite" if attempts < 2 else "fallback"
        return {
            "search_attempts": attempts,
            "search_results": f"搜索失败：{exc}",
            "sources": [],
            "route": next_node,
            "debug_steps": _append_debug(
                state,
                node="search",
                summary=f"第 {attempts} 次搜索异常，错误为：{exc}",
                edge=f"route={next_node}",
                next_node=next_node,
            ),
        }


def rewrite_query_node(state: MedicalAgentState) -> dict[str, Any]:
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_ROLE),
            SystemMessage(content=REWRITE_QUERY_PROMPT),
            HumanMessage(
                content=(
                    f"用户问题：{state['user_query']}\n"
                    f"当前意图总结：{state['intent_summary']}\n"
                    f"上一轮搜索词：{state['search_query']}\n"
                    f"上一轮搜索结果：{state['search_results']}"
                )
            ),
        ]
    )
    parsed = QueryRewriteResult.model_validate(parse_json_object(extract_text(response)))
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
    source_text = "\n".join(state.get("sources", [])) or "无"
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_ROLE),
            SystemMessage(content=ANSWER_PROMPT),
            HumanMessage(
                content=(
                    f"用户问题：{state['user_query']}\n"
                    f"意图总结：{state['intent_summary']}\n"
                    f"风险等级：{state['triage_level']}\n"
                    f"搜索词：{state['search_query']}\n"
                    f"搜索结果：\n{state['search_results']}\n\n"
                    f"来源列表：\n{source_text}"
                )
            ),
        ]
    )
    answer = extract_text(response)
    return {
        "final_answer": answer,
        "route": "completed",
        "debug_steps": _append_debug(
            state,
            node="answer",
            summary="基于搜索结果生成最终医疗回答",
            edge="to_end",
            next_node="end",
        ),
        "messages": [AIMessage(content=answer)],
    }


def fallback_answer_node(state: MedicalAgentState) -> dict[str, Any]:
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_ROLE),
            SystemMessage(content=FALLBACK_PROMPT),
            HumanMessage(
                content=(
                    f"用户问题：{state['user_query']}\n"
                    f"意图总结：{state['intent_summary']}\n"
                    f"风险等级：{state['triage_level']}\n"
                    f"搜索情况：{state['search_results']}"
                )
            ),
        ]
    )
    answer = extract_text(response)
    return {
        "final_answer": answer,
        "route": "fallback",
        "debug_steps": _append_debug(
            state,
            node="fallback",
            summary="搜索不可用，回退到保守医疗建议",
            edge="to_end",
            next_node="end",
        ),
        "messages": [AIMessage(content=answer)],
    }
