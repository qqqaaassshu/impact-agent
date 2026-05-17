from impact_agent.models.report import AssessmentReport, Summary


def build_report(state) -> AssessmentReport:
    risk_level = state.risk.get("risk_level", "unknown")
    overall_confidence = state.confidence.get("overall_confidence", "low")
    needs_human_review = bool(state.uncertain)

    confirmed_count = len(state.confirmed_affected)
    uncertain_count = len(state.uncertain)
    excluded_count = len(state.excluded)

    conclusion = f"确定影响 {confirmed_count} 项，不确定 {uncertain_count} 项，已排除 {excluded_count} 项"

    next_action = None
    if needs_human_review:
        next_action = "请人工复核“不确定项”中的动态引用或读取失败项"
    elif confirmed_count > 0:
        next_action = "请优先处理“确定影响项”中的结果"

    summary = Summary(
        requirement=state.request["requirement"],
        change_type=state.request["change_type"],
        risk_level=risk_level,
        overall_confidence=overall_confidence,
        needs_human_review=needs_human_review,
        conclusion=conclusion,
        source_snapshot=state.source_snapshot,
    )

    return AssessmentReport(
        summary=summary,
        confirmed_affected=state.confirmed_affected,
        uncertain=state.uncertain,
        excluded=state.excluded,
        coverage=state.coverage,
        evidence_chain=state.evidence_chain,
        knowledge_used=state.knowledge_used,
        next_action=next_action,
        trace=state.trace,
    )
