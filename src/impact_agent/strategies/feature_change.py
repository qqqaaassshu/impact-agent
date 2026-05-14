from impact_agent.strategies.base import ChangeStrategy


class FeatureChangeStrategy(ChangeStrategy):
    def generate_clues(self, request, project_profile, history) -> list[dict]:
        raise NotImplementedError

    def classify_match(self, file_path, content, clue, context) -> dict:
        raise NotImplementedError

    def collect_relations(self, candidate, context) -> list[dict]:
        raise NotImplementedError
