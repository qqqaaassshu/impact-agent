from pydantic import BaseModel, Field


class AssessmentState(BaseModel):
    request: dict = Field(default_factory=dict)
    source_snapshot: dict = Field(default_factory=dict)
    project_profile: dict = Field(default_factory=dict)
    history_references: list[dict] = Field(default_factory=list)
    searched_clues: list[dict] = Field(default_factory=list)
    pending_clues: list[dict] = Field(default_factory=list)
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
    search_round: int = 0
    max_search_rounds: int = 3
    llm_decisions: list[dict] = Field(default_factory=list)
    next_action: str | None = None
    trace: list[dict] = Field(default_factory=list)
