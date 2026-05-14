from impact_agent.models.state import AssessmentState
from impact_agent.services.report_builder import build_report


def test_report_builder_sets_review_flag_for_uncertain_items() -> None:
    state = AssessmentState(
        request={"requirement": "rename amount", "change_type": "field_rename"},
        source_snapshot={"type": "local"},
        uncertain_matches=[{"file_path": "src/dynamic.ts"}],
        risk={"risk_level": "medium"},
        confidence={"overall_confidence": "medium"},
    )

    report = build_report(state)

    assert report.summary.needs_human_review is True
    assert report.next_action is not None
