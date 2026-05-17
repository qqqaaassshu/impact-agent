import os
import json
import re
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DEFAULT_FILE_TYPES = [".ts", ".tsx", ".js", ".jsx", ".vue", ".json"]
DEFAULT_REPO_PATH = os.getenv("REPO_PATH", "")
DEFAULT_ROOT_PATH = os.getenv("REPO_ROOT_PATH", "")
MAX_SEARCH_ROUNDS = 3
MAX_CONTEXT_REVIEW_ITEMS = int(os.getenv("MAX_CONTEXT_REVIEW_ITEMS", "20"))
LLM_CONTEXT_REVIEW_ENABLED = os.getenv("LLM_CONTEXT_REVIEW", "true").strip().lower() in {"1", "true", "yes", "on"}
KNOWLEDGE_ROOT = PROJECT_ROOT / "data" / "knowledge"

OPENAI_COMPATIBLE_PROVIDERS = {
    "aliyun": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ark": "https://ark.cn-beijing.volces.com/api/v3",
    "baidu": "https://qianfan.baidubce.com/v2",
    "deepseek": "https://api.deepseek.com",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "kimi": "https://api.moonshot.cn/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "moonshot-global": "https://api.moonshot.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}


def get_llm():
    model = os.getenv("LLM_MODEL")
    if not model:
        raise ValueError(
            "请设置 LLM_MODEL，例如 deepseek-chat、qwen-plus、glm-4-flash 或 moonshot-v1-8k。"
            "如果使用国产大模型，建议同时设置 LLM_BASE_URL 和 LLM_API_KEY。"
        )

    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    model_name = model.strip()
    legacy_provider, separator, legacy_model_name = model_name.partition(":")
    if separator:
        provider = provider or legacy_provider.strip().lower()
        model_name = legacy_model_name.strip()

    base_url = os.getenv("LLM_BASE_URL") or OPENAI_COMPATIBLE_PROVIDERS.get(provider)
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not base_url:
        supported = "、".join(sorted(OPENAI_COMPATIBLE_PROVIDERS))
        raise ValueError(
            "请设置 LLM_BASE_URL，或设置 LLM_PROVIDER 使用内置厂商别名。"
            f"当前内置别名：{supported}"
        )
    if not api_key:
        raise ValueError("请设置 LLM_API_KEY；如果使用 OpenAI 兼容接口，也可以设置 OPENAI_API_KEY。")

    chat_model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
        timeout=float(os.getenv("LLM_TIMEOUT", "60")),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
    )
    return CompatibleChatModel(chat_model)


class CompatibleChatModel:
    def __init__(self, chat_model: ChatOpenAI) -> None:
        self.chat_model = chat_model

    def with_structured_output(self, schema: type[BaseModel]):
        mode = os.getenv("LLM_STRUCTURED_MODE", "json").strip().lower()
        if mode in {"native", "tool", "function_calling"}:
            return self.chat_model.with_structured_output(schema)
        return JsonStructuredChatModel(self.chat_model, schema)


class JsonStructuredChatModel:
    def __init__(self, chat_model: ChatOpenAI, schema: type[BaseModel]) -> None:
        self.chat_model = chat_model
        self.schema = schema

    def invoke(self, prompt: str):
        response = self.chat_model.invoke(self._build_prompt(prompt))
        text = _message_content_to_text(response.content)
        payload = _extract_json_object(text)
        return self.schema.model_validate(payload)

    def _build_prompt(self, prompt: str) -> str:
        schema_json = json.dumps(self.schema.model_json_schema(), ensure_ascii=False)
        return f"""
{prompt}

输出要求：
- 只返回一个 JSON 对象，不要返回 Markdown，不要返回代码块，不要解释。
- 字段名必须严格使用 schema 中定义的英文 key。
- 如果某个字段无法判断，按 schema 类型返回 null、false 或空数组，不要编造。

JSON schema：
{schema_json}
""".strip()


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if value:
                    parts.append(str(value))
        return "\n".join(parts)
    return str(content)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end < start:
            raise ValueError(f"大模型没有返回可解析的 JSON：{stripped[:200]}") from None
        payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("大模型返回的结构不是 JSON 对象")
    return payload
