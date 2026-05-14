from abc import ABC, abstractmethod


class ChangeStrategy(ABC):
    @abstractmethod
    def generate_clues(self, request, project_profile, history) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def classify_match(self, file_path, content, clue, context) -> dict:
        raise NotImplementedError

    @abstractmethod
    def collect_relations(self, candidate, context) -> list[dict]:
        raise NotImplementedError
