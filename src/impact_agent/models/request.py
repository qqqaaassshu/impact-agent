from pydantic import BaseModel, Field, field_validator, model_validator

from impact_agent.config import DEFAULT_FILE_TYPES
from impact_agent.models.common import ChangeType, SourceType


class ChangeScope(BaseModel):
    module: str | None = None
    page: str | None = None
    action: str | None = None
    target_entity: str | None = None
    entity_kind: str | None = None
    old_name: str | None = None
    new_name: str | None = None
    include_new_name_references: bool = False
    check_permissions: bool = True
    check_refresh_flow: bool = True


class SourceConfig(BaseModel):
    type: SourceType
    root_path: str | None = None
    include_uncommitted: bool = False
    project_id: str | None = None
    ref: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "SourceConfig":
        if self.type == "local" and not self.root_path:
            raise ValueError("local source requires root_path")
        if self.type == "gitlab" and not self.project_id:
            raise ValueError("gitlab source requires project_id")
        return self


class AssessmentRequest(BaseModel):
    source: SourceConfig
    repo_path: str | None = None
    requirement: str
    change_type: ChangeType
    change_scope: ChangeScope
    file_types: list[str] = Field(default_factory=lambda: list(DEFAULT_FILE_TYPES))

    @field_validator("file_types")
    @classmethod
    def normalize_file_types(cls, value: list[str]) -> list[str]:
        if not value:
            return list(DEFAULT_FILE_TYPES)
        normalized: list[str] = []
        for item in value:
            suffix = item if item.startswith(".") else f".{item}"
            if suffix not in normalized:
                normalized.append(suffix)
        return normalized

    @model_validator(mode="after")
    def validate_change_scope(self) -> "AssessmentRequest":
        if self.change_type == "field_rename":
            if not self.change_scope.old_name or not self.change_scope.new_name:
                raise ValueError("field_rename requires old_name and new_name")
        return self
