from impact_agent.models.request import AssessmentRequest
from impact_agent.strategies.field_rename import FieldRenameStrategy


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


def test_generate_clues_contains_old_and_new_names() -> None:
    strategy = FieldRenameStrategy()
    clues = strategy.generate_clues(build_request(), {}, [])

    assert [item["keyword"] for item in clues] == ["amount", "totalAmount"]


def test_classify_match_marks_dynamic_reference_uncertain() -> None:
    strategy = FieldRenameStrategy()
    decision = strategy.classify_match(
        "src/dynamic.ts",
        "",
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": 'return data[fieldName];', "line_no": 1}},
    )

    assert decision["status"] == "uncertain"


def test_classify_match_marks_plain_text_excluded() -> None:
    strategy = FieldRenameStrategy()
    decision = strategy.classify_match(
        "src/copy.ts",
        "",
        {"keyword": "amount", "clue_category": "old_name"},
        {"candidate": {"line": 'export const copy = "total amount due";', "line_no": 1}},
    )

    assert decision["status"] == "excluded"
