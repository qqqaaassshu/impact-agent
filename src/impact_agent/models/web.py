from impact_agent.config import DEFAULT_FILE_TYPES, DEFAULT_REPO_PATH, DEFAULT_ROOT_PATH
from pydantic import BaseModel, Field


class WebAssessmentInput(BaseModel):
    requirement: str
    root_path: str | None = None
    repo_path: str | None = None
    change_type: str | None = "field_rename"
    file_types: list[str] = Field(default_factory=list)

    def resolved_root_path(self) -> str:
        return self.root_path or DEFAULT_ROOT_PATH

    def resolved_repo_path(self) -> str:
        return self.repo_path or DEFAULT_REPO_PATH

    def resolved_file_types(self) -> list[str]:
        return self.file_types or list(DEFAULT_FILE_TYPES)
