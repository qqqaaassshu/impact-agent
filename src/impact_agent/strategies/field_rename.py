from impact_agent.config import get_llm
from impact_agent.models.llm import ClueExpansionResult, SemanticMatchDecision
from impact_agent.strategies.base import ChangeStrategy


class FieldRenameStrategy(ChangeStrategy):
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

        merged: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for item in base_clues:
            key = (item["keyword"], item["clue_category"])
            if key not in seen:
                seen.add(key)
                merged.append(item)

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

        if any(marker in line for marker in ["[", "get(", "getValue(", "fieldName", "columnsMap", "dynamic"]):
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
        return []

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
