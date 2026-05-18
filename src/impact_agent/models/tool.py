from pydantic import BaseModel, Field


class ToolHit(BaseModel):
    file: str
    symbol: str | None = None
    kind: str
    line_start: int | None = None
    line_end: int | None = None
    content: str = ""
    metadata: dict = Field(default_factory=dict)
    score: float | None = None
