from impact_agent.models.llm import ClueExpansionResult, SemanticMatchDecision
from impact_agent.models.request import AssessmentRequest
from impact_agent.strategies import field_rename
from impact_agent.strategies.field_rename import FieldRenameStrategy


class FakeStructuredLLM:
    def __init__(self, result) -> None:
        self.result = result

    def invoke(self, prompt: str):
        return self.result


class FakeLLM:
    def __init__(self, result) -> None:
        self.result = result

    def with_structured_output(self, schema):
        return FakeStructuredLLM(self.result)


def build_request() -> AssessmentRequest:
    return AssessmentRequest.model_validate(
        {
            "source": {"type": "local", "root_path": "/tmp/project"},
            "requirement": "rename amount",
            "change_type": "field_rename",
            "change_scope": {"old_name": "amount", "new_name": "totalAmount"},
            "file_types": [".ts"],
        }
    )


def test_generate_clues_merges_base_and_llm_variants(monkeypatch) -> None:
    monkeypatch.setenv("LLM_CLUE_EXPANSION", "true")
    monkeypatch.setattr(
        field_rename,
        "get_llm",
        lambda: FakeLLM(
            ClueExpansionResult(
                clues=["amount", "totalAmount", "amount_value"],
                reasoning="include snake_case variant",
            )
        ),
    )

    strategy = FieldRenameStrategy()
    clues = strategy.generate_clues(build_request(), {}, [])

    assert "amount" in [item["keyword"] for item in clues]
    assert "totalAmount" not in [item["keyword"] for item in clues]
    llm_clue = next(item for item in clues if item["keyword"] == "amount_value")
    assert llm_clue["clue_category"] == "llm_variant"
    assert llm_clue["source"] == "llm"


def test_generate_clues_does_not_search_new_name_by_default() -> None:
    strategy = FieldRenameStrategy()
    clues = strategy.generate_clues(build_request(), {}, [])

    keywords = {item["keyword"] for item in clues}

    assert "amount" in keywords
    assert "totalAmount" not in keywords


def test_generate_clues_can_include_new_name_as_reference_when_enabled() -> None:
    request = build_request()
    request.change_scope.include_new_name_references = True

    clues = FieldRenameStrategy().generate_clues(request, {}, [])

    assert any(item["keyword"] == "totalAmount" and item["clue_category"] == "new_name" for item in clues)
    assert any(
        item["keyword"] == "total_amount" and item.get("variant_source") == "new_name"
        for item in clues
    )


def test_classify_new_name_reference_is_excluded() -> None:
    decision = FieldRenameStrategy().classify_match(
        "src/order.ts",
        "console.log(order.totalAmount)",
        {"keyword": "totalAmount", "clue_category": "new_name"},
        {"candidate": {"line": "console.log(order.totalAmount)", "line_no": 1}},
    )

    assert decision["status"] == "excluded"
    assert decision["reason"] == "already_migrated_reference"


def test_classify_new_name_variant_reference_is_excluded() -> None:
    decision = FieldRenameStrategy().classify_match(
        "src/order.ts",
        'console.log(order["total_amount"])',
        {"keyword": "total_amount", "clue_category": "deterministic_variant", "variant_source": "new_name"},
        {"candidate": {"line": 'console.log(order["total_amount"])', "line_no": 1}},
    )

    assert decision["status"] == "excluded"
    assert decision["reason"] == "already_migrated_reference"


def test_generate_clues_filters_llm_new_name_when_not_requested(monkeypatch) -> None:
    monkeypatch.setenv("LLM_CLUE_EXPANSION", "true")
    monkeypatch.setattr(
        field_rename,
        "get_llm",
        lambda: FakeLLM(
            ClueExpansionResult(
                clues=["totalAmount", "total_amount", "amount_value"],
                reasoning="include variants",
            )
        ),
    )

    clues = FieldRenameStrategy().generate_clues(build_request(), {}, [])
    keywords = {item["keyword"] for item in clues}

    assert "totalAmount" not in keywords
    assert "total_amount" not in keywords
    assert "amount_value" in keywords


def test_classify_match_uses_llm_fallback_for_dynamic_reference(monkeypatch) -> None:
    monkeypatch.setenv("LLM_SEMANTIC_REVIEW", "true")
    monkeypatch.setattr(
        field_rename,
        "get_llm",
        lambda: FakeLLM(SemanticMatchDecision(is_affected=True, reason="dynamic access uses target field")),
    )

    strategy = FieldRenameStrategy()
    decision = strategy.classify_match(
        "src/dynamic.ts",
        'const fieldName = "amount";\nreturn data[fieldName];',
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": 'return data[fieldName];', "line_no": 2}},
    )

    assert decision["status"] == "confirmed_affected"
    assert decision["reason"] == "dynamic access uses target field"
    assert decision["confidence"] == "medium"


def test_classify_match_keeps_uncertain_when_llm_cannot_decide(monkeypatch) -> None:
    monkeypatch.setenv("LLM_SEMANTIC_REVIEW", "true")
    monkeypatch.setattr(
        field_rename,
        "get_llm",
        lambda: FakeLLM(SemanticMatchDecision(is_affected=None, reason="not enough context")),
    )

    strategy = FieldRenameStrategy()
    decision = strategy.classify_match(
        "src/dynamic.ts",
        'return data[fieldName];',
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": 'return data[fieldName];', "line_no": 1}},
    )

    assert decision["status"] == "uncertain"
    assert decision["reason"] == "not enough context"


def test_classify_match_marks_dynamic_reference_uncertain_without_llm() -> None:
    strategy = FieldRenameStrategy()
    decision = strategy.classify_match(
        "src/dynamic.ts",
        'return data[fieldName];',
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": 'return data[fieldName];', "line_no": 1}},
    )

    assert decision["status"] == "uncertain"
    assert decision["reason"] == "dynamic_field_reference"


def test_classify_match_marks_plain_text_excluded() -> None:
    strategy = FieldRenameStrategy()
    decision = strategy.classify_match(
        "src/copy.ts",
        "",
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": 'export const copy = "total amount due";', "line_no": 1}},
    )

    assert decision["status"] == "excluded"


def test_classify_match_marks_comment_hit_explicitly() -> None:
    strategy = FieldRenameStrategy()
    decision = strategy.classify_match(
        "src/order.ts",
        "",
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": "// TODO rename amount after backend release", "line_no": 8}},
    )

    assert decision["status"] == "excluded"
    assert decision["reason"] == "comment_match"
    assert decision["match_kind"] == "comment"


def test_classify_match_uses_react_analyzer_before_dynamic_fallback() -> None:
    strategy = FieldRenameStrategy()
    content = """
import React from 'react';

const Query = () => <TraderInput fieldName="amount" label="金额" />;
""".strip()

    decision = strategy.classify_match(
        "src/Query.jsx",
        content,
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": '<TraderInput fieldName="amount" label="金额" />', "line_no": 3}},
    )

    assert decision["status"] == "confirmed_affected"
    assert decision["framework"] == "react"
    assert decision["usage_type"] == "config_field"


def test_classify_match_uses_skill_ast_before_plain_static_reference(monkeypatch) -> None:
    monkeypatch.setenv("AST_ANALYSIS_ENGINE", "python")
    strategy = FieldRenameStrategy()
    content = """
interface Order {
  amount?: number;
}
""".strip()

    decision = strategy.classify_match(
        "src/order.ts",
        content,
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": "amount?: number;", "line_no": 2}},
    )

    assert decision["status"] == "confirmed_affected"
    assert decision["reason"] == "ast_type_field"
    assert decision["analysis_engine"] == "python_structure"


def test_collect_relations_uses_skill_ast_destructuring_alias(monkeypatch) -> None:
    monkeypatch.setenv("AST_ANALYSIS_ENGINE", "python")
    strategy = FieldRenameStrategy()
    content = "\n".join(
        [
            "const { amount: orderAmount } = order;",
            "return formatMoney(orderAmount);",
        ]
    )
    candidate = {
        "file_path": "src/order.ts",
        "relative_path": "src/order.ts",
        "line": "const { amount: orderAmount } = order;",
        "line_no": 1,
        "file_kind": "ts",
    }
    decision = {
        "status": "uncertain",
        "reason": "dynamic_field_reference",
        "confidence": "low",
        "file_path": "src/order.ts",
        "line_no": 1,
        "code": "const { amount: orderAmount } = order;",
        "clue_category": "old_name",
    }

    relations = strategy.collect_relations(
        candidate,
        {
            "content": content,
            "clue": {"keyword": "amount", "clue_category": "old_name"},
            "decision": decision,
            "evidence_id": "old_name::src/order.ts::1",
        },
    )

    assert len(relations) == 1
    assert relations[0]["propagated_symbol"] == "orderAmount"
    assert relations[0]["propagated_property"] == "amount"
    assert relations[0]["propagation_source"] == "destructuring_alias"


def test_collect_relations_derives_same_file_variable_propagation() -> None:
    strategy = FieldRenameStrategy()
    content = '\n'.join(
        [
            'const fieldName = "amount";',
            'return row[fieldName];',
            'const label = "amount";',
        ]
    )
    candidate = {
        "file_path": "src/dynamic.ts",
        "relative_path": "src/dynamic.ts",
        "line": 'const fieldName = "amount";',
        "line_no": 1,
        "file_kind": "ts",
    }
    decision = {
        "status": "uncertain",
        "reason": "dynamic_field_reference",
        "confidence": "low",
        "file_path": "src/dynamic.ts",
        "line_no": 1,
        "code": 'const fieldName = "amount";',
        "clue_category": "old_name",
    }

    relations = strategy.collect_relations(
        candidate,
        {
            "content": content,
            "clue": {"keyword": "amount", "clue_category": "old_name"},
            "decision": decision,
            "evidence_id": "old_name::src/dynamic.ts::1",
        },
    )

    assert len(relations) == 1
    assert relations[0]["reason"] == "variable_propagation_reference"
    assert relations[0]["line_no"] == 2
    assert relations[0]["propagated_symbol"] == "fieldName"
    assert relations[0]["source_evidence_id"] == "old_name::src/dynamic.ts::1"
