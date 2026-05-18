from impact_agent.config import Settings, get_settings
from impact_agent.providers.base import EmbeddingProvider
from impact_agent.providers.ollama import OllamaEmbeddingProvider
from impact_agent.providers.openai_compatible import OpenAICompatibleEmbeddingProvider


def create_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    active_settings = settings or get_settings()
    if active_settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(active_settings)
    if active_settings.embedding_provider == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {active_settings.embedding_provider}")
