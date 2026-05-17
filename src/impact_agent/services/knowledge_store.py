import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from impact_agent.config import KNOWLEDGE_ROOT
from impact_agent.models.history import AssessmentHistoryItem, AssessmentRecord
from impact_agent.models.report import AssessmentReport


ASSESSMENTS_ROOT = KNOWLEDGE_ROOT / "assessments"


def load_project_profile(project_id: str) -> dict:
    return {"project_id": project_id, "profile_loaded": False}


def load_recent_assessments(project_id: str, module: str | None, change_type: str) -> list[dict]:
    items: list[dict] = []
    for record in _iter_records():
        request = record.request
        source = request.get("source", {})
        scope = request.get("change_scope", {})
        record_project_id = scope.get("module") or source.get("root_path") or "local-project"
        if record_project_id != project_id:
            continue
        if module and scope.get("module") != module:
            continue
        if change_type and request.get("change_type") != change_type:
            continue
        items.append(
            {
                "assessment_id": record.assessment_id,
                "created_at": record.created_at,
                "requirement": record.history_item.requirement,
                "summary": record.report.summary.model_dump(),
            }
        )
    return items[:10]


def append_assessment_summary(report: AssessmentReport, request: dict | None = None) -> None:
    _ensure_root()
    assessment_id = report.summary.assessment_id or uuid4().hex
    created_at = report.summary.created_at or datetime.now(UTC).isoformat()
    report.summary.assessment_id = assessment_id
    report.summary.created_at = created_at

    request = request or {}
    scope = request.get("change_scope", {})
    source = request.get("source", {})
    history_item = AssessmentHistoryItem(
        assessment_id=assessment_id,
        created_at=created_at,
        requirement=report.summary.requirement,
        change_type=report.summary.change_type,
        risk_level=report.summary.risk_level,
        overall_confidence=report.summary.overall_confidence,
        needs_human_review=report.summary.needs_human_review,
        conclusion=report.summary.conclusion,
        project_root=source.get("root_path") or report.summary.source_snapshot.get("root_path"),
        repo_path=request.get("repo_path"),
        module=scope.get("module"),
    )
    record = AssessmentRecord(
        assessment_id=assessment_id,
        created_at=created_at,
        request=request,
        history_item=history_item,
        report=report,
    )
    target = ASSESSMENTS_ROOT / f"{assessment_id}.json"
    target.write_text(json.dumps(record.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")


def list_assessment_history(limit: int = 50, entrypoint: str | None = None) -> list[AssessmentHistoryItem]:
    records = _iter_records()
    if entrypoint:
        records = [record for record in records if record.request.get("entrypoint") == entrypoint]
    items = [record.history_item for record in records]
    return items[:limit]


def get_assessment_record(assessment_id: str) -> AssessmentRecord | None:
    target = ASSESSMENTS_ROOT / f"{assessment_id}.json"
    if not target.exists():
        return None
    return AssessmentRecord.model_validate_json(target.read_text(encoding="utf-8"))


def _iter_records() -> list[AssessmentRecord]:
    if not ASSESSMENTS_ROOT.exists():
        return []
    records: list[AssessmentRecord] = []
    for path in sorted(ASSESSMENTS_ROOT.glob("*.json"), reverse=True):
        try:
            records.append(AssessmentRecord.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    records.sort(key=lambda item: item.created_at, reverse=True)
    return records


def _ensure_root() -> None:
    ASSESSMENTS_ROOT.mkdir(parents=True, exist_ok=True)
