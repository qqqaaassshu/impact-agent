from pathlib import Path
import subprocess

from impact_agent.adapters.code_source.base import CodeSourceAdapter


class LocalCodeSourceAdapter(CodeSourceAdapter):
    def __init__(self, root_path: str) -> None:
        self.root_path = Path(root_path).expanduser().resolve()

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
        search_root = self._resolve_search_root(repo_path)
        normalized_types = set(file_types)
        results: list[dict] = []
        scanned_files = 0

        for file_path in search_root.rglob("*"):
            if not file_path.is_file() or file_path.suffix not in normalized_types:
                continue
            scanned_files += 1
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                if keyword in line:
                    results.append(
                        {
                            "file_path": str(file_path),
                            "relative_path": str(file_path.relative_to(self.root_path)),
                            "line_no": line_no,
                            "line": line.strip(),
                            "keyword": keyword,
                        }
                    )

        return {
            "keyword": keyword,
            "search_root": str(search_root),
            "scanned_files": scanned_files,
            "results": results,
        }

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

    def _resolve_search_root(self, repo_path: str | None) -> Path:
        if not repo_path:
            return self.root_path
        candidate = (self.root_path / repo_path).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"repo_path does not exist: {repo_path}")
        return candidate

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
