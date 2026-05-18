from impact_agent.config import Settings
from impact_agent.indexer.service import build_index
from impact_agent.indexer.store import IndexStore


def test_build_index_records_frontend_files(tmp_path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "App.vue").write_text("<template>{{ price }}</template>", encoding="utf-8")
    (src / "order.ts").write_text("export const price = 100", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "ignored.ts").write_text("export const ignored = true", encoding="utf-8")

    settings = Settings(IMPACT_AGENT_DATA_DIR=str(tmp_path / ".impact-agent"))

    result = build_index(repo, settings)
    status = IndexStore(tmp_path / ".impact-agent" / "index.sqlite").status()

    assert result.indexed_files == 2
    assert status.status == "ready"
    assert status.indexed_files == 2


def test_build_index_records_symbol_chunks(tmp_path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "order.ts").write_text("export const price = 100", encoding="utf-8")

    settings = Settings(IMPACT_AGENT_DATA_DIR=str(tmp_path / ".impact-agent"))
    build_index(repo, settings)
    store = IndexStore(tmp_path / ".impact-agent" / "index.sqlite")

    hits = store.search_symbol("price")

    assert hits[0].symbol == "price"
    assert hits[0].kind == "const"


def test_build_index_records_structure_metadata(tmp_path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "order.ts").write_text(
        """
import { formatPrice } from './format'

export function renderOrder(order) {
  return formatPrice(order.price)
}
""",
        encoding="utf-8",
    )

    settings = Settings(IMPACT_AGENT_DATA_DIR=str(tmp_path / ".impact-agent"))
    build_index(repo, settings)
    store = IndexStore(tmp_path / ".impact-agent" / "index.sqlite")

    file_hit = store.search_file("order.ts")[0]
    symbol_hit = store.search_symbol("renderOrder")[0]

    assert file_hit.metadata["imports"] == ["formatPrice"]
    assert file_hit.metadata["exports"] == ["renderOrder"]
    assert "formatPrice" in file_hit.metadata["calls"]
    assert "price" in file_hit.metadata["fields"]
    assert "formatPrice" in symbol_hit.metadata["calls"]
    assert "price" in symbol_hit.metadata["fields"]


def test_build_index_respects_include_paths(tmp_path) -> None:
    repo = tmp_path / "repo"
    (repo / "app-a").mkdir(parents=True)
    (repo / "app-b").mkdir(parents=True)
    (repo / "app-a" / "A.ts").write_text("export const a = 1", encoding="utf-8")
    (repo / "app-b" / "B.ts").write_text("export const b = 1", encoding="utf-8")

    settings = Settings(IMPACT_AGENT_DATA_DIR=str(tmp_path / ".impact-agent"))
    result = build_index(repo, settings, include_paths=["app-a"])
    store = IndexStore(tmp_path / ".impact-agent" / "index.sqlite")

    assert result.indexed_files == 1
    assert store.search_file("A.ts")
    assert not store.search_file("B.ts")


def test_search_uses_latest_index_run_repo(tmp_path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    (repo_a / "src").mkdir(parents=True)
    (repo_b / "src").mkdir(parents=True)
    (repo_a / "src" / "A.ts").write_text("export const price = 1", encoding="utf-8")
    (repo_b / "src" / "B.ts").write_text("export const price = 2", encoding="utf-8")

    settings = Settings(IMPACT_AGENT_DATA_DIR=str(tmp_path / ".impact-agent"))
    build_index(repo_a, settings)
    build_index(repo_b, settings)
    store = IndexStore(tmp_path / ".impact-agent" / "index.sqlite")

    hits = store.search_symbol("price")

    assert hits
    assert {hit.file for hit in hits} == {"src/B.ts"}
