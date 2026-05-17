from impact_agent.services.frontend_search import search_local_candidates, search_local_candidates_many


def test_search_local_candidates_normalizes_results_and_ignores_vendor_dirs(tmp_path) -> None:
    project_root = tmp_path / "project"
    source_root = project_root / "src"
    vendor_root = project_root / "node_modules" / "pkg"
    source_root.mkdir(parents=True)
    vendor_root.mkdir(parents=True)

    (source_root / "order.ts").write_text(
        "export const order = { amount: 1 }\nconsole.log(order.amount)\n",
        encoding="utf-8",
    )
    (vendor_root / "ignored.ts").write_text("export const amount = 1\n", encoding="utf-8")

    result = search_local_candidates(
        root_path=str(project_root),
        keyword="amount",
        file_types=[".ts"],
        repo_path="src",
    )

    assert result["search_root"] == str(source_root.resolve())
    assert result["scanned_files"] == 1
    assert len(result["results"]) == 2
    assert result["results"][0]["relative_path"] == "src/order.ts"
    assert result["results"][0]["file_kind"] == "source_module"
    assert all("node_modules" not in item["file_path"] for item in result["results"])


def test_search_local_candidates_marks_vue_files() -> None:
    result = search_local_candidates(
        root_path="tests/fixtures/local_field_rename_project",
        keyword="amount",
        file_types=[".ts"],
        repo_path="src",
    )

    assert result["results"]


def test_search_local_candidates_many_groups_results_by_keyword(tmp_path) -> None:
    project_root = tmp_path / "project"
    source_root = project_root / "src"
    source_root.mkdir(parents=True)

    (source_root / "order.ts").write_text(
        "export const order = { amount: 1, totalAmount: 1 }\nconsole.log(order.amount)\n",
        encoding="utf-8",
    )

    result = search_local_candidates_many(
        root_path=str(project_root),
        keywords=["amount", "totalAmount"],
        file_types=[".ts"],
        repo_path="src",
    )

    assert result["search_engine"] in {"rg", "python"}
    assert len(result["results_by_keyword"]["amount"]) == 2
    assert len(result["results_by_keyword"]["totalAmount"]) == 1


def test_search_local_candidates_does_not_match_keyword_inside_longer_identifier(tmp_path) -> None:
    project_root = tmp_path / "project"
    source_root = project_root / "src"
    source_root.mkdir(parents=True)

    (source_root / "market.js").write_text(
        "Eui.Messager.showToastMsg({ msg: 'ok' })\n",
        encoding="utf-8",
    )

    result = search_local_candidates(
        root_path=str(project_root),
        keyword="toastMsg",
        file_types=[".js"],
        repo_path="src",
    )

    assert result["results"] == []
