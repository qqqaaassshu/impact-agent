from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from impact_agent.config import get_settings
from impact_agent.models.tool import ToolHit
from impact_agent.providers.base import ChatProvider
from impact_agent.providers.openai_compatible import OpenAICompatibleChatProvider
from impact_agent.tools.code_search import search_by_file, search_by_symbol, search_by_text, search_by_usage


SYSTEM_PROMPT = """
你是前端代码变更影响范围分析 Agent。
你必须通过工具检索代码证据，不要凭空下结论。

每次只返回 JSON，不要返回 markdown。
JSON 格式：
{
  "action": "search_by_symbol" | "search_by_text" | "search_by_file" | "search_by_usage" | "finish",
  "query": "工具查询参数",
  "reason": "为什么选择这个动作",
  "final": "当 action=finish 时填写总结，否则为空"
}

分析原则：
- 先找用户需求中的关键字段、函数、组件、接口名。
- 找到定义后，继续找使用方和相关文件。
- 如果没有更多有价值的检索，返回 finish。
- 所有最终影响都必须来自工具结果。
"""


@dataclass
class ReactStep:
    action: str
    query: str
    reason: str
    result_count: int


@dataclass
class ReactResult:
    hits: list[ToolHit] = field(default_factory=list)
    steps: list[ReactStep] = field(default_factory=list)
    final: str = ""
    used_llm: bool = False
    error: str | None = None


class ReactRunner:
    def __init__(self, provider: ChatProvider | None = None) -> None:
        self.settings = get_settings()
        self.provider = provider or OpenAICompatibleChatProvider(self.settings)

    def run(self, requirement: str) -> ReactResult:
        result = ReactResult(used_llm=False, final="ReAct 未产生结果。")
        for event in self.stream(requirement):
            if event.get("type") == "result":
                return event["result"]
        return result

    def stream(self, requirement: str) -> Iterator[dict[str, Any]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": requirement},
        ]
        result = ReactResult(used_llm=True)
        visited: set[tuple[str, str]] = set()

        try:
            yield {
                "type": "phase",
                "message": "开始分析需求，准备让模型拆解检索路径。",
            }
            for iteration in range(self.settings.max_react_iteration):
                yield {
                    "type": "thinking",
                    "message": f"第 {iteration + 1} 轮：模型正在决定下一步检索动作。",
                }
                decision = self.provider.complete_json(messages)
                action = str(decision.get("action", "finish"))
                query = str(decision.get("query", "")).strip()
                reason = str(decision.get("reason", ""))

                if action == "finish":
                    result.final = str(decision.get("final", ""))
                    yield {
                        "type": "finish",
                        "message": result.final or "模型判断没有更多有价值的检索动作。",
                    }
                    yield {"type": "result", "result": result}
                    return

                if not query:
                    result.final = "模型未提供有效查询，停止 ReAct。"
                    yield {"type": "finish", "message": result.final}
                    yield {"type": "result", "result": result}
                    return

                key = (action, query)
                if key in visited:
                    result.final = "检测到重复查询，停止 ReAct。"
                    yield {"type": "finish", "message": result.final}
                    yield {"type": "result", "result": result}
                    return
                visited.add(key)

                yield {
                    "type": "tool_start",
                    "action": action,
                    "query": query,
                    "reason": reason,
                    "message": f"调用 {action} 检索：{query}",
                }
                hits = _run_tool(action, query, self.settings.max_tool_results)
                result.hits.extend(hits)
                result.steps.append(
                    ReactStep(action=action, query=query, reason=reason, result_count=len(hits))
                )
                yield {
                    "type": "tool_result",
                    "action": action,
                    "query": query,
                    "reason": reason,
                    "result_count": len(hits),
                    "hits": _compact_hits(hits, limit=5),
                    "message": f"{action} 命中 {len(hits)} 条结果。",
                }
                messages.append({"role": "assistant", "content": _decision_to_json(decision)})
                messages.append(
                    {
                        "role": "user",
                        "content": _observation_message(action=action, query=query, hits=hits),
                    }
                )

            result.final = "达到最大 ReAct 轮次，停止分析。"
            yield {"type": "finish", "message": result.final}
            yield {"type": "result", "result": result}
        except Exception as exc:
            result.used_llm = False
            result.error = str(exc)
            yield {
                "type": "error",
                "message": f"ReAct 执行失败，将切换到本地关键词检索：{result.error}",
                "error": result.error,
            }
            yield {"type": "result", "result": result}


def _run_tool(action: str, query: str, limit: int) -> list[ToolHit]:
    if action == "search_by_symbol":
        return search_by_symbol(query, limit=limit)
    if action == "search_by_text":
        return search_by_text(query, limit=limit)
    if action == "search_by_file":
        return search_by_file(query, limit=limit)
    if action == "search_by_usage":
        return search_by_usage(query, limit=limit)
    return []


def _decision_to_json(decision: dict[str, Any]) -> str:
    import json

    return json.dumps(decision, ensure_ascii=False)


def _observation_message(*, action: str, query: str, hits: list[ToolHit]) -> str:
    compact_hits = _compact_hits(hits, limit=8, content_limit=500)
    return _decision_to_json(
        {
            "observation": {
                "tool": action,
                "query": query,
                "result_count": len(hits),
                "hits": compact_hits,
            }
        }
    )


def _compact_hits(
    hits: list[ToolHit],
    *,
    limit: int,
    content_limit: int = 240,
) -> list[dict[str, Any]]:
    return [
        {
            "file": hit.file,
            "symbol": hit.symbol,
            "kind": hit.kind,
            "line_start": hit.line_start,
            "line_end": hit.line_end,
            "content": hit.content[:content_limit],
        }
        for hit in hits[:limit]
    ]
