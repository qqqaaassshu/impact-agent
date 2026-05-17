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
    assert "totalAmount" in [item["keyword"] for item in clues]
    llm_clue = next(item for item in clues if item["keyword"] == "amount_value")
    assert llm_clue["clue_category"] == "llm_variant"
    assert llm_clue["source"] == "llm"


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
