from collections.abc import Callable
from typing import Any

from impact_agent.models.llm import ClarificationNeeded, UnsupportedRequest
from impact_agent.models.request import AssessmentRequest
from impact_agent.models.report import AssessmentReport
from impact_agent.orchestrator.runner import AssessmentRunner
from impact_agent.services.intake import intake_and_normalize
from impact_agent.services.knowledge_store import get_assessment_record, list_assessment_history


class AssessmentService:
    def submit(
        self,
        raw_input: dict | str | AssessmentRequest,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        entrypoint: str = "api",
    ) -> AssessmentReport | ClarificationNeeded | UnsupportedRequest:
        if progress_callback:
            progress_callback(
                {
                    "stage": "intake",
                    "title": "解析需求",
                    "message": "正在判断需求是否属于字段变更，并提取旧字段名和新字段名",
                }
            )
        normalized = intake_and_normalize(raw_input, progress_callback=progress_callback)
        if isinstance(normalized, ClarificationNeeded | UnsupportedRequest):
            return normalized
        return AssessmentRunner(progress_callback=progress_callback, entrypoint=entrypoint).run(normalized)

    def list_history(self, limit: int = 50, entrypoint: str | None = None):
        return list_assessment_history(limit=limit, entrypoint=entrypoint)

    def get_history_detail(self, assessment_id: str):
        return get_assessment_record(assessment_id)
