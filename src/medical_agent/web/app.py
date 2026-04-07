from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from langchain_core.messages import HumanMessage

from medical_agent.graph.builder import create_medical_agent
from medical_agent.schemas import ConsultationRequest, ConsultationResponse, DebugStep


BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
app = FastAPI(title="Medical Consultation Agent", version="1.0.0")
# 服务启动时就把图编译好，后续请求直接复用同一个 graph_app。
graph_app = create_medical_agent()


def _build_runtime_mermaid(debug_steps: list[dict]) -> str:
    # 把本次真实执行过的节点轨迹拼成 Mermaid 文本，给前端调试展示用。
    lines = ["flowchart LR", "    start_node([开始])"]
    previous = "start_node"
    for step in debug_steps:
        node_id = f"n{step['index']}"
        label = f"{step['node']}<br/>{step['summary']}"
        edge = str(step["edge"]).replace('"', "'")
        lines.append(f'    {node_id}["{label}"]')
        lines.append(f"    {previous} -->|{edge}| {node_id}")
        previous = node_id
    lines.append("    finish_node([结束])")
    lines.append(f"    {previous} --> finish_node")
    return "\n".join(lines)


@app.get("/", response_class=FileResponse)
def read_index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/graph", response_class=PlainTextResponse)
def graph_mermaid() -> str:
    return graph_app.get_graph().draw_mermaid()


@app.post("/api/consult", response_model=ConsultationResponse)
def consult(request: ConsultationRequest) -> ConsultationResponse:
    # graph_app.invoke 会按照 builder.py 里定义的图完整跑一遍。
    # thread_id 会交给 checkpointer，用来区分不同会话线程。
    result = graph_app.invoke(
        {"messages": [HumanMessage(content=request.question)]},
        config={"configurable": {"thread_id": request.thread_id}},
    )
    # LangGraph 返回的是状态字典，这里再整理成稳定的 API 响应模型。
    debug_steps = [DebugStep.model_validate(step) for step in result.get("debug_steps", [])]
    return ConsultationResponse(
        question=request.question,
        answer=result.get("final_answer", ""),
        triage_level=result.get("triage_level", "中"),
        intent_summary=result.get("intent_summary", ""),
        rewritten_query=result.get("search_query", ""),
        sources=result.get("sources", []),
        search_attempts=result.get("search_attempts", 0),
        route=result.get("route", "completed"),
        debug_steps=debug_steps,
        debug_mermaid=_build_runtime_mermaid([step.model_dump() for step in debug_steps]),
    )
