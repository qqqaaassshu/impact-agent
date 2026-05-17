import os
import re

from impact_agent.config import get_llm
from impact_agent.adapters.framework.react import ReactAnalyzer
from impact_agent.adapters.framework.vue import VueAnalyzer
from impact_agent.models.llm import ClueExpansionResult, SemanticMatchDecision
from impact_agent.strategies.base import ChangeStrategy


class FieldRenameStrategy(ChangeStrategy):
    def __init__(self, progress_callback=None) -> None:
        self.progress_callback = progress_callback

    def generate_clues(self, request, project_profile, history) -> list[dict]:
        scope = request.change_scope
        base_clues = [
            {
                "keyword": scope.old_name,
                "clue_category": "old_name",
                "reason": "search old field references",
                "source": "base",
            },
            {
                "keyword": scope.new_name,
                "clue_category": "new_name",
                "reason": "search already-migrated references",
                "source": "base",
            },
        ]

        deterministic_clues = _deterministic_field_variants(scope.old_name, scope.new_name)
        if not _llm_clue_expansion_enabled():
            return _merge_clues(base_clues, deterministic_clues)

        self._emit_progress(
            "llm_clue_expansion",
            "调用大模型扩展关键词",
            "正在让大模型补充少量可能的字段别名或写法变体",
        )
        llm = get_llm().with_structured_output(ClueExpansionResult)
        llm_result = llm.invoke(
            f"""
你是字段变更分析助手。
请根据以下变更信息，推断前端代码中可能出现的字段搜索关键词变体。
只返回关键词列表，不要解释。

requirement: {request.requirement}
old_name: {scope.old_name}
new_name: {scope.new_name}
module: {scope.module}
entity_kind: {scope.entity_kind}
file_types: {request.file_types}
""".strip()
        )

        merged = _merge_clues(base_clues, deterministic_clues)
        seen: set[tuple[str, str]] = {(item["keyword"], item["clue_category"]) for item in merged}

        for keyword in llm_result.clues:
            if not keyword or keyword in {scope.old_name, scope.new_name}:
                continue
            key = (keyword, "llm_variant")
            if key not in seen:
                seen.add(key)
                merged.append(
                    {
                        "keyword": keyword,
                        "clue_category": "llm_variant",
                        "reason": llm_result.reasoning or "llm clue expansion",
                        "source": "llm",
                    }
                )

        return merged

    def classify_match(self, file_path, content, clue, context) -> dict:
        line = context["candidate"]["line"]
        line_no = context["candidate"]["line_no"]
        keyword = clue["keyword"]

        if _is_comment_line(line):
            decision = self._decision(
                status="excluded",
                reason="comment_match",
                confidence="high",
                file_path=file_path,
                line_no=line_no,
                code=line,
                clue_category=clue["clue_category"],
            )
            decision["match_kind"] = "comment"
            return decision

        framework_usage = self._find_framework_usage(file_path, content, line_no, keyword)
        if framework_usage:
            decision = self._decision(
                status="confirmed_affected",
                reason=f"{framework_usage['framework']}_{framework_usage['usage_type']}",
                confidence=framework_usage["confidence"],
                file_path=file_path,
                line_no=line_no,
                code=line,
                clue_category=clue["clue_category"],
            )
            decision["framework"] = framework_usage["framework"]
            decision["usage_type"] = framework_usage["usage_type"]
            return decision

        if any(marker in line for marker in ["[", "get(", "getValue(", "fieldName", "columnsMap", "dynamic"]):
            if not _llm_semantic_review_enabled():
                return self._decision(
                    status="uncertain",
                    reason="dynamic_field_reference",
                    confidence="low",
                    file_path=file_path,
                    line_no=line_no,
                    code=line,
                    clue_category=clue["clue_category"],
                )
            return self._semantic_fallback(
                file_path=file_path,
                content=content,
                line_no=line_no,
                line=line,
                keyword=keyword,
                clue_category=clue["clue_category"],
            )

        if not self._contains_field_reference(line, keyword):
            return self._decision(
                status="excluded",
                reason="substring_only_match",
                confidence="medium",
                file_path=file_path,
                line_no=line_no,
                code=line,
                clue_category=clue["clue_category"],
            )

        return self._decision(
            status="confirmed_affected",
            reason="static_field_reference",
            confidence="high",
            file_path=file_path,
            line_no=line_no,
            code=line,
            clue_category=clue["clue_category"],
        )

    def collect_relations(self, candidate, context) -> list[dict]:
        content = context.get("content") or ""
        clue = context.get("clue") or {}
        decision = context.get("decision") or {}
        source_evidence_id = context.get("evidence_id")
        keyword = clue.get("keyword")
        if not content or not keyword or decision.get("status") != "uncertain":
            return []

        line = candidate.get("line") or decision.get("code") or ""
        source_line_no = int(candidate.get("line_no") or decision.get("line_no") or 0)
        symbols = _extract_symbols_bound_to_keyword(line, keyword)
        if not symbols:
            return []

        relations: list[dict] = []
        seen: set[tuple[str, int]] = set()
        lines = content.splitlines()
        for symbol in symbols:
            pattern = re.compile(rf"(?<![\w$]){re.escape(symbol)}(?![\w$])")
            for index in _forward_scope_line_numbers(lines, source_line_no):
                candidate_line = lines[index - 1]
                if not pattern.search(candidate_line):
                    continue
                stripped = candidate_line.strip()
                if not stripped or _is_declaration_only(stripped, symbol):
                    continue
                key = (symbol, index)
                if key in seen:
                    continue
                seen.add(key)
                relations.append(
                    {
                        "status": "uncertain",
                        "reason": "variable_propagation_reference",
                        "confidence": "low",
                        "file_path": candidate.get("file_path") or decision.get("file_path"),
                        "relative_path": candidate.get("relative_path"),
                        "line_no": index,
                        "code": stripped,
                        "line": stripped,
                        "clue_category": clue.get("clue_category", decision.get("clue_category", "old_name")),
                        "source_evidence_id": source_evidence_id,
                        "propagated_symbol": symbol,
                        "keyword": keyword,
                        "file_kind": candidate.get("file_kind"),
                    }
                )
                if len(relations) >= 10:
                    return relations
        return relations

    def _semantic_fallback(
        self,
        *,
        file_path: str,
        content: str,
        line_no: int,
        line: str,
        keyword: str,
        clue_category: str,
    ) -> dict:
        context = self._line_context(content, line_no)
        self._emit_progress(
            "llm_semantic_review",
            "调用大模型复核动态引用",
            f"正在复核 {file_path}:{line_no} 的动态字段引用是否受影响",
        )
        llm = get_llm().with_structured_output(SemanticMatchDecision)
        result = llm.invoke(
            f"""
以下代码片段中，字段 {keyword} 是否是一个需要随变更同步修改的业务字段引用？
文件：{file_path}
代码片段：
{context}

返回结构：is_affected=true 表示确认受影响；false 表示确认排除；null 表示无法判断。
""".strip()
        )
        if result.is_affected is True:
            return self._decision(
                status="confirmed_affected",
                reason=result.reason or "llm_semantic_confirmed",
                confidence="medium",
                file_path=file_path,
                line_no=line_no,
                code=line,
                clue_category=clue_category,
            )
        if result.is_affected is False:
            return self._decision(
                status="excluded",
                reason=result.reason or "llm_semantic_excluded",
                confidence="medium",
                file_path=file_path,
                line_no=line_no,
                code=line,
                clue_category=clue_category,
            )
        return self._decision(
            status="uncertain",
            reason=result.reason or "dynamic_field_reference",
            confidence="low",
            file_path=file_path,
            line_no=line_no,
            code=line,
            clue_category=clue_category,
        )

    def _contains_field_reference(self, line: str, keyword: str) -> bool:
        patterns = [
            f".{keyword}",
            f"['{keyword}']",
            f'["{keyword}"]',
            f"'{keyword}'",
            f'"{keyword}"',
            f"{{{{ {keyword} }}}}",
            f"{{{keyword}}}",
            f"{keyword}:",
            f" {keyword}:",
            f"<{keyword}>",
        ]
        return any(pattern in line for pattern in patterns)

    def _find_framework_usage(self, file_path: str, content: str, line_no: int, keyword: str) -> dict | None:
        analyzers = []
        if file_path.endswith(".vue") or "<template" in content:
            analyzers.append(VueAnalyzer())
        if file_path.endswith((".jsx", ".tsx")) or "from 'react'" in content or 'from "react"' in content:
            analyzers.append(ReactAnalyzer())

        for analyzer in analyzers:
            for usage in analyzer.extract_field_usages(content, keyword):
                if usage["line_no"] == line_no:
                    return usage
        return None

    def _line_context(self, content: str, line_no: int) -> str:
        lines = content.splitlines()
        start = max(0, line_no - 4)
        end = min(len(lines), line_no + 3)
        return "\n".join(f"{index + 1}: {lines[index]}" for index in range(start, end))

    def _decision(
        self,
        *,
        status: str,
        reason: str,
        confidence: str,
        file_path: str,
        line_no: int,
        code: str,
        clue_category: str,
    ) -> dict:
        return {
            "status": status,
            "reason": reason,
            "confidence": confidence,
            "file_path": file_path,
            "line_no": line_no,
            "code": code,
            "clue_category": clue_category,
        }

    def _emit_progress(self, stage: str, title: str, message: str) -> None:
        if self.progress_callback:
            self.progress_callback({"stage": stage, "title": title, "message": message})


def _llm_semantic_review_enabled() -> bool:
    return os.getenv("LLM_SEMANTIC_REVIEW", "false").strip().lower() in {"1", "true", "yes", "on"}


def _llm_clue_expansion_enabled() -> bool:
    return os.getenv("LLM_CLUE_EXPANSION", "false").strip().lower() in {"1", "true", "yes", "on"}


def _deterministic_field_variants(old_name: str | None, new_name: str | None) -> list[dict]:
    variants: list[dict] = []
    for source, name in (("old_name", old_name), ("new_name", new_name)):
        if not name:
            continue
        for variant in _name_variants(name):
            if variant == name:
                continue
            variants.append(
                {
                    "keyword": variant,
                    "clue_category": "deterministic_variant",
                    "reason": f"deterministic variant of {source}",
                    "source": "deterministic",
                }
            )
    return variants


def _name_variants(name: str) -> list[str]:
    snake = _camel_to_snake(name)
    kebab = snake.replace("_", "-")
    lower = name.lower()
    upper = name.upper()
    title = name[:1].upper() + name[1:] if name else name
    return list(dict.fromkeys([name, snake, kebab, lower, upper, title]))


def _camel_to_snake(name: str) -> str:
    result: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0 and (not name[index - 1].isupper()):
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def _merge_clues(*groups: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for item in group:
            key = (item["keyword"], item["clue_category"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _extract_symbols_bound_to_keyword(line: str, keyword: str) -> list[str]:
    escaped = re.escape(keyword)
    patterns = [
        rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*['\"]{escaped}['\"]",
        rf"\b([A-Za-z_$][\w$]*)\s*=\s*['\"]{escaped}['\"]",
        rf"\b([A-Za-z_$][\w$]*)\s*:\s*['\"]{escaped}['\"]",
    ]
    symbols: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, line):
            symbol = match.group(1)
            if symbol not in symbols:
                symbols.append(symbol)
    return symbols


def _is_comment_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("//", "/*", "*", "<!--"))


def _is_declaration_only(line: str, symbol: str) -> bool:
    return bool(re.fullmatch(rf"(?:const|let|var)\s+{re.escape(symbol)}\b.*", line))


def _forward_scope_line_numbers(lines: list[str], source_line_no: int, max_lines: int = 80) -> list[int]:
    if source_line_no <= 0:
        return []
    depth = 0
    for line in lines[:source_line_no]:
        depth += _brace_delta(line)
    source_depth = max(depth, 0)
    line_numbers: list[int] = []
    end_line_no = min(len(lines), source_line_no + max_lines)
    for line_no in range(source_line_no + 1, end_line_no + 1):
        line = lines[line_no - 1]
        if source_depth > 0 and depth < source_depth:
            break
        if source_depth > 0 and depth == source_depth and line.lstrip().startswith("}"):
            break
        line_numbers.append(line_no)
        depth += _brace_delta(line)
    return line_numbers


def _brace_delta(line: str) -> int:
    scrubbed = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "", line)
    return scrubbed.count("{") - scrubbed.count("}")
