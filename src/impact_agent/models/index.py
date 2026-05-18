from pathlib import Path

from pydantic import BaseModel, Field


class IndexBuildRequest(BaseModel):
    repo_root: str
    include_paths: list[str] = Field(default_factory=list)
    incremental: bool = True


class IndexedFile(BaseModel):
    file: str
    language: str
    size_bytes: int
    file_hash: str


class IndexBuildResult(BaseModel):
    repo_root: str
    indexed_files: int
    skipped_files: int = 0
    status: str = "ready"


class IndexStatus(BaseModel):
    status: str
    repo_root: str | None = None
    indexed_files: int = 0
    last_built_at: str | None = None


def language_for_path(path: str | Path) -> str:
    suffix = Path(path).suffix
    return {
        ".js": "javascript",
        ".jsx": "javascriptreact",
        ".ts": "typescript",
        ".tsx": "typescriptreact",
        ".vue": "vue",
        ".json": "json",
    }.get(suffix, "unknown")
