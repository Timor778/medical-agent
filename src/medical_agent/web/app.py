from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from medical_agent.graph.builder import create_medical_agent
from medical_agent.graph.runner import run_consultation, stream_consultation
from medical_agent.schemas import ConsultationRequest, ConsultationResponse


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = BASE_DIR / "index.html"

app = FastAPI(title="Medical Consultation Agent", version="1.0.0")
graph_app = create_medical_agent()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/", response_class=FileResponse)
def read_index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico")
def favicon() -> Response:
    # 浏览器会默认请求 /favicon.ico。这里返回 204，避免启动后日志里一直出现 404。
    return Response(status_code=204)


@app.get("/api/graph", response_class=PlainTextResponse)
def graph_mermaid() -> str:
    return graph_app.get_graph().draw_mermaid()


@app.post("/api/consult", response_model=ConsultationResponse)
def consult(request: ConsultationRequest) -> ConsultationResponse:
    return run_consultation(request.question, request.thread_id)


@app.post("/api/consult/stream")
def consult_stream(request: ConsultationRequest) -> StreamingResponse:
    def event_stream():
        for item in stream_consultation(request.question, request.thread_id):
            yield _sse(item["event"], item["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
