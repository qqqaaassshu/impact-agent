import json
from pathlib import Path
from typing import Any

from impact_agent.config import DEFAULT_REPO_PATH, DEFAULT_ROOT_PATH
from impact_agent.models.llm import ClarificationNeeded, IntakeParseResult
from impact_agent.models.request import AssessmentRequest
from impact_agent.config import get_llm


def intake_and_normalize(raw_input: dict | str | AssessmentRequest) -> AssessmentRequest | ClarificationNeeded:
    if isinstance(raw_input, AssessmentRequest):
        return raw_input

    if isinstance(raw_input, dict):
        try:
            return AssessmentRequest.model_validate(raw_input)
        except Exception:
            return _parse_with_llm(raw_input)

    if isinstance(raw_input, str):
        stripped = raw_input.strip()
        if _looks_like_json(stripped):
            return intake_and_normalize(json.loads(stripped))
        path = Path(stripped)
        if path.exists() and path.is_file():
            content = path.read_text(encoding="utf-8")
            if _looks_like_json(content.strip()):
                return intake_and_normalize(json.loads(content))
            return _parse_with_llm(content)
        return _parse_with_llm(stripped)

    raise TypeError("raw_input must be a dict, string, or AssessmentRequest")


def _parse_with_llm(raw_input: dict[str, Any] | str) -> AssessmentRequest | ClarificationNeeded:
    llm = get_llm().with_structured_output(IntakeParseResult)
    requirement = raw_input if isinstance(raw_input, str) else json.dumps(raw_input, ensure_ascii=False)
    result = llm.invoke(
        f"""
你是需求变更影响分析系统的 intake 解析器。
请从以下输入中提取结构化字段，无法确定时返回 null，不要猜测。
如果信息明显不足以形成 field_rename 请求，请设置 needs_clarification=true 并返回问题列表。

输入：{requirement}
""".strip()
    )

    if result.needs_clarification:
        return ClarificationNeeded(questions=result.questions)

    if not result.old_name or not result.new_name:
        return ClarificationNeeded(
            questions=result.questions or ["请补充旧字段名和新字段名"]
        )

    payload = {
        "source": {
            "type": "local",
            "root_path": raw_input.get("source", {}).get("root_path") if isinstance(raw_input, dict) else DEFAULT_ROOT_PATH,
            "include_uncommitted": False,
        },
        "repo_path": result.repo_path or DEFAULT_REPO_PATH,
        "requirement": result.requirement or requirement,
        "change_type": result.change_type or "field_rename",
        "change_scope": {
            "module": result.module,
            "old_name": result.old_name,
            "new_name": result.new_name,
            "entity_kind": result.entity_kind or "api_field",
        },
    }

    if not payload["source"]["root_path"]:
        return ClarificationNeeded(questions=["请提供本地项目 root_path，或设置 REPO_ROOT_PATH 环境变量"])

    return AssessmentRequest.model_validate(payload)


def _looks_like_json(value: str) -> bool:
    return value.startswith("{") or value.startswith("[")
