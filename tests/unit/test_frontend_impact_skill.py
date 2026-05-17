from impact_agent.services.frontend_impact_skill import FrontendImpactSearchSkill


def test_skill_ast_analyze_detects_type_object_config_and_destructuring(monkeypatch) -> None:
    monkeypatch.setenv("AST_ANALYSIS_ENGINE", "python")
    content = """
interface Order {
  amount?: number;
}

const columns = [{ dataIndex: "amount" }];
const view = order.amount;
const { amount: orderAmount } = order;
console.log(orderAmount);
""".strip()

    result = FrontendImpactSearchSkill().ast_analyze(
        file_path="src/order.ts",
        content=content,
        field_name="amount",
    )

    observation = result["observation"]
    usage_types = {item["usage_type"] for item in observation["usages"]}
    binding_symbols = {item["symbol"] for item in observation["bindings"]}

    assert result["skill"] == "frontend-impact-search"
    assert result["action"] == "ast_analyze"
    assert observation["available"] is True
    assert {"type_field", "config_field", "object_property", "destructuring_alias"}.issubset(usage_types)
    assert "orderAmount" in binding_symbols


def test_skill_local_search_many_returns_structured_observation(tmp_path) -> None:
    project_root = tmp_path / "project"
    source_root = project_root / "src"
    source_root.mkdir(parents=True)
    (source_root / "order.ts").write_text("export const order = { amount: 1 }\n", encoding="utf-8")

    result = FrontendImpactSearchSkill().local_search_many(
        root_path=str(project_root),
        keywords=["amount"],
        file_types=[".ts"],
        repo_path="src",
    )

    assert result["skill"] == "frontend-impact-search"
    assert result["action"] == "local_search_many"
    assert result["observation"]["results_by_keyword"]["amount"]
