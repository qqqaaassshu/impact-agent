from impact_agent.adapters.framework.base import FrameworkAnalyzer


class ReactAnalyzer(FrameworkAnalyzer):
    def detect_file_kind(self, file_path: str, content: str) -> str:
        if file_path.endswith((".jsx", ".tsx")) or "from 'react'" in content or 'from "react"' in content:
            return "react_component"
        return "source_module"

    def extract_ui_entries(self, content: str) -> list[dict]:
        entries: list[dict] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("<") or "return (" in stripped:
                entries.append({"line_no": line_no, "line": stripped})
        return entries

    def extract_event_bindings(self, content: str) -> list[dict]:
        bindings: list[dict] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if "onClick=" in stripped or "onChange=" in stripped or "onSubmit=" in stripped:
                bindings.append({"line_no": line_no, "line": stripped, "framework": "react"})
        return bindings

    def extract_field_usages(self, content: str, field_name: str) -> list[dict]:
        usages: list[dict] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if field_name not in stripped or _is_comment(stripped):
                continue

            usage_type = _classify_react_usage(stripped, field_name)
            if usage_type is None:
                continue

            usages.append(
                {
                    "line_no": line_no,
                    "line": stripped,
                    "framework": "react",
                    "usage_type": usage_type,
                    "confidence": "high",
                }
            )
        return usages


def _is_comment(line: str) -> bool:
    return line.startswith("//") or line.startswith("*") or line.startswith("{/*")


def _classify_react_usage(line: str, field_name: str) -> str | None:
    quoted = [f"'{field_name}'", f'"{field_name}"']
    if f".{field_name}" in line:
        return "object_property"
    if f"['{field_name}']" in line or f'["{field_name}"]' in line:
        return "bracket_property"
    if any(marker in line for marker in ("dataIndex", "fieldName", "name", "key", "prop")) and any(
        value in line for value in quoted
    ):
        return "config_field"
    if "{" in line and "}" in line and field_name in line:
        return "jsx_expression"
    if f"{field_name}:" in line:
        return "object_field"
    if any(value in line for value in quoted):
        return "string_key"
    return None
