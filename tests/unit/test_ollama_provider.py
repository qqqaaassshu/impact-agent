from typing import Any

from impact_agent.config import Settings
from impact_agent.providers.ollama import OllamaEmbeddingProvider


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {"embedding": [1, 2.5, 3]}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


def test_ollama_embedding_provider(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, json: dict[str, Any], timeout: int) -> FakeResponse:
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("impact_agent.providers.ollama.httpx.post", fake_post)
    settings = Settings(
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_MODEL_NAME="bge-m3:latest",
        EMBEDDING_BASE_URL="http://127.0.0.1:11434",
    )

    provider = OllamaEmbeddingProvider(settings)
    embedding = provider.embed_query("price field")

    assert embedding == [1.0, 2.5, 3.0]
    assert calls[0]["url"] == "http://127.0.0.1:11434/api/embeddings"
    assert calls[0]["json"] == {"model": "bge-m3:latest", "prompt": "price field"}


def test_ollama_embedding_provider_batches_documents(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, json: dict[str, Any], timeout: int) -> FakeResponse:
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"embeddings": [[1, 2], [3, 4]]})

    monkeypatch.setattr("impact_agent.providers.ollama.httpx.post", fake_post)
    settings = Settings(
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_MODEL_NAME="bge-m3:latest",
        EMBEDDING_BASE_URL="http://127.0.0.1:11434",
    )

    provider = OllamaEmbeddingProvider(settings)
    embeddings = provider.embed_documents(["one", "two"])

    assert embeddings == [[1.0, 2.0], [3.0, 4.0]]
    assert calls[0]["url"] == "http://127.0.0.1:11434/api/embed"
    assert calls[0]["json"] == {"model": "bge-m3:latest", "input": ["one", "two"]}
