from impact_agent.config import JsonStructuredChatModel
from impact_agent.models.llm import IntakeParseResult


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChatModel:
    def __init__(self, content: str) -> None:
        self.content = content
        self.prompt = ""

    def invoke(self, prompt: str) -> FakeMessage:
        self.prompt = prompt
        return FakeMessage(self.content)


def test_json_structured_chat_model_parses_plain_json() -> None:
    chat = FakeChatModel('{"change_type":"field_rename","old_name":"amount","new_name":"totalAmount"}')

    result = JsonStructuredChatModel(chat, IntakeParseResult).invoke("解析需求")

    assert result.change_type == "field_rename"
    assert result.old_name == "amount"
    assert result.new_name == "totalAmount"
    assert "只返回一个 JSON 对象" in chat.prompt


def test_json_structured_chat_model_parses_fenced_json() -> None:
    chat = FakeChatModel(
        """
```json
{"needs_clarification":true,"questions":["请补充旧字段名","请补充新字段名"]}
```
""".strip()
    )

    result = JsonStructuredChatModel(chat, IntakeParseResult).invoke("解析需求")

    assert result.needs_clarification is True
    assert result.questions == ["请补充旧字段名", "请补充新字段名"]
