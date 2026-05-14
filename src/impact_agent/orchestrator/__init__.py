from impact_agent.models.request import AssessmentRequest
from impact_agent.models.report import AssessmentReport


class Orchestrator:
    def run(self, request: AssessmentRequest) -> AssessmentReport:
        raise NotImplementedError
