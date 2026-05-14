from impact_agent.models.request import AssessmentRequest


def intake_and_normalize(raw_input: dict | AssessmentRequest) -> AssessmentRequest:
    if isinstance(raw_input, AssessmentRequest):
        return raw_input
    if isinstance(raw_input, str):
        raise ValueError("当前版本未启用自然语言 intake，请提供结构化请求")
    if not isinstance(raw_input, dict):
        raise TypeError("raw_input must be a dict or AssessmentRequest")
    return AssessmentRequest.model_validate(raw_input)
