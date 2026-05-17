from impact_agent.adapters.framework.base import FrameworkAnalyzer


class VueAnalyzer(FrameworkAnalyzer):
    def detect_file_kind(self, file_path: str, content: str) -> str:
        if file_path.endswith(".vue") or "<template" in content:
            return "vue_sfc"
        return "source_module"

    def extract_ui_entries(self, content: str) -> list[dict]:
        entries: list[dict] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("<template") or stripped.startswith("<script") or stripped.startswith("<style"):
                entries.append({"line_no": line_no, "line": stripped})
        return entries

    def extract_event_bindings(self, content: str) -> list[dict]:
        bindings: list[dict] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            for marker in ("@", "v-on:"):
                if marker in stripped:
                    bindings.append({"line_no": line_no, "line": stripped, "framework": "vue"})
                    break
        return bindings

    def extract_field_usages(self, content: str, field_name: str) -> list[dict]:
        usages: list[dict] = []
        section = "script"
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("<template"):
                section = "template"
            elif stripped.startswith("</template"):
                section = "script"
            elif stripped.startswith("<script"):
                section = "script"

            if field_name not in stripped or _is_comment(stripped):
                continue

            usage_type = _classify_vue_usage(stripped, field_name, section)
            if usage_type is None:
                continue

            usages.append(
                {
                    "line_no": line_no,
                    "line": stripped,
                    "framework": "vue",
                    "usage_type": usage_type,
                    "confidence": "high",
                }
            )
        return usages


def _is_comment(line: str) -> bool:
    return line.startswith("//") or line.startswith("*") or line.startswith("<!--")


def _classify_vue_usage(line: str, field_name: str, section: str) -> str | None:
    quoted = [f"'{field_name}'", f'"{field_name}"']
    if "{{" in line and field_name in line:
        return "template_interpolation"
    if section == "template" and any(marker in line for marker in ("v-model", "v-bind", ":")) and field_name in line:
        return "template_binding"
    if f".{field_name}" in line:
        return "object_property"
    if f"['{field_name}']" in line or f'["{field_name}"]' in line:
        return "bracket_property"
    if any(value in line for value in quoted):
        return "string_key"
    if f"{field_name}:" in line:
        return "object_field"
    return None
