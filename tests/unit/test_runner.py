import json
from pathlib import Path

from impact_agent.orchestrator.runner import AssessmentRunner
from impact_agent.services.intake import intake_and_normalize


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
REQUEST_FILE = FIXTURE_ROOT / "local_field_rename_request.json"


def test_runner_produces_three_way_report() -> None:
    payload = json.loads(REQUEST_FILE.read_text(encoding="utf-8"))
    payload["source"]["root_path"] = str(FIXTURE_ROOT / "local_field_rename_project")
    request = intake_and_normalize(payload)

    report = AssessmentRunner().run(request)

    assert report.summary.change_type == "field_rename"
    assert report.confirmed_affected
    assert report.uncertain_matches
    assert report.excluded_matches
    assert report.evidence_chain["count"] >= 3
