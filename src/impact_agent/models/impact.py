from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    file: str
    line_start: int | None = None
    line_end: int | None = None
    snippet: str = ""
    reason: str


class ImpactItem(BaseModel):
    file: str
    symbol: str | None = None
    impact_type: str
    description: str
    reason: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"
    needs_review: bool = True


class ImpactReport(BaseModel):
    request_id: str
    summary: str = ""
    repo: dict = Field(default_factory=dict)
    affected: list[ImpactItem] = Field(default_factory=list)
    uncertain: list[ImpactItem] = Field(default_factory=list)
    excluded: list[ImpactItem] = Field(default_factory=list)
    tool_trace: list[dict] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    overall_confidence: Literal["low", "medium", "high"] = "low"
