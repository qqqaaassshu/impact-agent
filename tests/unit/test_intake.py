from impact_agent.models.request import AssessmentRequest
from impact_agent.services.intake import intake_and_normalize


def test_intake_uses_default_file_types() -> None:
    request = intake_and_normalize(
        {
            "source": {"type": "local", "root_path": "/tmp/project"},
            "requirement": "rename amount",
            "change_type": "field_rename",
            "change_scope": {"old_name": "amount", "new_name": "totalAmount"},
            "file_types": [],
        }
    )

    assert isinstance(request, AssessmentRequest)
    assert ".ts" in request.file_types
    assert ".vue" in request.file_types


def test_intake_rejects_natural_language_string() -> None:
    try:
        intake_and_normalize("rename amount to totalAmount")
    except ValueError as exc:
        assert "未启用自然语言 intake" in str(exc)
    else:
        raise AssertionError("expected ValueError")
