from pydantic import BaseModel, Field


class AssessmentState(BaseModel):
    request: dict = Field(default_factory=dict)
    source_snapshot: dict = Field(default_factory=dict)
    project_profile: dict = Field(default_factory=dict)
    history_references: list[dict] = Field(default_factory=list)
    searched_clues: list[dict] = Field(default_factory=list)
    read_files: dict[str, str] = Field(default_factory=dict)
    confirmed_affected: list[dict] = Field(default_factory=list)
    uncertain_matches: list[dict] = Field(default_factory=list)
    excluded_matches: list[dict] = Field(default_factory=list)
    relations: list[dict] = Field(default_factory=list)
    coverage: dict = Field(default_factory=dict)
    evidence_chain: dict = Field(default_factory=dict)
    knowledge_used: dict = Field(default_factory=dict)
    risk: dict = Field(default_factory=dict)
    confidence: dict = Field(default_factory=dict)
    next_action: str | None = None
    trace: list[str] = Field(default_factory=list)
