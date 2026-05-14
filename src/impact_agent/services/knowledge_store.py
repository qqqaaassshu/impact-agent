def load_project_profile(project_id: str) -> dict:
    return {"project_id": project_id, "profile_loaded": False}


def load_recent_assessments(project_id: str, module: str | None, change_type: str) -> list[dict]:
    return []


def append_assessment_summary(report) -> None:
    return None
