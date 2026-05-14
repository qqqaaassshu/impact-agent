from impact_agent.models.llm import ClarificationNeeded
from impact_agent.models.report import AssessmentReport, Summary
from impact_agent import cli


class FakeAssessmentService:
    def __init__(self, result) -> None:
        self.result = result

    def submit(self, raw_input):
        return self.result


def test_cli_prints_clarification_json(monkeypatch, capsys, tmp_path) -> None:
    input_file = tmp_path / "prompt.txt"
    input_file.write_text("帮我看看这个字段改动会影响哪里", encoding="utf-8")

    monkeypatch.setattr(cli, "AssessmentService", lambda: FakeAssessmentService(ClarificationNeeded(questions=["请补充旧字段名"])))
    monkeypatch.setattr("sys.argv", ["impact_agent.cli", "--input", str(input_file)])

    cli.main()

    output = capsys.readouterr().out
    assert '"needs_clarification": true' in output
    assert '请补充旧字段名' in output


def test_cli_prints_report_json(monkeypatch, capsys, tmp_path) -> None:
    input_file = tmp_path / "request.json"
    input_file.write_text('{"source": {"type": "local", "root_path": "/tmp/project"}}', encoding="utf-8")

    report = AssessmentReport(
        summary=Summary(
            requirement="将 amount 改为 totalAmount",
            change_type="field_rename",
            risk_level="low",
            overall_confidence="high",
            needs_human_review=False,
            conclusion="confirmed=1, uncertain=0, excluded=0",
            source_snapshot={"type": "local"},
        ),
        confirmed_affected=[{"file_path": "src/order.ts", "line_no": 1}],
        uncertain_matches=[],
        excluded_matches=[],
        coverage={"search_round": 1},
        evidence_chain={"items": [], "count": 1},
        knowledge_used={},
        next_action="请优先处理 confirmed_affected 中的确定影响项",
        trace=[{"node": "validated_request"}],
    )

    monkeypatch.setattr(cli, "AssessmentService", lambda: FakeAssessmentService(report))
    monkeypatch.setattr("sys.argv", ["impact_agent.cli", "--input", str(input_file)])

    cli.main()

    output = capsys.readouterr().out
    assert '"change_type": "field_rename"' in output
    assert '"confirmed_affected"' in output
