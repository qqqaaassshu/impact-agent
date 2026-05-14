from pydantic import BaseModel, Field

from impact_agent.models.report import AssessmentReport


class AssessmentHistoryItem(BaseModel):
    assessment_id: str
    created_at: str
    requirement: str
    change_type: str
    risk_level: str
    overall_confidence: str
    needs_human_review: bool
    conclusion: str
    project_root: str | None = None
    repo_path: str | None = None
    module: str | None = None


class AssessmentRecord(BaseModel):
    assessment_id: str
    created_at: str
    request: dict = Field(default_factory=dict)
    history_item: AssessmentHistoryItem
    report: AssessmentReport
