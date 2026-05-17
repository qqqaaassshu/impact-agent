from __future__ import annotations

from impact_agent.services.ast_analyzer import analyze_javascript_ast
from impact_agent.services.frontend_search import search_local_candidates, search_local_candidates_many


class FrontendImpactSearchSkill:
    """Runtime adapter for the frontend-impact-search Skill package.

    The executable capability is owned by the Skill package. This class is the
    application-side adapter that invokes those capabilities and returns
    structured observations to the Agent.
    """

    name = "frontend-impact-search"

    def local_search(
        self,
        *,
        root_path: str,
        keyword: str,
        file_types: list[str],
        repo_path: str | None = None,
    ) -> dict:
        return {
            "skill": self.name,
            "action": "local_search",
            "observation": search_local_candidates(
                root_path=root_path,
                keyword=keyword,
                file_types=file_types,
                repo_path=repo_path,
            ),
        }

    def local_search_many(
        self,
        *,
        root_path: str,
        keywords: list[str],
        file_types: list[str],
        repo_path: str | None = None,
    ) -> dict:
        return {
            "skill": self.name,
            "action": "local_search_many",
            "observation": search_local_candidates_many(
                root_path=root_path,
                keywords=keywords,
                file_types=file_types,
                repo_path=repo_path,
            ),
        }

    def ast_analyze(self, *, file_path: str, content: str, field_name: str) -> dict:
        return {
            "skill": self.name,
            "action": "ast_analyze",
            "observation": analyze_javascript_ast(file_path, content, field_name),
        }
