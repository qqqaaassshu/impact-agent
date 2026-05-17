import json
import re
from pathlib import Path
from collections.abc import Callable
from typing import Any

from impact_agent.config import DEFAULT_REPO_PATH, DEFAULT_ROOT_PATH
from impact_agent.models.llm import ClarificationNeeded, IntakeParseResult, UnsupportedRequest
from impact_agent.models.request import AssessmentRequest
from impact_agent.config import get_llm


ProgressCallback = Callable[[dict[str, Any]], None] | None


def intake_and_normalize(
    raw_input: dict | str | AssessmentRequest,
    progress_callback: ProgressCallback = None,
) -> AssessmentRequest | ClarificationNeeded | UnsupportedRequest:
    if isinstance(raw_input, AssessmentRequest):
        if raw_input.change_type == "field_rename":
            return _reject_unsupported_source(raw_input) or raw_input
        return _parse_with_llm(raw_input.model_dump(), progress_callback)

    if isinstance(raw_input, dict):
        try:
            request = AssessmentRequest.model_validate(raw_input)
            if request.change_type == "field_rename":
                return _reject_unsupported_source(request) or request
            return _parse_with_llm(raw_input, progress_callback)
        except Exception:
            parsed = _parse_field_rename_locally(raw_input)
            if parsed is not None:
                return _reject_unsupported_source(parsed) or parsed
            return _parse_with_llm(raw_input, progress_callback)

    if isinstance(raw_input, str):
        stripped = raw_input.strip()
        if _looks_like_json(stripped):
            return intake_and_normalize(json.loads(stripped), progress_callback)
        path = Path(stripped)
        if path.exists() and path.is_file():
            content = path.read_text(encoding="utf-8")
            if _looks_like_json(content.strip()):
                return intake_and_normalize(json.loads(content), progress_callback)
            parsed = _parse_field_rename_locally(content)
            if parsed is not None:
                return _reject_unsupported_source(parsed) or parsed
            return _parse_with_llm(content, progress_callback)
        parsed = _parse_field_rename_locally(stripped)
        if parsed is not None:
            return _reject_unsupported_source(parsed) or parsed
        return _parse_with_llm(stripped, progress_callback)

    raise TypeError("raw_input must be a dict, string, or AssessmentRequest")


def _parse_with_llm(
    raw_input: dict[str, Any] | str,
    progress_callback: ProgressCallback = None,
) -> AssessmentRequest | ClarificationNeeded | UnsupportedRequest:
    if progress_callback:
        progress_callback(
            {
                "stage": "llm_intake",
                "title": "调用大模型判断需求",
                "message": "当前输入无法用本地规则直接确认，正在调用大模型判断是否支持该需求",
            }
        )
    llm = get_llm().with_structured_output(IntakeParseResult)
    requirement = raw_input if isinstance(raw_input, str) else json.dumps(raw_input, ensure_ascii=False)
    result = llm.invoke(
        f"""
你是需求变更影响分析系统的 intake 解析器。
请从以下输入中提取结构化字段，无法确定时返回 null，不要猜测。
当前系统只支持字段改名 field_rename。
如果需求不是字段改名，请判断它属于 feature_change 或其他不支持类型，不要强行转换成 field_rename。
如果信息不足以判断是否为字段改名，设置 needs_clarification=true 并返回问题列表。

输入：{requirement}
""".strip()
    )

    if result.needs_clarification:
        return ClarificationNeeded(questions=result.questions)

    if result.change_type and result.change_type != "field_rename":
        return UnsupportedRequest(
            reason=f"当前版本只支持字段变更分析，暂不支持“{_display_change_type(result.change_type)}”",
        )

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
            "repo_path": result.repo_path or DEFAULT_REPO_PATH or None,
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

    request = AssessmentRequest.model_validate(payload)
    return _reject_unsupported_source(request) or request


def _looks_like_json(value: str) -> bool:
    return value.startswith("{") or value.startswith("[")


def _parse_field_rename_locally(raw_input: dict[str, Any] | str) -> AssessmentRequest | None:
    if isinstance(raw_input, dict):
        requirement = str(raw_input.get("requirement") or raw_input.get("message") or "")
        root_path = raw_input.get("source", {}).get("root_path") or raw_input.get("root_path") or DEFAULT_ROOT_PATH
        repo_path = raw_input.get("repo_path") or DEFAULT_REPO_PATH or None
        file_types = raw_input.get("file_types")
    else:
        requirement = raw_input
        root_path = DEFAULT_ROOT_PATH
        repo_path = DEFAULT_REPO_PATH or None
        file_types = None

    parsed = _extract_field_rename(requirement)
    if not parsed:
        return None
    old_name, new_name = parsed
    if not root_path:
        return None

    return AssessmentRequest.model_validate(
        {
            "source": {"type": "local", "root_path": root_path, "include_uncommitted": False},
            "repo_path": repo_path,
            "requirement": requirement,
            "change_type": "field_rename",
            "change_scope": {
                "old_name": old_name,
                "new_name": new_name,
                "entity_kind": "api_field",
            },
            "file_types": file_types or [],
        }
    )


def _extract_field_rename(requirement: str) -> tuple[str, str] | None:
    patterns = [
        r"(?:从|把|将)\s*[`'\"]?([A-Za-z_$][\w$.-]*)[`'\"]?\s*(?:改为|改成|修改为|变更为|替换为|rename\s+to)\s*[`'\"]?([A-Za-z_$][\w$.-]*)[`'\"]?",
        r"[`'\"]?([A-Za-z_$][\w$.-]*)[`'\"]?\s*(?:->|=>|改为|改成|修改为|变更为|替换为)\s*[`'\"]?([A-Za-z_$][\w$.-]*)[`'\"]?",
        r"rename\s+[`'\"]?([A-Za-z_$][\w$.-]*)[`'\"]?\s+to\s+[`'\"]?([A-Za-z_$][\w$.-]*)[`'\"]?",
    ]
    for pattern in patterns:
        match = re.search(pattern, requirement, flags=re.IGNORECASE)
        if not match:
            continue
        old_name, new_name = match.group(1), match.group(2)
        if old_name != new_name:
            return old_name, new_name
    return None


def _reject_unsupported_source(request: AssessmentRequest) -> UnsupportedRequest | None:
    if request.source.type != "local":
        return UnsupportedRequest(
            reason=f"当前版本只支持本地代码源，暂不支持“{request.source.type}”代码源",
        )
    return None


def _display_change_type(change_type: str) -> str:
    labels = {
        "field_rename": "字段变更",
        "feature_change": "功能变更",
    }
    return labels.get(change_type, change_type)
