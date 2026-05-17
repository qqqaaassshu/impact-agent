from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


SUPPORTED_AST_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
CONFIG_FIELD_NAMES = {"dataIndex", "field", "fieldName", "key", "name", "prop"}


def analyze_javascript_ast(file_path: str, content: str, field_name: str) -> dict[str, Any]:
    """Return structured field usage and binding signals for JS/TS files.

    The primary engine uses the TypeScript compiler API through a small Node
    script. If Node or TypeScript is unavailable, a conservative Python
    structural fallback keeps the feature usable without adding dependencies.
    """

    if not _ast_analysis_enabled():
        return _empty_result("disabled")

    suffix = Path(file_path).suffix.lower()
    if suffix not in SUPPORTED_AST_SUFFIXES:
        return _empty_result("unsupported_file_type")

    if _ast_engine() in {"auto", "typescript"}:
        result = _run_typescript_ast(file_path, content, field_name)
        if result.get("available"):
            return result
        if _ast_engine() == "typescript":
            return result

    fallback = _analyze_with_python_structure(content, field_name)
    fallback["available"] = True
    fallback["engine"] = "python_structure"
    return fallback


def find_usage_on_line(analysis: dict[str, Any], line_no: int) -> dict[str, Any] | None:
    usages = [item for item in analysis.get("usages", []) if item.get("line_no") == line_no]
    if not usages:
        return None
    return sorted(usages, key=_usage_priority)[0]


def bound_symbols_on_line(analysis: dict[str, Any], line_no: int) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    seen: set[str] = set()
    for binding in analysis.get("bindings", []):
        symbol = binding.get("symbol")
        if binding.get("line_no") != line_no or not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(binding)
    return symbols


def _run_typescript_ast(file_path: str, content: str, field_name: str) -> dict[str, Any]:
    node_path = shutil.which("node")
    if not node_path:
        return _empty_result("node_not_found")

    script_path = Path(__file__).resolve().parents[3] / "skills" / "frontend-impact-search" / "scripts" / "ts_ast_extract.mjs"
    if not script_path.exists():
        return _empty_result("typescript_ast_script_not_found")

    payload = json.dumps(
        {
            "filePath": file_path,
            "content": content,
            "fieldName": field_name,
        },
        ensure_ascii=False,
    )
    timeout = float(os.getenv("AST_ANALYSIS_TIMEOUT_SECONDS", "3"))

    try:
        completed = subprocess.run(
            [node_path, str(script_path)],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        return _empty_result(f"typescript_ast_failed:{exc}")

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "typescript_ast_non_zero_exit"
        return _empty_result(message)

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return _empty_result(f"typescript_ast_invalid_json:{exc}")

    return _normalize_result(result, "typescript")


def _analyze_with_python_structure(content: str, field_name: str) -> dict[str, Any]:
    usages: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    seen_usages: set[tuple[int, str]] = set()
    seen_bindings: set[tuple[int, str, str]] = set()
    in_type_block = False
    type_depth = 0

    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or _is_comment_line(line):
            continue

        starts_type_block = bool(re.search(r"\b(?:interface|type)\s+\w+.*\{", line))
        if starts_type_block:
            in_type_block = True
            type_depth += _brace_delta(line)

        for usage_type in _line_usage_types(line, field_name, in_type_block):
            key = (line_no, usage_type)
            if key not in seen_usages:
                seen_usages.add(key)
                usages.append(
                    {
                        "line_no": line_no,
                        "usage_type": usage_type,
                        "confidence": "high",
                        "engine": "python_structure",
                    }
                )

        for binding in _line_bindings(line, field_name):
            key = (line_no, binding["symbol"], binding["binding_type"])
            if key not in seen_bindings:
                seen_bindings.add(key)
                bindings.append(
                    {
                        "line_no": line_no,
                        "confidence": "medium",
                        "engine": "python_structure",
                        **binding,
                    }
                )

        if in_type_block and not starts_type_block:
            type_depth += _brace_delta(line)
        if in_type_block and type_depth <= 0:
            in_type_block = False
            type_depth = 0

    return {"usages": usages, "bindings": bindings, "errors": []}


def _line_usage_types(line: str, field_name: str, in_type_block: bool) -> list[str]:
    escaped = re.escape(field_name)
    usage_types: list[str] = []

    if re.search(rf"\.\s*{escaped}(?![\w$])", line):
        usage_types.append("object_property")
    if re.search(rf"\[\s*['\"]{escaped}['\"]\s*\]", line):
        usage_types.append("bracket_property")

    field_key_pattern = rf"(?<![\w$]){escaped}(?![\w$])\s*\??\s*:"
    if re.search(field_key_pattern, line):
        usage_types.append("type_field" if in_type_block else "object_field")

    quoted = rf"['\"]{escaped}['\"]"
    config_name_pattern = "|".join(re.escape(name) for name in CONFIG_FIELD_NAMES)
    if re.search(rf"\b(?:{config_name_pattern})\b\s*:\s*{quoted}", line):
        usage_types.append("config_field")
    if re.search(rf"\b(?:{config_name_pattern})\b\s*=\s*{quoted}", line):
        usage_types.append("config_field")

    destructuring = _match_destructuring_binding(line, field_name)
    if destructuring:
        usage_types.append("destructuring_alias" if destructuring != field_name else "destructuring_property")

    return list(dict.fromkeys(usage_types))


def _line_bindings(line: str, field_name: str) -> list[dict[str, str]]:
    escaped = re.escape(field_name)
    bindings: list[dict[str, str]] = []

    for pattern, binding_type in (
        (rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*['\"]{escaped}['\"]", "string_literal"),
        (rf"\b([A-Za-z_$][\w$]*)\s*=\s*['\"]{escaped}['\"]", "string_literal"),
        (rf"\b([A-Za-z_$][\w$]*)\s*:\s*['\"]{escaped}['\"]", "string_config"),
        (rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*[^;]*\.\s*{escaped}(?![\w$])", "property_access"),
        (
            rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*[^;]*\[\s*['\"]{escaped}['\"]\s*\]",
            "bracket_property",
        ),
    ):
        for match in re.finditer(pattern, line):
            bindings.append(
                {
                    "symbol": match.group(1),
                    "property_name": field_name,
                    "binding_type": binding_type,
                }
            )

    destructuring_symbol = _match_destructuring_binding(line, field_name)
    if destructuring_symbol:
        bindings.append(
            {
                "symbol": destructuring_symbol,
                "property_name": field_name,
                "binding_type": "destructuring_alias" if destructuring_symbol != field_name else "destructuring_property",
            }
        )

    return bindings


def _match_destructuring_binding(line: str, field_name: str) -> str | None:
    match = re.search(r"\{(?P<body>[^{}]+)\}\s*=", line)
    if not match:
        return None
    body = match.group("body")
    escaped = re.escape(field_name)
    alias_match = re.search(rf"(?<![\w$]){escaped}(?![\w$])\s*:\s*([A-Za-z_$][\w$]*)", body)
    if alias_match:
        return alias_match.group(1)
    shorthand_match = re.search(rf"(?<![\w$]){escaped}(?![\w$])", body)
    if shorthand_match:
        return field_name
    return None


def _normalize_result(result: dict[str, Any], default_engine: str) -> dict[str, Any]:
    usages = [_normalize_item(item, default_engine) for item in result.get("usages", []) if item.get("line_no")]
    bindings = [_normalize_item(item, default_engine) for item in result.get("bindings", []) if item.get("line_no")]
    return {
        "available": bool(result.get("available", True)),
        "engine": result.get("engine") or default_engine,
        "usages": _dedupe_items(usages, ("line_no", "usage_type")),
        "bindings": _dedupe_items(bindings, ("line_no", "symbol", "binding_type")),
        "errors": result.get("errors", []),
    }


def _normalize_item(item: dict[str, Any], default_engine: str) -> dict[str, Any]:
    normalized = dict(item)
    normalized["line_no"] = int(normalized["line_no"])
    normalized.setdefault("confidence", "medium")
    normalized.setdefault("engine", default_engine)
    return normalized


def _dedupe_items(items: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(name) for name in keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _usage_priority(item: dict[str, Any]) -> int:
    order = {
        "type_field": 0,
        "object_property": 1,
        "bracket_property": 2,
        "object_field": 3,
        "config_field": 4,
        "destructuring_alias": 5,
        "destructuring_property": 6,
    }
    return order.get(item.get("usage_type"), 100)


def _empty_result(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "engine": None,
        "usages": [],
        "bindings": [],
        "errors": [reason],
    }


def _ast_analysis_enabled() -> bool:
    return os.getenv("AST_ANALYSIS_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _ast_engine() -> str:
    value = os.getenv("AST_ANALYSIS_ENGINE", "auto").strip().lower()
    if value not in {"auto", "typescript", "python"}:
        return "auto"
    return value


def _is_comment_line(line: str) -> bool:
    return line.startswith(("//", "/*", "*"))


def _brace_delta(line: str) -> int:
    scrubbed = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "", line)
    return scrubbed.count("{") - scrubbed.count("}")
