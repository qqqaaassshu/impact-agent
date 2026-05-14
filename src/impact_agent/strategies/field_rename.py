from impact_agent.strategies.base import ChangeStrategy


class FieldRenameStrategy(ChangeStrategy):
    def generate_clues(self, request, project_profile, history) -> list[dict]:
        scope = request.change_scope
        clues = [
            {
                "keyword": scope.old_name,
                "clue_category": "old_name",
                "reason": "search old field references",
            },
            {
                "keyword": scope.new_name,
                "clue_category": "new_name",
                "reason": "search already-migrated references",
            },
        ]
        return clues

    def classify_match(self, file_path, content, clue, context) -> dict:
        line = context["candidate"]["line"]
        line_no = context["candidate"]["line_no"]
        keyword = clue["keyword"]

        if any(marker in line for marker in ["[", "get(", "getValue(", "fieldName", "columnsMap", "dynamic"]):
            return self._decision(
                status="uncertain",
                reason="dynamic_field_reference",
                confidence="low",
                file_path=file_path,
                line_no=line_no,
                code=line,
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
