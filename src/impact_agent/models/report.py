from pydantic import BaseModel, Field

from impact_agent.models.evidence import Evidence


class Summary(BaseModel):
    requirement: str
    change_type: str
    risk_level: str
    overall_confidence: str
    needs_human_review: bool
    conclusion: str
    stop_reason: str | None = None
    source_snapshot: dict = Field(default_factory=dict)
    assessment_id: str | None = None
    created_at: str | None = None


class AssessmentReport(BaseModel):
    summary: Summary
    confirmed_affected: list[dict] = Field(default_factory=list)
    uncertain_matches: list[dict] = Field(default_factory=list)
    excluded_matches: list[dict] = Field(default_factory=list)
    coverage: dict = Field(default_factory=dict)
    evidence_chain: dict = Field(default_factory=dict)
    knowledge_used: dict = Field(default_factory=dict)
    next_action: str | None = None
    trace: list[dict] = Field(default_factory=list)
