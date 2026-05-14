import argparse
import json

from impact_agent.orchestrator.runner import AssessmentRunner
from impact_agent.services.intake import intake_and_normalize


def main() -> None:
    parser = argparse.ArgumentParser(description="需求变更影响范围评估 Agent")
    parser.add_argument("--input", required=True, help="结构化请求 JSON 文件路径")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as file:
        payload = json.load(file)

    request = intake_and_normalize(payload)
    report = AssessmentRunner().run(request)
    print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
