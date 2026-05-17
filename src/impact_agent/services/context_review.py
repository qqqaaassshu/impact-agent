from impact_agent.config import get_llm
from impact_agent.models.llm import ContextReviewResult


REVIEWABLE_REASONS = {
    "dynamic_field_reference",
    "variable_propagation_reference",
    "file_read_failed",
}


def select_review_candidates(state: dict, limit: int) -> list[dict]:
    candidates: list[dict] = []
    read_files: dict[str, str] = state.get("read_files", {})
    for item in state.get("uncertain", []):
        if item.get("reason") not in REVIEWABLE_REASONS:
            continue
        content = read_files.get(item.get("file_path", ""))
        if not content:
            continue
        candidates.append(
            {
                **item,
                "context": build_context(content, int(item.get("line_no") or 1)),
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def review_context_candidates(request, candidates: list[dict]) -> dict[str, dict]:
    if not candidates:
        return {}

    evidence_payload = [
        {
            "evidence_id": item.get("evidence_id"),
            "file_path": item.get("relative_path") or item.get("file_path"),
            "line_no": item.get("line_no"),
            "code": item.get("code") or item.get("line"),
            "reason": item.get("reason"),
            "context": item.get("context"),
        }
        for item in candidates
    ]

    llm = get_llm().with_structured_output(ContextReviewResult)
    result = llm.invoke(
        f"""
你是前端字段变更影响范围复核助手。
当前只允许你判断给定 evidence，不允许新增文件、不允许新增 evidence_id。
如果上下文能证明字段变更会沿变量、配置、props、函数参数继续影响该 evidence，status 返回 confirmed_affected。
如果上下文能证明只是普通文案、无关变量或非字段语义，status 返回 excluded。
如果证据不足，status 返回 uncertain。

字段变更需求：{request.requirement}
旧字段名：{request.change_scope.old_name}
新字段名：{request.change_scope.new_name}

待复核 evidence：
{evidence_payload}
""".strip()
    )

    allowed_ids = {item.get("evidence_id") for item in candidates}
    decisions: dict[str, dict] = {}
    for decision in result.decisions:
        if decision.evidence_id not in allowed_ids:
            continue
        if decision.status not in {"confirmed_affected", "excluded", "uncertain"}:
            continue
        decisions[decision.evidence_id] = decision.model_dump()
    return decisions


def apply_context_review_decisions(state: dict, decisions: dict[str, dict]) -> dict:
    if not decisions:
        return state

    confirmed = list(state.get("confirmed_affected", []))
    uncertain = []
    excluded = list(state.get("excluded", []))
    evidence_items = list(state.get("evidence_chain", {}).get("items", []))

    for item in state.get("uncertain", []):
        evidence_id = item.get("evidence_id")
        decision = decisions.get(evidence_id)
        if not decision:
            uncertain.append(item)
            continue

        updated = {
            **item,
            "status": decision["status"],
            "reason": decision["reason"],
            "confidence": decision.get("confidence", "medium"),
            "review_source": "llm_context_review",
        }
        if decision["status"] == "confirmed_affected":
            confirmed.append(updated)
        elif decision["status"] == "excluded":
            excluded.append(updated)
        else:
            uncertain.append(updated)

    for evidence in evidence_items:
        decision = decisions.get(evidence.get("evidence_id"))
        if not decision:
            continue
        evidence["decision"] = decision["status"]
        evidence["reason"] = decision["reason"]
        evidence["confidence"] = decision.get("confidence", "medium")
        evidence["review_source"] = "llm_context_review"

    state["confirmed_affected"] = confirmed
    state["uncertain"] = uncertain
    state["excluded"] = excluded
    state["evidence_chain"] = {
        **state.get("evidence_chain", {}),
        "items": evidence_items,
        "count": len(evidence_items),
    }
    return state


def build_context(content: str, line_no: int, radius: int = 8) -> str:
    lines = content.splitlines()
    start = max(0, line_no - radius - 1)
    end = min(len(lines), line_no + radius)
    return "\n".join(f"{index + 1}: {lines[index]}" for index in range(start, end))
