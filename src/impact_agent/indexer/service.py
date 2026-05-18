import hashlib
from pathlib import Path

from impact_agent.config import Settings
from impact_agent.indexer.scanner import iter_code_files
from impact_agent.indexer.store import IndexStore
from impact_agent.indexer.structure_extractor import extract_structure
from impact_agent.indexer.symbol_extractor import extract_symbols
from impact_agent.indexer.vector_store import ChromaVectorStore
from impact_agent.models.index import IndexBuildResult, IndexedFile, language_for_path
from impact_agent.models.tool import ToolHit


def build_index(
    repo_root: str | Path,
    settings: Settings,
    include_paths: list[str] | None = None,
) -> IndexBuildResult:
    root = Path(repo_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository root does not exist or is not a directory: {root}")

    indexed_files: list[IndexedFile] = []
    chunks: list[ToolHit] = []
    for path in iter_code_files(root, include_paths=include_paths):
        relative_path = path.relative_to(root).as_posix()
        language = language_for_path(path)
        indexed_files.append(
            IndexedFile(
                file=relative_path,
                language=language,
                size_bytes=path.stat().st_size,
                file_hash=_file_hash(path),
            )
        )
        content = path.read_text(encoding="utf-8", errors="ignore")
        structure = extract_structure(content)
        chunks.append(_file_chunk(path, relative_path, language, content, structure))
        chunks.extend(_symbol_chunks(relative_path, language, content))

    store = IndexStore(Path(settings.data_dir) / "index.sqlite")
    store.replace_index(root, indexed_files, chunks)
    ChromaVectorStore(settings).replace_chunks(root, chunks)

    return IndexBuildResult(
        repo_root=str(root),
        indexed_files=len(indexed_files),
    )


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_chunk(
    path: Path,
    relative_path: str,
    language: str,
    content: str,
    structure,
) -> ToolHit:
    line_count = content.count("\n") + (1 if content else 0)
    return ToolHit(
        file=relative_path,
        symbol=None,
        kind="file",
        line_start=1 if content else None,
        line_end=line_count if content else None,
        content=content,
        metadata={
            "language": language,
            "size_bytes": path.stat().st_size,
            "imports": structure.imports,
            "exports": structure.exports,
            "calls": structure.calls,
            "fields": structure.fields,
        },
    )


def _symbol_chunks(relative_path: str, language: str, content: str) -> list[ToolHit]:
    chunks: list[ToolHit] = []
    for symbol in extract_symbols(content):
        structure = extract_structure(symbol.content)
        chunks.append(
            ToolHit(
                file=relative_path,
                symbol=symbol.name,
                kind=symbol.kind,
                line_start=symbol.line_start,
                line_end=symbol.line_end,
                content=symbol.content,
                metadata={
                    "language": language,
                    "symbol_kind": symbol.kind,
                    "calls": structure.calls,
                    "fields": structure.fields,
                },
            )
        )
    return chunks
