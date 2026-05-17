from abc import ABC, abstractmethod


class CodeSourceAdapter(ABC):
    @abstractmethod
    def snapshot(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def search(self, keyword: str, file_types: list[str], repo_path: str | None = None) -> dict:
        raise NotImplementedError

    def search_many(self, keywords: list[str], file_types: list[str], repo_path: str | None = None) -> dict:
        results_by_keyword = {}
        total_scanned_files = 0
        search_root = None
        search_engine = "adapter"
        for keyword in keywords:
            result = self.search(keyword, file_types, repo_path)
            results_by_keyword[keyword] = result["results"]
            total_scanned_files += int(result.get("scanned_files", 0))
            search_root = search_root or result.get("search_root")
            search_engine = result.get("search_engine", search_engine)
        return {
            "keywords": keywords,
            "search_root": search_root,
            "scanned_files": total_scanned_files,
            "search_engine": search_engine,
            "results_by_keyword": results_by_keyword,
        }

    @abstractmethod
    def read(self, file_path: str) -> dict:
        raise NotImplementedError
