from collections.abc import Iterable
from pathlib import Path

from impact_agent.indexer.filters import should_index_file


def iter_code_files(repo_root: str | Path, include_paths: list[str] | None = None) -> Iterable[Path]:
    root = Path(repo_root)
    scan_roots = _scan_roots(root, include_paths or [])
    for scan_root in scan_roots:
        for path in scan_root.rglob("*"):
            if path.is_file() and should_index_file(path):
                yield path


def _scan_roots(repo_root: Path, include_paths: list[str]) -> list[Path]:
    if not include_paths:
        return [repo_root]

    roots: list[Path] = []
    for include_path in include_paths:
        candidate = (repo_root / include_path).resolve()
        if candidate.exists() and candidate.is_dir():
            roots.append(candidate)
    return roots or [repo_root]
