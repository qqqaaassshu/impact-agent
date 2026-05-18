import re
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from impact_agent.config import get_settings
from impact_agent.models.analysis import AnalyzeRequest
from impact_agent.models.impact import Evidence, ImpactItem, ImpactReport
from impact_agent.models.tool import ToolHit
from impact_agent.orchestrator.react_runner import ReactRunner
from impact_agent.tools.code_search import search_by_symbol, search_by_text


STOP_WORDS = {
    "the",
    "and",
    "or",
    "to",
    "from",
    "with",
    "需求",
    "变更",
    "影响",
    "字段",
    "接口",
    "页面",
    "组件",
    "分析",
    "确认",
}

TOKEN_PATTERN = re.compile(r"[A-Za-z_$][\w$]*|[\u4e00-\u9fff]{2,}")


def analyze_requirement(request: AnalyzeRequest) -> ImpactReport:
    settings = get_settings()
    limit = request.limit or settings.max_tool_results
    react_result = ReactRunner().run(request.requirement)
    return build_report_from_react_result(request, react_result, limit=limit)


def stream_analyze_requirement(request: AnalyzeRequest) -> Iterator[dict[str, Any]]:
    settings = get_settings()
    limit = request.limit or settings.max_tool_results
    react_result = None

    for event in ReactRunner().stream(request.requirement):
        if event.get("type") == "result":
            react_result = event["result"]
            continue
        yield event

    if react_result is None:
        yield {
            "type": "error",
            "message": "分析流程没有返回结果。",
        }
        return

    report = build_report_from_react_result(request, react_result, limit=limit)
    yield {
        "type": "report",
        "message": "影响清单已生成。",
        "report": report.model_dump(),
    }


def build_report_from_react_result(
    request: AnalyzeRequest,
    react_result,
    *,
    limit: int,
) -> ImpactReport:
    if react_result.used_llm and react_result.hits:
        unique_hits = _dedupe_hits(react_result.hits)
        uncertain = [
            _impact_item_from_hit(hit, reason=_reason_from_hit(hit, react_result.steps))
            for hit in unique_hits[:limit]
        ]
        return ImpactReport(
            request_id=str(uuid4()),
            summary=react_result.final
            or f"ReAct 检索发现 {len(uncertain)} 个候选影响点，需进一步确认。",
            repo={"repo_root": request.repo_root} if request.repo_root else {},
            uncertain=uncertain,
            tool_trace=[
                {
                    "tool": step.action,
                    "query": step.query,
                    "reason": step.reason,
                    "result_count": step.result_count,
                }
                for step in react_result.steps
            ],
            risk_level="medium" if uncertain else "low",
            overall_confidence="low",
        )

    fallback_report = analyze_requirement_without_llm(request)
    if react_result.error:
        fallback_report.tool_trace.insert(
            0,
            {
                "tool": "react_runner",
                "query": request.requirement,
                "result_count": 0,
                "error": react_result.error,
                "fallback": True,
            },
        )
    return fallback_report


def analyze_requirement_without_llm(request: AnalyzeRequest) -> ImpactReport:
    settings = get_settings()
    limit = request.limit or settings.max_tool_results
    entities = extract_requirement_entities(request.requirement)
    hits: list[ToolHit] = []
    tool_trace: list[dict] = []

    for entity in entities:
        symbol_hits = search_by_symbol(entity, limit=limit)
        text_hits = search_by_text(entity, limit=limit)
        hits.extend(symbol_hits)
        hits.extend(text_hits)
        tool_trace.append(
            {
                "tool": "search_by_symbol/search_by_text",
                "query": entity,
                "result_count": len(symbol_hits) + len(text_hits),
            }
        )

    unique_hits = _dedupe_hits(hits)
    uncertain = [_impact_item_from_hit(hit) for hit in unique_hits[:limit]]

    return ImpactReport(
        request_id=str(uuid4()),
        summary=f"基于关键词检索发现 {len(uncertain)} 个候选影响点，需进一步确认。",
        repo={"repo_root": request.repo_root} if request.repo_root else {},
        uncertain=uncertain,
        tool_trace=tool_trace,
        risk_level="medium" if uncertain else "low",
        overall_confidence="low",
    )


def extract_requirement_entities(requirement: str) -> list[str]:
    entities: list[str] = []
    for match in TOKEN_PATTERN.finditer(requirement):
        token = match.group(0).strip()
        if len(token) < 2 or token in STOP_WORDS:
            continue
        entities.append(token)
    return list(dict.fromkeys(entities))


def _dedupe_hits(hits: list[ToolHit]) -> list[ToolHit]:
    seen: set[tuple[str, str | None, int | None, int | None]] = set()
    unique: list[ToolHit] = []
    for hit in hits:
        key = (hit.file, hit.symbol, hit.line_start, hit.line_end)
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique


def _impact_item_from_hit(
    hit: ToolHit,
    *,
    reason: str = "由最小分析链路的索引检索命中，当前阶段需人工确认。",
) -> ImpactItem:
    target = hit.symbol or hit.file
    return ImpactItem(
        file=hit.file,
        symbol=hit.symbol,
        impact_type=hit.kind,
        description=f"`{target}` 命中需求关键词，可能受本次变更影响。",
        reason=reason,
        evidence=[
            Evidence(
                file=hit.file,
                line_start=hit.line_start,
                line_end=hit.line_end,
                snippet=hit.content[:600],
                reason=reason,
            )
        ],
        confidence="low",
        needs_review=True,
    )


def _reason_from_hit(hit: ToolHit, steps) -> str:
    matched_steps = [
        step
        for step in steps
        if _query_matches_hit(str(step.query), hit)
    ]
    if not matched_steps:
        return "该位置来自 ReAct 工具检索结果，可能包含需求描述中的业务词、字段、组件或相关调用链。"

    first = matched_steps[0]
    target = hit.symbol or hit.file
    return (
        f"模型因为「{first.reason or '需求中存在相关线索'}」使用 {first.action} "
        f"检索「{first.query}」，命中了 `{target}`。因此该文件可能包含变更字段、展示逻辑、"
        "调用关系或相邻业务逻辑，需要人工确认是否受影响。"
    )


def _query_matches_hit(query: str, hit: ToolHit) -> bool:
    normalized_query = query.lower()
    haystack = " ".join(
        item
        for item in [hit.file, hit.symbol or "", hit.kind, hit.content[:1000]]
        if item
    ).lower()
    return normalized_query in haystack
