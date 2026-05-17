from pathlib import Path

from impact_agent.adapters.code_source.local import LocalCodeSourceAdapter


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "local_field_rename_project"


def test_local_search_finds_matches() -> None:
    adapter = LocalCodeSourceAdapter(str(FIXTURE_ROOT))

    result = adapter.search("amount", [".ts"], "src")

    assert result["results"]
    assert any(item["relative_path"] == "src/order.ts" for item in result["results"])


def test_local_search_many_groups_matches() -> None:
    adapter = LocalCodeSourceAdapter(str(FIXTURE_ROOT))

    result = adapter.search_many(["amount", "totalAmount"], [".ts"], "src")

    assert result["results_by_keyword"]["amount"]
    assert result["results_by_keyword"]["totalAmount"]


def test_local_snapshot_reports_directory_metadata() -> None:
    adapter = LocalCodeSourceAdapter(str(FIXTURE_ROOT))

    snapshot = adapter.snapshot()

    assert snapshot["type"] == "local"
    assert snapshot["root_path"] == str(FIXTURE_ROOT.resolve())
    assert "is_repo" in snapshot["git"]
    assert "commit" in snapshot["git"]
    assert "has_uncommitted_changes" in snapshot["git"]
