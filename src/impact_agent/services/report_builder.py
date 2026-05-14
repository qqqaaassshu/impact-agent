from impact_agent.models.report import AssessmentReport, Summary


def build_report(state) -> AssessmentReport:
    risk_level = state.risk.get("risk_level", "unknown")
    overall_confidence = state.confidence.get("overall_confidence", "low")
    needs_human_review = bool(state.uncertain_matches)

    confirmed_count = len(state.confirmed_affected)
    uncertain_count = len(state.uncertain_matches)
    excluded_count = len(state.excluded_matches)

    conclusion = (
        f"confirmed={confirmed_count}, uncertain={uncertain_count}, excluded={excluded_count}"
    )

    next_action = None
    if needs_human_review:
        next_action = "请人工复核 uncertain_matches 中的动态引用或读取失败项"
    elif confirmed_count > 0:
        next_action = "请优先处理 confirmed_affected 中的确定影响项"

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
        uncertain_matches=state.uncertain_matches,
        excluded_matches=state.excluded_matches,
        coverage=state.coverage,
        evidence_chain=state.evidence_chain,
        knowledge_used=state.knowledge_used,
        next_action=next_action,
        trace=state.trace,
    )
