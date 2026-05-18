import httpx

from impact_agent.config import Settings, get_settings
from impact_agent.providers.base import ChatProvider, EmbeddingProvider


class OllamaChatProvider(ChatProvider):
    def name(self) -> str:
        return "ollama"


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def name(self) -> str:
        return "ollama"

    def embed_query(self, text: str) -> list[float]:
        base_url = (self.settings.embedding_base_url or "http://127.0.0.1:11434").rstrip("/")
        model_name = self.settings.embedding_model_name or "bge-m3:latest"
        response = httpx.post(
            f"{base_url}/api/embeddings",
            json={"model": model_name, "prompt": text},
            timeout=60,
        )
        response.raise_for_status()
        embedding = response.json()["embedding"]
        return [float(value) for value in embedding]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        base_url = (self.settings.embedding_base_url or "http://127.0.0.1:11434").rstrip("/")
        model_name = self.settings.embedding_model_name or "bge-m3:latest"
        try:
            response = httpx.post(
                f"{base_url}/api/embed",
                json={"model": model_name, "input": texts},
                timeout=120,
            )
            response.raise_for_status()
            embeddings = response.json()["embeddings"]
            return [[float(value) for value in embedding] for embedding in embeddings]
        except Exception:
            return [self.embed_query(text) for text in texts]
