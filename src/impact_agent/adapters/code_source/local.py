from pathlib import Path
import subprocess

from impact_agent.adapters.code_source.base import CodeSourceAdapter
from impact_agent.services.frontend_impact_skill import FrontendImpactSearchSkill


class LocalCodeSourceAdapter(CodeSourceAdapter):
    def __init__(self, root_path: str) -> None:
        self.root_path = Path(root_path).expanduser().resolve()
        self.skill = FrontendImpactSearchSkill()

    def snapshot(self) -> dict:
        snapshot = {
            "type": "local",
            "root_path": str(self.root_path),
            "git": {
                "is_repo": False,
                "commit": None,
                "has_uncommitted_changes": None,
            },
        }

        try:
            is_repo = self._run_git(["rev-parse", "--is-inside-work-tree"]).strip() == "true"
        except RuntimeError:
            return snapshot

        snapshot["git"]["is_repo"] = is_repo
        if not is_repo:
            return snapshot

        try:
            snapshot["git"]["commit"] = self._run_git(["rev-parse", "HEAD"]).strip()
            status = self._run_git(["status", "--porcelain"]).strip()
            snapshot["git"]["has_uncommitted_changes"] = bool(status)
        except RuntimeError:
            snapshot["git"]["has_uncommitted_changes"] = None

        return snapshot

    def search(self, keyword: str, file_types: list[str], repo_path: str | None = None) -> dict:
        result = self.skill.local_search(
            root_path=str(self.root_path),
            keyword=keyword,
            file_types=file_types,
            repo_path=repo_path,
        )
        return result["observation"]

    def search_many(self, keywords: list[str], file_types: list[str], repo_path: str | None = None) -> dict:
        result = self.skill.local_search_many(
            root_path=str(self.root_path),
            keywords=keywords,
            file_types=file_types,
            repo_path=repo_path,
        )
        return result["observation"]

    def read(self, file_path: str) -> dict:
        target = Path(file_path)
        try:
            content = target.read_text(encoding="utf-8")
            return {
                "read_success": True,
                "file_path": str(target),
                "content": content,
            }
        except UnicodeDecodeError:
            content = target.read_text(encoding="utf-8", errors="ignore")
            return {
                "read_success": True,
                "file_path": str(target),
                "content": content,
            }
        except OSError as exc:
            return {
                "read_success": False,
                "file_path": str(target),
                "error": str(exc),
            }

    def _run_git(self, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.root_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            raise RuntimeError(str(exc)) from exc
        return result.stdout
