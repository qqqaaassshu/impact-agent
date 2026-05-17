from impact_agent.models.history import AssessmentHistoryItem
from impact_agent.models.llm import ClarificationNeeded, UnsupportedRequest
from impact_agent.models.report import AssessmentReport, Summary
from impact_agent.services.assessment_service import AssessmentService
from impact_agent.services import assessment_service as assessment_service_module


def test_submit_returns_clarification(monkeypatch) -> None:
    monkeypatch.setattr(
        assessment_service_module,
        "intake_and_normalize",
        lambda raw, progress_callback=None: ClarificationNeeded(questions=["请补充旧字段名"]),
    )

    result = AssessmentService().submit({"requirement": "x"})

    assert isinstance(result, ClarificationNeeded)


def test_submit_returns_unsupported(monkeypatch) -> None:
    unsupported = UnsupportedRequest(reason="当前版本只支持字段变更分析")
    monkeypatch.setattr(
        assessment_service_module,
        "intake_and_normalize",
        lambda raw, progress_callback=None: unsupported,
    )

    result = AssessmentService().submit({"requirement": "新增导出按钮"})

    assert result is unsupported


def test_submit_returns_report(monkeypatch) -> None:
    request = type("Request", (), {"model_dump": lambda self: {"source": {}}, "requirement": "x"})()
    report = AssessmentReport(
        summary=Summary(
            requirement="x",
            change_type="field_rename",
            risk_level="low",
            overall_confidence="high",
            needs_human_review=False,
            conclusion="确定影响 1 项，不确定 0 项，已排除 0 项",
            source_snapshot={"type": "local"},
        ),
        confirmed_affected=[],
        uncertain=[],
        excluded=[],
        coverage={},
        evidence_chain={"items": [], "count": 0},
        knowledge_used={},
        next_action=None,
        trace=[],
    )

    class FakeRunner:
        def __init__(self, progress_callback=None) -> None:
            self.progress_callback = progress_callback

        def run(self, normalized_request):
            assert normalized_request is request
            return report

    monkeypatch.setattr(assessment_service_module, "intake_and_normalize", lambda raw, progress_callback=None: request)
    monkeypatch.setattr(assessment_service_module, "AssessmentRunner", FakeRunner)

    result = AssessmentService().submit({"requirement": "x"})

    assert result is report


def test_submit_emits_llm_intake_progress_only_when_llm_path_is_used(monkeypatch) -> None:
    events = []
    request = type("Request", (), {"model_dump": lambda self: {"source": {}}, "requirement": "x"})()
    report = AssessmentReport(
        summary=Summary(
            requirement="x",
            change_type="field_rename",
            risk_level="low",
            overall_confidence="high",
            needs_human_review=False,
            conclusion="confirmed 0, uncertain 0, excluded 0",
            source_snapshot={"type": "local"},
        ),
        confirmed_affected=[],
        uncertain=[],
        excluded=[],
        coverage={},
        evidence_chain={"items": [], "count": 0},
        knowledge_used={},
        next_action=None,
        trace=[],
    )

    class FakeRunner:
        def __init__(self, progress_callback=None) -> None:
            self.progress_callback = progress_callback

        def run(self, normalized_request):
            return report

    def fake_intake(raw, progress_callback=None):
        if progress_callback:
            progress_callback({"stage": "llm_intake", "title": "调用大模型判断需求", "message": "x"})
        return request

    monkeypatch.setattr(assessment_service_module, "intake_and_normalize", fake_intake)
    monkeypatch.setattr(assessment_service_module, "AssessmentRunner", FakeRunner)

    result = AssessmentService().submit("ambiguous", progress_callback=events.append)

    assert result is report
    assert [event["stage"] for event in events] == ["intake", "llm_intake"]


def test_history_methods_delegate(monkeypatch) -> None:
    history_items = [
        AssessmentHistoryItem(
            assessment_id="a-1",
            created_at="2026-05-14T00:00:00+00:00",
            requirement="x",
            change_type="field_rename",
            risk_level="low",
            overall_confidence="high",
            needs_human_review=False,
            conclusion="done",
        )
    ]
    monkeypatch.setattr(assessment_service_module, "list_assessment_history", lambda limit=50: history_items)
    monkeypatch.setattr(assessment_service_module, "get_assessment_record", lambda assessment_id: {"assessment_id": assessment_id})

    service = AssessmentService()

    assert service.list_history() == history_items
    assert service.get_history_detail("a-1") == {"assessment_id": "a-1"}
