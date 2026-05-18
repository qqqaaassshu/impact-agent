import json
from typing import Any

import httpx

from impact_agent.config import Settings, get_settings
from impact_agent.providers.base import ChatProvider, EmbeddingProvider


class OpenAICompatibleChatProvider(ChatProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def name(self) -> str:
        return "openai_compatible"

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.settings.chat_model_api_key:
            raise RuntimeError("CHAT_MODEL_API_KEY is not configured.")
        if not self.settings.chat_model_base_url:
            raise RuntimeError("CHAT_MODEL_BASE_URL is not configured.")
        if not self.settings.chat_model_name:
            raise RuntimeError("CHAT_MODEL_NAME is not configured.")

        response = httpx.post(
            _chat_completions_url(self.settings.chat_model_base_url),
            headers={
                "Authorization": f"Bearer {self.settings.chat_model_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.chat_model_name,
                "messages": messages,
                "temperature": self.settings.chat_model_temperature,
                "max_tokens": self.settings.chat_model_max_tokens,
                "response_format": {"type": self.settings.chat_model_response_format}
                if self.settings.chat_model_response_format
                else None,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def name(self) -> str:
        return "openai_compatible"

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("OpenAI-compatible embedding provider is not implemented yet.")


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/chat/completions"
