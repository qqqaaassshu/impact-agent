import argparse
import json

from impact_agent.models.llm import ClarificationNeeded
from impact_agent.services.assessment_service import AssessmentService


def main() -> None:
    parser = argparse.ArgumentParser(description="需求变更影响范围评估 Agent")
    parser.add_argument("--input", required=True, help="请求文件路径，支持 JSON 或纯文本需求描述")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as file:
        raw_input = file.read()

    result = AssessmentService().submit(raw_input)
    if isinstance(result, ClarificationNeeded):
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
        return

    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
