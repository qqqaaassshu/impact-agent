from impact_agent.models.llm import ClarificationNeeded, IntakeParseResult
from impact_agent.models.request import AssessmentRequest
from impact_agent.services import intake
from impact_agent.services.intake import intake_and_normalize


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


def test_intake_parses_natural_language_string(monkeypatch) -> None:
    monkeypatch.setattr(
        intake,
        "get_llm",
        lambda: FakeLLM(
            IntakeParseResult(
                change_type="field_rename",
                old_name="amount",
                new_name="totalAmount",
                module="order",
                repo_path="src",
                entity_kind="api_field",
                requirement="将 amount 改为 totalAmount",
            )
        ),
    )

    result = intake_and_normalize(
        {
            "source": {"type": "local", "root_path": "/tmp/project"},
            "message": "请把订单金额字段从 amount 改成 totalAmount",
        }
    )

    assert isinstance(result, AssessmentRequest)
    assert result.change_scope.old_name == "amount"
    assert result.change_scope.new_name == "totalAmount"
    assert result.repo_path == "src"


def test_intake_returns_clarification_for_ambiguous_input(monkeypatch) -> None:
    monkeypatch.setattr(
        intake,
        "get_llm",
        lambda: FakeLLM(
            IntakeParseResult(
                needs_clarification=True,
                questions=["请补充旧字段名", "请补充新字段名"],
            )
        ),
    )

    result = intake_and_normalize("帮我看看这个字段改动会影响哪里")

    assert isinstance(result, ClarificationNeeded)
    assert result.questions == ["请补充旧字段名", "请补充新字段名"]
