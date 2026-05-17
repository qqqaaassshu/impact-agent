from fastapi.testclient import TestClient

from impact_agent.models.history import AssessmentHistoryItem, AssessmentRecord
from impact_agent.models.llm import ClarificationNeeded, UnsupportedRequest
from impact_agent.models.report import AssessmentReport, Summary
from impact_agent.web import app as web_app


class FakeService:
    def submit(self, raw_input, progress_callback=None):
        if progress_callback:
            progress_callback({"stage": "test", "title": "测试进度", "message": "测试流式进度"})
        if raw_input["requirement"] == "need clarification":
            return ClarificationNeeded(questions=["请补充旧字段名"])
        if raw_input["requirement"] == "unsupported":
            return UnsupportedRequest(reason="当前版本只支持字段变更分析")
        return AssessmentReport(
            summary=Summary(
                requirement=raw_input["requirement"],
                change_type="field_rename",
                risk_level="low",
                overall_confidence="high",
                needs_human_review=False,
                conclusion="确定影响 1 项，不确定 0 项，已排除 0 项",
                source_snapshot={"type": "local", "root_path": raw_input["source"].get("root_path")},
                assessment_id="a-1",
                created_at="2026-05-14T00:00:00+00:00",
            ),
            confirmed_affected=[{"file_path": "src/order.ts", "line_no": 1}],
            uncertain=[],
            excluded=[],
            coverage={"search_round": 1},
            evidence_chain={"items": [], "count": 1},
            knowledge_used={},
            next_action="请优先处理“确定影响项”中的结果",
            trace=[{"node": "validated_request"}],
        )

    def list_history(self, limit=50):
        return [
            AssessmentHistoryItem(
                assessment_id="a-1",
                created_at="2026-05-14T00:00:00+00:00",
                requirement="将 amount 改为 totalAmount",
                change_type="field_rename",
                risk_level="low",
                overall_confidence="high",
                needs_human_review=False,
                conclusion="确定影响 1 项，不确定 0 项，已排除 0 项",
                project_root="/tmp/project",
                repo_path="src",
                module="order",
            )
        ]

    def get_history_detail(self, assessment_id: str):
        if assessment_id != "a-1":
            return None
        history_item = self.list_history()[0]
        report = self.submit(
            {
                "source": {"root_path": "/tmp/project"},
                "requirement": history_item.requirement,
            }
        )
        return AssessmentRecord(
            assessment_id="a-1",
            created_at="2026-05-14T00:00:00+00:00",
            request={"repo_path": "src"},
            history_item=history_item,
            report=report,
        )


class FailingService:
    def submit(self, raw_input):
        raise ValueError("请设置 LLM_BASE_URL")


def test_health_endpoint() -> None:
    client = TestClient(web_app.app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_assessment_returns_report(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "service", FakeService())
    client = TestClient(web_app.app)

    response = client.post(
        "/api/assessments",
        json={
            "requirement": "将 amount 改为 totalAmount",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "report"
    assert payload["summary"]["change_type"] == "field_rename"
    assert "uncertain" in payload
    assert "excluded" in payload


def test_create_assessment_uses_root_when_repo_path_is_empty(monkeypatch) -> None:
    class CapturingService(FakeService):
        raw_input = None

        def submit(self, raw_input):
            self.raw_input = raw_input
            return super().submit(raw_input)

    fake_service = CapturingService()
    monkeypatch.setattr(web_app, "service", fake_service)
    client = TestClient(web_app.app)

    response = client.post(
        "/api/assessments",
        json={
            "requirement": "将 amount 改为 totalAmount",
            "root_path": "/tmp/project",
            "repo_path": "",
        },
    )

    assert response.status_code == 200
    assert fake_service.raw_input["repo_path"] is None


def test_stream_assessment_returns_progress_and_result(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "service", FakeService())
    client = TestClient(web_app.app)

    response = client.post(
        "/api/assessments/stream",
        json={
            "requirement": "将 amount 改为 totalAmount",
            "root_path": "/tmp/project",
        },
    )

    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "event: result" in response.text
    assert '"kind": "report"' in response.text


def test_create_assessment_returns_clarification(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "service", FakeService())
    client = TestClient(web_app.app)

    response = client.post(
        "/api/assessments",
        json={
            "requirement": "need clarification",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "clarification"
    assert payload["needs_clarification"] is True


def test_create_assessment_returns_unsupported(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "service", FakeService())
    client = TestClient(web_app.app)

    response = client.post(
        "/api/assessments",
        json={
            "requirement": "unsupported",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "unsupported"
    assert payload["supported"] is False


def test_create_assessment_returns_chinese_error(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "service", FailingService())
    client = TestClient(web_app.app)

    response = client.post(
        "/api/assessments",
        json={
            "requirement": "你好",
        },
    )

    assert response.status_code == 400
    assert "LLM_BASE_URL" in response.json()["detail"]


def test_history_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "service", FakeService())
    client = TestClient(web_app.app)

    list_response = client.get("/api/assessments")
    assert list_response.status_code == 200
    assert list_response.json()[0]["assessment_id"] == "a-1"

    detail_response = client.get("/api/assessments/a-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["assessment_id"] == "a-1"

    missing_response = client.get("/api/assessments/missing")
    assert missing_response.status_code == 404
