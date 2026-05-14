from abc import ABC, abstractmethod


class CodeSourceAdapter(ABC):
    @abstractmethod
    def snapshot(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def search(self, keyword: str, file_types: list[str], repo_path: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def read(self, file_path: str) -> dict:
        raise NotImplementedError
