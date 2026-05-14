from typing import Any

from langgraph.graph import END, StateGraph

from impact_agent.adapters.code_source.local import LocalCodeSourceAdapter
from impact_agent.models.request import AssessmentRequest
from impact_agent.models.report import AssessmentReport
from impact_agent.models.state import AssessmentState
from impact_agent.policies.confidence import ConfidencePolicy
from impact_agent.policies.risk import RiskPolicy
from impact_agent.services.knowledge_store import append_assessment_summary, load_project_profile, load_recent_assessments
from impact_agent.services.report_builder import build_report
from impact_agent.strategies.field_rename import FieldRenameStrategy


class AssessmentRunner:
    def __init__(self) -> None:
        self.graph = self._build_graph()

    def run(self, request: AssessmentRequest) -> AssessmentReport:
        state = AssessmentState(request=request.model_dump())
        final_state = self.graph.invoke(state.model_dump())
        report = final_state["report"]
        append_assessment_summary(report)
        return report

    def _build_graph(self):
        graph = StateGraph(dict)
        graph.add_node("validate_request", self._validate_request)
        graph.add_node("load_source_snapshot", self._load_source_snapshot)
        graph.add_node("load_knowledge", self._load_knowledge)
        graph.add_node("generate_clues", self._generate_clues)
        graph.add_node("analyze_matches", self._analyze_matches)
        graph.add_node("evaluate_risk", self._evaluate_risk)
        graph.add_node("evaluate_confidence", self._evaluate_confidence)
        graph.add_node("build_report", self._build_report)
        graph.set_entry_point("validate_request")
        graph.add_edge("validate_request", "load_source_snapshot")
        graph.add_edge("load_source_snapshot", "load_knowledge")
        graph.add_edge("load_knowledge", "generate_clues")
        graph.add_edge("generate_clues", "analyze_matches")
        graph.add_edge("analyze_matches", "evaluate_risk")
        graph.add_edge("evaluate_risk", "evaluate_confidence")
        graph.add_edge("evaluate_confidence", "build_report")
        graph.add_edge("build_report", END)
        return graph.compile()

    def _validate_request(self, state: dict[str, Any]) -> dict[str, Any]:
        request = AssessmentRequest.model_validate(state["request"])
        if request.source.type != "local":
            raise ValueError("当前 MVP 只支持本地代码源")
        if request.change_type != "field_rename":
            raise ValueError("当前 MVP 只支持 field_rename")
        state["trace"] = [*state.get("trace", []), "validated_request"]
        return state

    def _load_source_snapshot(self, state: dict[str, Any]) -> dict[str, Any]:
        request = AssessmentRequest.model_validate(state["request"])
        adapter = LocalCodeSourceAdapter(request.source.root_path or "")
        state["source_snapshot"] = adapter.snapshot()
        state["trace"] = [*state.get("trace", []), "loaded_source_snapshot"]
        return state

    def _load_knowledge(self, state: dict[str, Any]) -> dict[str, Any]:
        request = AssessmentRequest.model_validate(state["request"])
        project_id = request.change_scope.module or request.source.root_path or "local-project"
        state["project_profile"] = load_project_profile(project_id)
        state["history_references"] = load_recent_assessments(project_id, request.change_scope.module, request.change_type)
        state["knowledge_used"] = {
            "project_profile_loaded": bool(state["project_profile"].get("profile_loaded", False)),
            "history_count": len(state["history_references"]),
        }
        state["trace"] = [*state.get("trace", []), "loaded_knowledge"]
        return state

    def _generate_clues(self, state: dict[str, Any]) -> dict[str, Any]:
        request = AssessmentRequest.model_validate(state["request"])
        strategy = FieldRenameStrategy()
        clues = strategy.generate_clues(request, state.get("project_profile", {}), state.get("history_references", []))
        state["searched_clues"] = clues
        state["trace"] = [*state.get("trace", []), "generated_clues"]
        return state

    def _analyze_matches(self, state: dict[str, Any]) -> dict[str, Any]:
        request = AssessmentRequest.model_validate(state["request"])
        adapter = LocalCodeSourceAdapter(request.source.root_path or "")
        strategy = FieldRenameStrategy()

        confirmed: list[dict] = []
        uncertain: list[dict] = []
        excluded: list[dict] = []
        evidence_by_id: dict[str, dict] = {}
        read_files: dict[str, str] = {}
        total_results = 0

        for clue in state.get("searched_clues", []):
            search_result = adapter.search(clue["keyword"], request.file_types, request.repo_path)
            total_results += len(search_result["results"])
            for candidate in search_result["results"]:
                read_result = adapter.read(candidate["file_path"])
                if not read_result["read_success"]:
                    decision = {
                        "status": "uncertain",
                        "reason": "file_read_failed",
                        "confidence": "low",
                        "file_path": candidate["file_path"],
                        "line_no": candidate["line_no"],
                        "code": candidate["line"],
                        "clue_category": clue["clue_category"],
                    }
                else:
                    read_files[candidate["file_path"]] = read_result["content"]
                    decision = strategy.classify_match(
                        candidate["file_path"],
                        read_result["content"],
                        clue,
                        {"candidate": candidate},
                    )

                enriched = {
                    **candidate,
                    **decision,
                }
                evidence_id = f"{clue['clue_category']}::{candidate['relative_path']}::{candidate['line_no']}"
                evidence_by_id[evidence_id] = {
                    "evidence_id": evidence_id,
                    "source_type": "local",
                    "clue_category": decision["clue_category"],
                    "decision": decision["status"],
                    "reason": decision["reason"],
                    "confidence": decision["confidence"],
                    "file_path": candidate["file_path"],
                    "line_no": candidate["line_no"],
                    "code": decision["code"],
                }
                enriched["evidence_id"] = evidence_id

                if decision["status"] == "confirmed_affected":
                    confirmed.append(enriched)
                elif decision["status"] == "uncertain":
                    uncertain.append(enriched)
                else:
                    excluded.append(enriched)

        state["confirmed_affected"] = confirmed
        state["uncertain_matches"] = uncertain
        state["excluded_matches"] = excluded
        state["read_files"] = read_files
        state["coverage"] = {
            "searched_keywords": [item["keyword"] for item in state.get("searched_clues", [])],
            "search_roots": [request.repo_path or "."],
            "total_matches": total_results,
            "confirmed_count": len(confirmed),
            "uncertain_count": len(uncertain),
            "excluded_count": len(excluded),
        }
        state["evidence_chain"] = {
            "items": list(evidence_by_id.values()),
            "count": len(evidence_by_id),
        }
        state["trace"] = [*state.get("trace", []), "analyzed_matches"]
        return state

    def _evaluate_risk(self, state: dict[str, Any]) -> dict[str, Any]:
        risk = RiskPolicy().evaluate(AssessmentState.model_validate(state))
        state["risk"] = risk
        state["trace"] = [*state.get("trace", []), "evaluated_risk"]
        return state

    def _evaluate_confidence(self, state: dict[str, Any]) -> dict[str, Any]:
        confidence = ConfidencePolicy().evaluate(AssessmentState.model_validate(state))
        state["confidence"] = confidence
        state["trace"] = [*state.get("trace", []), "evaluated_confidence"]
        return state

    def _build_report(self, state: dict[str, Any]) -> dict[str, Any]:
        state["trace"] = [*state.get("trace", []), "built_report"]
        report = build_report(AssessmentState.model_validate(state))
        state["report"] = report
        return state
