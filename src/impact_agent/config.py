from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: str = Field(default=".impact-agent", alias="IMPACT_AGENT_DATA_DIR")
    default_include: str = Field(default="src", alias="IMPACT_AGENT_DEFAULT_INCLUDE")
    default_exclude: str = Field(
        default="node_modules,dist,build,.git",
        alias="IMPACT_AGENT_DEFAULT_EXCLUDE",
    )

    chat_model_provider: str = Field(default="openai_compatible", alias="CHAT_MODEL_PROVIDER")
    chat_model_name: str = Field(default="", alias="CHAT_MODEL_NAME")
    chat_model_base_url: str = Field(default="", alias="CHAT_MODEL_BASE_URL")
    chat_model_api_key: str = Field(default="", alias="CHAT_MODEL_API_KEY")
    chat_model_response_format: str = Field(default="", alias="CHAT_MODEL_RESPONSE_FORMAT")
    chat_model_temperature: float = Field(default=0.2, alias="CHAT_MODEL_TEMPERATURE")
    chat_model_max_tokens: int = Field(default=4096, alias="CHAT_MODEL_MAX_TOKENS")

    embedding_provider: str = Field(default="openai_compatible", alias="EMBEDDING_PROVIDER")
    embedding_model_name: str = Field(default="", alias="EMBEDDING_MODEL_NAME")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")

    max_react_iteration: int = Field(default=8, alias="MAX_REACT_ITERATION")
    max_tool_results: int = Field(default=20, alias="MAX_TOOL_RESULTS")
    max_chunk_tokens: int = Field(default=800, alias="MAX_CHUNK_TOKENS")

    @property
    def default_exclude_patterns(self) -> list[str]:
        return [item.strip() for item in self.default_exclude.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
