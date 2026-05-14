from pydantic import BaseModel, Field

from impact_agent.models.common import ChangeType


class ClarificationNeeded(BaseModel):
    needs_clarification: bool = True
    questions: list[str] = Field(default_factory=list)


class IntakeParseResult(BaseModel):
    change_type: ChangeType | None = None
    old_name: str | None = None
    new_name: str | None = None
    module: str | None = None
    repo_path: str | None = None
    entity_kind: str | None = None
    requirement: str | None = None
    needs_clarification: bool = False
    questions: list[str] = Field(default_factory=list)


class ClueExpansionResult(BaseModel):
    clues: list[str] = Field(default_factory=list)
    reasoning: str | None = None


class SearchDecisionResult(BaseModel):
    action: str
    next_keywords: list[str] = Field(default_factory=list)
    reasoning: str | None = None


class SemanticMatchDecision(BaseModel):
    is_affected: bool | None = None
    reason: str | None = None
