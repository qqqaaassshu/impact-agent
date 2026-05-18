from impact_agent.config import Settings
from impact_agent.indexer.service import build_index
from impact_agent.indexer.store import IndexStore
from impact_agent.tools.code_search import search_by_file, search_by_symbol, search_by_usage


def test_search_tools_return_indexed_chunks(tmp_path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "App.vue").write_text("<template>{{ price }}</template>", encoding="utf-8")

    settings = Settings(IMPACT_AGENT_DATA_DIR=str(tmp_path / ".impact-agent"))
    build_index(repo, settings)
    store = IndexStore(tmp_path / ".impact-agent" / "index.sqlite")

    file_hits = search_by_file("App.vue", store=store)

    assert file_hits[0].metadata["language"] == "vue"


def test_search_by_symbol_prefers_extracted_symbol_chunks(tmp_path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "order.ts").write_text(
        """
export function getOrderDetail() {
  return { price: 100 };
}
""",
        encoding="utf-8",
    )

    settings = Settings(IMPACT_AGENT_DATA_DIR=str(tmp_path / ".impact-agent"))
    build_index(repo, settings)
    store = IndexStore(tmp_path / ".impact-agent" / "index.sqlite")

    hits = search_by_symbol("getOrderDetail", store=store)

    assert hits[0].file == "src/order.ts"
    assert hits[0].symbol == "getOrderDetail"
    assert hits[0].kind == "function"


def test_search_by_usage_uses_structure_metadata(tmp_path) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "format.ts").write_text("export function formatPrice(value) { return value }")
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

    hits = search_by_usage("formatPrice", store=store)

    assert hits[0].file == "src/order.ts"
    assert "formatPrice" in hits[0].metadata["calls"]
