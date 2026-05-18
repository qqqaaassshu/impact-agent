from pathlib import Path

from impact_agent.config import get_settings
from impact_agent.indexer.store import IndexStore
from impact_agent.indexer.vector_store import ChromaVectorStore
from impact_agent.models.tool import ToolHit


def search_by_symbol(
    symbol: str,
    symbol_type: str | None = None,
    *,
    store: IndexStore | None = None,
    limit: int | None = None,
) -> list[ToolHit]:
    """Search symbol definitions and direct references."""
    _ = symbol_type
    active_store = store or _default_store()
    return active_store.search_symbol(symbol, limit=limit or get_settings().max_tool_results)


def search_by_usage(
    symbol: str,
    file_hint: str | None = None,
    *,
    store: IndexStore | None = None,
    limit: int | None = None,
) -> list[ToolHit]:
    """Search callers, importers, and dependents of a symbol."""
    active_store = store or _default_store()
    _ = file_hint
    return active_store.search_usage(symbol, limit=limit or get_settings().max_tool_results)


def search_by_file(
    file_path: str,
    *,
    store: IndexStore | None = None,
    limit: int | None = None,
) -> list[ToolHit]:
    """Return a file-level structure summary."""
    active_store = store or _default_store()
    return active_store.search_file(file_path, limit=limit or get_settings().max_tool_results)


def search_by_text(
    query: str,
    filters: dict | None = None,
    *,
    store: IndexStore | None = None,
    limit: int | None = None,
) -> list[ToolHit]:
    """Run semantic or text search for business terms."""
    _ = filters
    active_store = store or _default_store()
    settings = get_settings()
    active_limit = limit or settings.max_tool_results
    if store is None:
        try:
            semantic_hits = ChromaVectorStore(settings).semantic_search(
                query,
                limit=active_limit,
                repo_root=active_store.active_repo_root(),
            )
            if semantic_hits:
                return semantic_hits
        except Exception:
            pass
    return active_store.search_text(query, limit=active_limit)


def _default_store() -> IndexStore:
    settings = get_settings()
    return IndexStore(Path(settings.data_dir) / "index.sqlite")
