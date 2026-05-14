import os
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI

DEFAULT_FILE_TYPES = [".ts", ".tsx", ".js", ".jsx", ".vue", ".json"]
DEFAULT_REPO_PATH = os.getenv("REPO_PATH", "src")
DEFAULT_ROOT_PATH = os.getenv("REPO_ROOT_PATH", "")
MAX_SEARCH_ROUNDS = 3
PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = PROJECT_ROOT / "data" / "knowledge"

OPENAI_COMPATIBLE_PROVIDERS = {
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
    "baidu": "https://qianfan.baidubce.com/v2",
}


def get_llm():
    model_str = os.getenv("LLM_MODEL")
    if not model_str:
        raise ValueError(
            "请设置环境变量 LLM_MODEL，格式为 provider:model_name；"
            "海外模型示例：anthropic:claude-sonnet-4-20250514；"
            "国内模型示例：deepseek:deepseek-chat / qwen:qwen-plus"
        )

    provider, separator, model_name = model_str.partition(":")
    if not separator or not model_name:
        raise ValueError("LLM_MODEL 格式错误，应为 provider:model_name")

    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError(f"使用 {provider} 需要设置环境变量 LLM_API_KEY")
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=OPENAI_COMPATIBLE_PROVIDERS[provider],
        )

    return init_chat_model(model_str)
