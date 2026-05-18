from impact_agent.config import Settings


def test_default_exclude_patterns_are_split() -> None:
    settings = Settings(IMPACT_AGENT_DEFAULT_EXCLUDE="node_modules, dist, .git")

    assert settings.default_exclude_patterns == ["node_modules", "dist", ".git"]


def test_chat_model_settings_are_loaded() -> None:
    settings = Settings(
        CHAT_MODEL_NAME="deepseek-v4-flash",
        CHAT_MODEL_BASE_URL="https://api.deepseek.com",
        CHAT_MODEL_RESPONSE_FORMAT="json_object",
        CHAT_MODEL_TEMPERATURE="0.2",
        CHAT_MODEL_MAX_TOKENS="4096",
    )

    assert settings.chat_model_name == "deepseek-v4-flash"
    assert settings.chat_model_base_url == "https://api.deepseek.com"
    assert settings.chat_model_response_format == "json_object"
    assert settings.chat_model_temperature == 0.2
    assert settings.chat_model_max_tokens == 4096
