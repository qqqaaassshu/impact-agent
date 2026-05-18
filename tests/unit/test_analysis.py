from impact_agent.config import Settings
from impact_agent.indexer.service import build_index
from impact_agent.models.analysis import AnalyzeRequest
from impact_agent.services.analysis import (
    analyze_requirement_without_llm,
    extract_requirement_entities,
)


def test_extract_requirement_entities() -> None:
    entities = extract_requirement_entities("行情 price 字段从分改成元，影响 QuoteCard")

    assert "price" in entities
    assert "QuoteCard" in entities
    assert "字段" not in entities


def test_analyze_requirement_returns_uncertain_candidates(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "QuoteCard.vue").write_text(
        "<template>{{ price }}</template>",
        encoding="utf-8",
    )
    monkeypatch.setenv("IMPACT_AGENT_DATA_DIR", str(tmp_path / ".impact-agent"))

    settings = Settings(IMPACT_AGENT_DATA_DIR=str(tmp_path / ".impact-agent"))
    build_index(repo, settings)

    report = analyze_requirement_without_llm(
        AnalyzeRequest(repo_root=str(repo), requirement="price 字段从分改成元")
    )

    assert report.uncertain
    assert report.uncertain[0].file == "src/QuoteCard.vue"
