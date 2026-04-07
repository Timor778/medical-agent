from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import answer_node, clarify_node, fallback_answer_node, rewrite_query_node, search_node, understand_node
from .routing import route_after_search, route_after_understand
from .state import MedicalAgentState


def create_medical_agent():
    # StateGraph 可以理解成“带共享状态的流程图”。
    # 每个节点读写 MedicalAgentState，边决定下一步流向。
    workflow = StateGraph(MedicalAgentState)
    workflow.add_node("understand", understand_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("search", search_node)
    workflow.add_node("rewrite", rewrite_query_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("fallback", fallback_answer_node)

    workflow.add_edge(START, "understand")
    # 先理解用户问题，再决定是继续搜索还是先追问补充信息。
    workflow.add_conditional_edges(
        "understand",
        route_after_understand,
        {"clarify": "clarify", "search": "search"},
    )
    # 搜索之后可能直接回答，也可能改写搜索词重试，或者走保守兜底回答。
    workflow.add_conditional_edges(
        "search",
        route_after_search,
        {"rewrite": "rewrite", "fallback": "fallback", "answer": "answer"},
    )
    workflow.add_edge("rewrite", "search")
    workflow.add_edge("clarify", END)
    workflow.add_edge("answer", END)
    workflow.add_edge("fallback", END)

    # 这里用内存版 checkpointer 保存线程状态，适合本地调试和演示。
    return workflow.compile(checkpointer=InMemorySaver())
