from pydantic import BaseModel, Field


class SourceSnapshot(BaseModel):
    type: str
    details: dict = Field(default_factory=dict)


class Evidence(BaseModel):
    evidence_id: str
    source_type: str
    clue_category: str
    decision: str
    reason: str
    confidence: str
    file_path: str | None = None
    line_no: int | None = None
    code: str | None = None
