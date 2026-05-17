from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from impact_agent.adapters.code_source.local import LocalCodeSourceAdapter
from impact_agent.config import LLM_CONTEXT_REVIEW_ENABLED, MAX_CONTEXT_REVIEW_ITEMS, MAX_SEARCH_ROUNDS, get_llm
from impact_agent.models.llm import SearchDecisionResult
from impact_agent.models.request import AssessmentRequest
from impact_agent.models.report import AssessmentReport
from impact_agent.models.state import AssessmentState
from impact_agent.policies.confidence import ConfidencePolicy
from impact_agent.policies.risk import RiskPolicy
from impact_agent.services.knowledge_store import append_assessment_summary, load_project_profile, load_recent_assessments
from impact_agent.services.context_review import (
    apply_context_review_decisions,
    review_context_candidates,
    select_review_candidates,
)
from impact_agent.services.report_builder import build_report
from impact_agent.strategies.field_rename import FieldRenameStrategy


class AssessmentRunner:
    def __init__(
        self,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        entrypoint: str = "api",
    ) -> None:
        self.progress_callback = progress_callback
        self.entrypoint = entrypoint
        self.graph = self._build_graph()

    def run(self, request: AssessmentRequest) -> AssessmentReport:
        state = AssessmentState(request=request.model_dump(), max_search_rounds=MAX_SEARCH_ROUNDS)
        final_state = self.graph.invoke(state.model_dump())
        report = final_state["report"]
        request_payload = request.model_dump()
        request_payload["entrypoint"] = self.entrypoint
        append_assessment_summary(report, request_payload)
        return report

    def _build_graph(self):
        graph = StateGraph(dict)
        graph.add_node("validate_request", self._validate_request)
        graph.add_node("load_source_snapshot", self._load_source_snapshot)
        graph.add_node("load_knowledge", self._load_knowledge)
        graph.add_node("generate_clues", self._generate_clues)
        graph.add_node("analyze_matches", self._analyze_matches)
        graph.add_node("decide_search_next_step", self._decide_search_next_step)
        graph.add_node("review_special_contexts", self._review_special_contexts)
        graph.add_node("evaluate_risk", self._evaluate_risk)
        graph.add_node("evaluate_confidence", self._evaluate_confidence)
        graph.add_node("build_report", self._build_report)
        graph.set_entry_point("validate_request")
        graph.add_edge("validate_request", "load_source_snapshot")
        graph.add_edge("load_source_snapshot", "load_knowledge")
        graph.add_edge("load_knowledge", "generate_clues")
        graph.add_edge("generate_clues", "analyze_matches")
        graph.add_edge("analyze_matches", "decide_search_next_step")
        graph.add_conditional_edges(
            "decide_search_next_step",
            self._should_continue_search,
            {
                "search_more": "generate_clues",
                "finish": "review_special_contexts",
            },
        )
        graph.add_edge("review_special_contexts", "evaluate_risk")
        graph.add_edge("evaluate_risk", "evaluate_confidence")
        graph.add_edge("evaluate_confidence", "build_report")
        graph.add_edge("build_report", END)
        return graph.compile()

    def _validate_request(self, state: dict[str, Any]) -> dict[str, Any]:
        self._emit_progress("validate_request", "校验输入", "正在校验工程路径、代码源类型和变更类型")
        request = AssessmentRequest.model_validate(state["request"])
        if request.source.type != "local":
            raise ValueError("当前 MVP 只支持本地代码源")
        if request.change_type != "field_rename":
            raise ValueError("当前 MVP 只支持字段变更")
        state["trace"] = [*state.get("trace", []), {"node": "validate_request"}]
        return state

    def _load_source_snapshot(self, state: dict[str, Any]) -> dict[str, Any]:
        self._emit_progress("load_source_snapshot", "读取代码源快照", "正在读取本地仓库信息和 Git 状态")
        request = AssessmentRequest.model_validate(state["request"])
        adapter = LocalCodeSourceAdapter(request.source.root_path or "")
        state["source_snapshot"] = adapter.snapshot()
        state["trace"] = [*state.get("trace", []), {"node": "load_source_snapshot"}]
        return state

    def _load_knowledge(self, state: dict[str, Any]) -> dict[str, Any]:
        self._emit_progress("load_knowledge", "读取知识上下文", "正在加载项目画像、历史分析记录和人工反馈")
        request = AssessmentRequest.model_validate(state["request"])
        project_id = request.change_scope.module or request.source.root_path or "local-project"
        state["project_profile"] = load_project_profile(project_id)
        state["history_references"] = load_recent_assessments(project_id, request.change_scope.module, request.change_type)
        state["knowledge_used"] = {
            "project_profile_loaded": bool(state["project_profile"].get("profile_loaded", False)),
            "history_count": len(state["history_references"]),
        }
        state["trace"] = [
            *state.get("trace", []),
            {"node": "load_knowledge", "history_count": len(state["history_references"])},
        ]
        return state

    def _generate_clues(self, state: dict[str, Any]) -> dict[str, Any]:
        round_no = state.get("search_round", 0) + 1
        self._emit_progress("generate_clues", "生成检索线索", f"正在生成第 {round_no} 轮字段关键词和变体")
        request = AssessmentRequest.model_validate(state["request"])
        strategy = FieldRenameStrategy(progress_callback=self.progress_callback)
        if state.get("pending_clues"):
            clues = state["pending_clues"]
            state["pending_clues"] = []
        else:
            clues = strategy.generate_clues(request, state.get("project_profile", {}), state.get("history_references", []))
        state["searched_clues"] = clues
        state["search_round"] = state.get("search_round", 0) + 1
        state["trace"] = [
            *state.get("trace", []),
            {
                "node": "generate_clues",
                "search_round": state["search_round"],
                "keywords": [item["keyword"] for item in clues],
            },
        ]
        return state

    def _analyze_matches(self, state: dict[str, Any]) -> dict[str, Any]:
        self._emit_progress("analyze_matches", "扫描并分析命中", "正在检索前端代码并判断确定影响、不确定和排除项")
        request = AssessmentRequest.model_validate(state["request"])
        adapter = LocalCodeSourceAdapter(request.source.root_path or "")
        strategy = FieldRenameStrategy(progress_callback=self.progress_callback)

        confirmed: list[dict] = list(state.get("confirmed_affected", []))
        uncertain: list[dict] = list(state.get("uncertain", []))
        excluded: list[dict] = list(state.get("excluded", []))
        relations: list[dict] = list(state.get("relations", []))
        evidence_by_id = {
            item["evidence_id"]: item for item in state.get("evidence_chain", {}).get("items", []) if item.get("evidence_id")
        }
        read_files: dict[str, str] = dict(state.get("read_files", {}))
        total_results = state.get("coverage", {}).get("total_matches", 0)

        clues = state.get("searched_clues", [])
        clues_by_keyword = {clue["keyword"]: clue for clue in clues}
        search_result = adapter.search_many([clue["keyword"] for clue in clues], request.file_types, request.repo_path)
        state["trace"] = [
            *state.get("trace", []),
            {
                "node": "skill_act",
                "skill": "frontend-impact-search",
                "action": "local_search_many",
                "keywords": search_result.get("keywords", []),
                "search_engine": search_result.get("search_engine"),
                "scanned_files": search_result.get("scanned_files", 0),
            },
        ]

        for keyword, candidates in search_result.get("results_by_keyword", {}).items():
            clue = clues_by_keyword.get(keyword)
            if not clue:
                continue
            total_results += len(candidates)
            for candidate in candidates:
                evidence_id = f"{clue['clue_category']}::{candidate['relative_path']}::{candidate['line_no']}"
                if evidence_id in evidence_by_id:
                    continue
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

                enriched = {**candidate, **decision, "evidence_id": evidence_id}
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

                if decision["status"] == "confirmed_affected":
                    confirmed.append(enriched)
                elif decision["status"] == "uncertain":
                    uncertain.append(enriched)
                else:
                    excluded.append(enriched)

                if read_result["read_success"]:
                    for relation in strategy.collect_relations(
                        candidate,
                        {
                            "content": read_result["content"],
                            "clue": clue,
                            "decision": decision,
                            "evidence_id": evidence_id,
                        },
                    ):
                        relation_evidence_id = f"propagation::{evidence_id}::{relation['line_no']}"
                        if relation_evidence_id in evidence_by_id:
                            continue
                        relation_enriched = {**relation, "evidence_id": relation_evidence_id}
                        relations.append(relation_enriched)
                        uncertain.append(relation_enriched)
                        evidence_by_id[relation_evidence_id] = {
                            "evidence_id": relation_evidence_id,
                            "source_type": "local",
                            "clue_category": relation["clue_category"],
                            "decision": relation["status"],
                            "reason": relation["reason"],
                            "confidence": relation["confidence"],
                            "file_path": relation["file_path"],
                            "line_no": relation["line_no"],
                            "code": relation["code"],
                            "source_evidence_id": relation.get("source_evidence_id"),
                            "propagated_symbol": relation.get("propagated_symbol"),
                        }

        state["confirmed_affected"] = confirmed
        state["uncertain"] = uncertain
        state["excluded"] = excluded
        state["relations"] = relations
        state["read_files"] = read_files
        state["coverage"] = {
            "searched_keywords": [item["keyword"] for item in state.get("searched_clues", [])],
            "search_roots": [request.repo_path or "."],
            "total_matches": total_results,
            "derived_relation_count": len(relations),
            "confirmed_count": len(confirmed),
            "uncertain_count": len(uncertain),
            "excluded_count": len(excluded),
            "search_round": state.get("search_round", 1),
        }
        state["total_candidate_count"] = total_results
        state["evidence_chain"] = {
            "items": list(evidence_by_id.values()),
            "count": len(evidence_by_id),
        }
        state["trace"] = [
            *state.get("trace", []),
            {
                "node": "analyze_matches",
                "confirmed_count": len(confirmed),
                "uncertain_count": len(uncertain),
                "excluded_count": len(excluded),
                "derived_relation_count": len(relations),
                "ast_analyzed_files": strategy.ast_analyzed_file_count,
            },
        ]
        return state

    def _decide_search_next_step(self, state: dict[str, Any]) -> dict[str, Any]:
        self._emit_progress("decide_search_next_step", "判断是否继续检索", "正在根据当前证据决定是否追加关键词")
        if state.get("total_candidate_count", 0) > 0 and not state.get("force_llm_search_decision"):
            result = SearchDecisionResult(action="finish", next_keywords=[], reasoning="已命中候选代码，优先返回当前证据")
            state["llm_decisions"] = [
                *state.get("llm_decisions", []),
                {"node": "decide_search_next_step", "result": result.model_dump(), "source": "deterministic"},
            ]
            state["trace"] = [
                *state.get("trace", []),
                {
                    "node": "decide_search_next_step",
                    "action": result.action,
                    "reasoning": result.reasoning,
                    "next_keywords": result.next_keywords,
                },
            ]
            return state

        llm = get_llm().with_structured_output(SearchDecisionResult)
        result = llm.invoke(
            f"""
你是代码影响分析 agent 的搜索决策器。
请根据当前搜索状态判断是否继续搜索更多关键词。
如果证据已经足够，action 返回 finish。
如果还需要继续，action 返回 search_more，并给出 next_keywords。

search_round: {state.get('search_round', 0)}
max_search_rounds: {state.get('max_search_rounds', MAX_SEARCH_ROUNDS)}
searched_keywords: {[item['keyword'] for item in state.get('searched_clues', [])]}
confirmed_count: {len(state.get('confirmed_affected', []))}
uncertain_count: {len(state.get('uncertain', []))}
excluded_count: {len(state.get('excluded', []))}
""".strip()
        )
        decision = {"node": "decide_search_next_step", "result": result.model_dump()}
        state["llm_decisions"] = [*state.get("llm_decisions", []), decision]
        if result.action == "search_more":
            state["pending_clues"] = [
                {
                    "keyword": keyword,
                    "clue_category": "llm_variant",
                    "reason": result.reasoning or "llm decided to continue search",
                    "source": "llm",
                }
                for keyword in result.next_keywords
                if keyword
            ]
        state["trace"] = [
            *state.get("trace", []),
            {
                "node": "decide_search_next_step",
                "action": result.action,
                "reasoning": result.reasoning,
                "next_keywords": result.next_keywords,
            },
        ]
        return state

    def _should_continue_search(self, state: dict[str, Any]) -> str:
        if state.get("search_round", 0) >= state.get("max_search_rounds", MAX_SEARCH_ROUNDS):
            return "finish"
        if state.get("pending_clues"):
            return "search_more"
        return "finish"

    def _review_special_contexts(self, state: dict[str, Any]) -> dict[str, Any]:
        if not LLM_CONTEXT_REVIEW_ENABLED:
            state["trace"] = [
                *state.get("trace", []),
                {"node": "review_special_contexts", "reviewed_count": 0, "skipped": "disabled"},
            ]
            return state

        candidates = select_review_candidates(state, MAX_CONTEXT_REVIEW_ITEMS)
        self._emit_progress(
            "review_special_contexts",
            "特殊场景复核",
            f"正在复核 {len(candidates)} 个变量传递、动态引用或上下文不确定场景",
        )
        if not candidates:
            state["trace"] = [*state.get("trace", []), {"node": "review_special_contexts", "reviewed_count": 0}]
            return state

        self._emit_progress(
            "llm_context_review",
            "调用大模型复核特殊上下文",
            f"正在调用大模型复核 {len(candidates)} 个已命中的高风险上下文",
        )
        request = AssessmentRequest.model_validate(state["request"])
        decisions = review_context_candidates(request, candidates)
        state = apply_context_review_decisions(state, decisions)
        state["trace"] = [
            *state.get("trace", []),
            {
                "node": "review_special_contexts",
                "candidate_count": len(candidates),
                "reviewed_count": len(decisions),
                "max_review_items": MAX_CONTEXT_REVIEW_ITEMS,
            },
        ]
        return state

    def _evaluate_risk(self, state: dict[str, Any]) -> dict[str, Any]:
        self._emit_progress("evaluate_risk", "评估风险", "正在根据确定项和不确定项计算风险等级")
        risk = RiskPolicy().evaluate(AssessmentState.model_validate(state))
        state["risk"] = risk
        state["trace"] = [*state.get("trace", []), {"node": "evaluate_risk", **risk}]
        return state

    def _evaluate_confidence(self, state: dict[str, Any]) -> dict[str, Any]:
        self._emit_progress("evaluate_confidence", "评估置信度", "正在评估整体结论可信度")
        confidence = ConfidencePolicy().evaluate(AssessmentState.model_validate(state))
        state["confidence"] = confidence
        state["trace"] = [*state.get("trace", []), {"node": "evaluate_confidence", **confidence}]
        return state

    def _build_report(self, state: dict[str, Any]) -> dict[str, Any]:
        self._emit_progress("build_report", "生成报告", "正在整理摘要、覆盖范围和证据链")
        state["trace"] = [*state.get("trace", []), {"node": "build_report"}]
        report = build_report(AssessmentState.model_validate(state))
        state["report"] = report
        return state

    def _emit_progress(self, stage: str, title: str, message: str, **extra: Any) -> None:
        if not self.progress_callback:
            return
        self.progress_callback(
            {
                "stage": stage,
                "title": title,
                "message": message,
                **extra,
            }
        )
