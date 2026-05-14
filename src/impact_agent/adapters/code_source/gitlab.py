from impact_agent.adapters.code_source.base import CodeSourceAdapter


class GitLabCodeSourceAdapter(CodeSourceAdapter):
    def snapshot(self) -> dict:
        raise NotImplementedError

    def search(self, keyword: str, file_types: list[str], repo_path: str | None = None) -> dict:
        raise NotImplementedError

    def read(self, file_path: str) -> dict:
        raise NotImplementedError
