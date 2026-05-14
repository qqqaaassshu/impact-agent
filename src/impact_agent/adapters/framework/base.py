from abc import ABC, abstractmethod


class FrameworkAnalyzer(ABC):
    @abstractmethod
    def detect_file_kind(self, file_path: str, content: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def extract_ui_entries(self, content: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def extract_event_bindings(self, content: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def extract_field_usages(self, content: str, field_name: str) -> list[dict]:
        raise NotImplementedError
