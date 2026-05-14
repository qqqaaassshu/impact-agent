from impact_agent.models.llm import ClarificationNeeded
from impact_agent.models.request import AssessmentRequest
from impact_agent.models.report import AssessmentReport
from impact_agent.orchestrator.runner import AssessmentRunner
from impact_agent.services.intake import intake_and_normalize
from impact_agent.services.knowledge_store import get_assessment_record, list_assessment_history


class AssessmentService:
    def submit(self, raw_input: dict | str | AssessmentRequest) -> AssessmentReport | ClarificationNeeded:
        normalized = intake_and_normalize(raw_input)
        if isinstance(normalized, ClarificationNeeded):
            return normalized
        return AssessmentRunner().run(normalized)

    def list_history(self, limit: int = 50):
        return list_assessment_history(limit=limit)

    def get_history_detail(self, assessment_id: str):
        return get_assessment_record(assessment_id)
