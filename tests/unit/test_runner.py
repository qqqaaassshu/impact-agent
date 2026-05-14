import json
from pathlib import Path

from impact_agent.models.llm import ClueExpansionResult, SearchDecisionResult
from impact_agent.orchestrator import runner as runner_module
from impact_agent.orchestrator.runner import AssessmentRunner
from impact_agent.services.intake import intake_and_normalize
from impact_agent.strategies import field_rename as field_rename_module


class FakeStructuredLLM:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.index = 0

    def invoke(self, prompt: str):
        result = self.results[min(self.index, len(self.results) - 1)]
        self.index += 1
        return result


class FakeLLM:
    def __init__(self, results) -> None:
        self.structured_llm = FakeStructuredLLM(results)

    def with_structured_output(self, schema):
        return self.structured_llm


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
REQUEST_FILE = FIXTURE_ROOT / "local_field_rename_request.json"


def build_request():
    payload = json.loads(REQUEST_FILE.read_text(encoding="utf-8"))
    payload["source"]["root_path"] = str(FIXTURE_ROOT / "local_field_rename_project")
    return intake_and_normalize(payload)


def test_runner_produces_three_way_report_with_search_loop(monkeypatch) -> None:
    clue_llm = FakeLLM(
        [
            ClueExpansionResult(
                clues=["record.amount"],
                reasoning="include property access variant",
            )
        ]
    )
    decision_llm = FakeLLM(
        [
            SearchDecisionResult(
                action="search_more",
                next_keywords=["record.amount"],
                reasoning="search property access variant",
            ),
            SearchDecisionResult(action="finish", next_keywords=[], reasoning="enough evidence"),
        ]
    )
    monkeypatch.setattr(field_rename_module, "get_llm", lambda: clue_llm)
    monkeypatch.setattr(runner_module, "get_llm", lambda: decision_llm)

    request = build_request()
    report = AssessmentRunner().run(request)

    assert report.summary.change_type == "field_rename"
    assert report.confirmed_affected
    assert report.uncertain_matches
    assert report.excluded_matches
    assert report.evidence_chain["count"] >= 3
    assert report.coverage["search_round"] == 2
    assert "llm_decide_search:search_more" in report.trace
    assert "llm_decide_search:finish" in report.trace


def test_runner_stops_at_max_search_rounds(monkeypatch) -> None:
    monkeypatch.setattr(runner_module, "MAX_SEARCH_ROUNDS", 1)
    clue_llm = FakeLLM(
        [
            ClueExpansionResult(
                clues=["amount_value"],
                reasoning="include snake_case variant",
            )
        ]
    )
    decision_llm = FakeLLM(
        [
            SearchDecisionResult(
                action="search_more",
                next_keywords=["amount_value"],
                reasoning="keep searching",
            )
        ]
    )
    monkeypatch.setattr(field_rename_module, "get_llm", lambda: clue_llm)
    monkeypatch.setattr(runner_module, "get_llm", lambda: decision_llm)

    request = build_request()
    report = AssessmentRunner().run(request)

    assert report.coverage["search_round"] == 1
    assert report.trace.count("generated_clues") == 1
    assert "llm_decide_search:search_more" in report.trace
