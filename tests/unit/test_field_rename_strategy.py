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

    assert [item["keyword"] for item in clues] == ["amount", "totalAmount", "amount_value"]
    assert clues[-1]["clue_category"] == "llm_variant"
    assert clues[-1]["source"] == "llm"


def test_classify_match_uses_llm_fallback_for_dynamic_reference(monkeypatch) -> None:
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


def test_classify_match_marks_plain_text_excluded() -> None:
    strategy = FieldRenameStrategy()
    decision = strategy.classify_match(
        "src/copy.ts",
        "",
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": 'export const copy = "total amount due";', "line_no": 1}},
    )

    assert decision["status"] == "excluded"
