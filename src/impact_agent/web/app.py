import json
from queue import Empty, Queue
from threading import Thread

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from impact_agent.models.history import AssessmentRecord
from impact_agent.models.llm import ClarificationNeeded, UnsupportedRequest
from impact_agent.models.report import AssessmentReport
from impact_agent.models.web import WebAssessmentInput
from impact_agent.services.assessment_service import AssessmentService

app = FastAPI(title="impact-agent web api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = AssessmentService()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/assessments")
def list_assessments(limit: int = 50):
    return [item.model_dump() for item in service.list_history(limit=limit)]


@app.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: str):
    record = service.get_history_detail(assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    return record.model_dump()


@app.post("/api/assessments")
def create_assessment(payload: WebAssessmentInput):
    raw_input = _build_raw_input(payload)
    try:
        result = service.submit(raw_input)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=_friendly_error_message(exc)) from exc
    if isinstance(result, ClarificationNeeded):
        return {"kind": "clarification", **result.model_dump()}
    if isinstance(result, UnsupportedRequest):
        return {"kind": "unsupported", **result.model_dump()}
    return {"kind": "report", **result.model_dump()}


@app.post("/api/assessments/stream")
def stream_assessment(payload: WebAssessmentInput):
    raw_input = _build_raw_input(payload)

    def event_stream():
        queue: Queue[tuple[str, dict]] = Queue()
        yield _sse("progress", {"stage": "request_received", "title": "接收请求", "message": "已收到分析请求"})

        def collect_progress(event: dict) -> None:
            queue.put(("progress", event))

        def run_analysis() -> None:
            try:
                result = service.submit(raw_input, progress_callback=collect_progress)
                if isinstance(result, ClarificationNeeded):
                    queue.put(("result", {"kind": "clarification", **result.model_dump()}))
                elif isinstance(result, UnsupportedRequest):
                    queue.put(("result", {"kind": "unsupported", **result.model_dump()}))
                else:
                    queue.put(("result", {"kind": "report", **result.model_dump()}))
                queue.put(("done", {"title": "分析完成", "message": "已生成分析结果"}))
            except Exception as exc:
                queue.put(("error", {"message": _friendly_error_message(exc)}))

        worker = Thread(target=run_analysis, daemon=True)
        worker.start()

        while True:
            try:
                event, data = queue.get(timeout=15)
            except Empty:
                yield _sse("heartbeat", {"message": "分析仍在进行"})
                continue
            yield _sse(event, data)
            if event in {"done", "error"}:
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _build_raw_input(payload: WebAssessmentInput) -> dict:
    repo_path = payload.resolved_repo_path()
    return {
        "source": {"type": "local", "root_path": payload.resolved_root_path(), "include_uncommitted": False},
        "repo_path": repo_path or None,
        "requirement": payload.requirement,
        "change_type": payload.change_type,
        "file_types": payload.resolved_file_types(),
    }


def _sse(event: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _friendly_error_message(exc: Exception) -> str:
    message = str(exc)
    if "LLM_MODEL" in message or "LLM_BASE_URL" in message or "LLM_API_KEY" in message:
        return message
    if "API key" in message or "api_key" in message.lower():
        return "大模型密钥配置有误，请检查 LLM_API_KEY。"
    if "Connection" in message or "connect" in message.lower() or "timeout" in message.lower():
        return "大模型服务连接失败，请检查网络、LLM_BASE_URL 和模型服务状态。"
    return f"分析失败：{message}"
