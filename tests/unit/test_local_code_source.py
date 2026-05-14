from pathlib import Path

from impact_agent.adapters.code_source.local import LocalCodeSourceAdapter


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "local_field_rename_project"


def test_local_search_finds_matches() -> None:
    adapter = LocalCodeSourceAdapter(str(FIXTURE_ROOT))

    result = adapter.search("amount", [".ts"], "src")

    assert result["results"]
    assert any(item["relative_path"] == "src/order.ts" for item in result["results"])


def test_local_snapshot_reports_non_git_directory() -> None:
    adapter = LocalCodeSourceAdapter(str(FIXTURE_ROOT))

    snapshot = adapter.snapshot()

    assert snapshot["type"] == "local"
    assert snapshot["git"]["is_repo"] is False
