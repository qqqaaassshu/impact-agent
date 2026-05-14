from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from impact_agent.models.history import AssessmentRecord
from impact_agent.models.llm import ClarificationNeeded
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
    raw_input = {
        "source": {"type": "local", "root_path": payload.resolved_root_path(), "include_uncommitted": False},
        "repo_path": payload.resolved_repo_path(),
        "requirement": payload.requirement,
        "change_type": payload.change_type,
        "file_types": payload.resolved_file_types(),
    }
    result = service.submit(raw_input)
    if isinstance(result, ClarificationNeeded):
        return {"kind": "clarification", **result.model_dump()}
    return {"kind": "report", **result.model_dump()}
