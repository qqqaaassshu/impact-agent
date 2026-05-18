from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    repo_root: str | None = None
    requirement: str
    limit: int | None = None
