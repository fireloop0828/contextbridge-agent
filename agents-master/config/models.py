"""LLM 模型列表与 ChatModel 工厂。"""

from __future__ import annotations

import os

from dotenv import dotenv_values
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from config.paths import APP_DIR

ANTHROPIC_MODELS = [
    "claude-3-7-sonnet-latest",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
]
OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini"]
DASHSCOPE_MODELS = [
    "glm-5.1",
    "qwen-max",
    "qwen-vl-plus",
]

OUTPUT_TOKEN_INFO = {
    "claude-3-5-sonnet-latest": {"max_tokens": 8192},
    "claude-3-5-haiku-latest": {"max_tokens": 8192},
    "claude-3-7-sonnet-latest": {"max_tokens": 64000},
    "gpt-4o": {"max_tokens": 16000},
    "gpt-4o-mini": {"max_tokens": 16000},
    "glm-5.1": {"max_tokens": 8192},
    "qwen-max": {"max_tokens": 8192},
    "qwen-vl-plus": {"max_tokens": 8192},
}

DASHSCOPE_BASE_URL_DEFAULT = "https://dashscope.aliyuncs.com/compatible-mode/v1"

_DOTENV_FILE_VARS: dict | None = None


def _get_dotenv_file_vars() -> dict:
    global _DOTENV_FILE_VARS
    if _DOTENV_FILE_VARS is None:
        env_path = os.path.join(APP_DIR, ".env")
        _DOTENV_FILE_VARS = dotenv_values(env_path) if os.path.exists(env_path) else {}
    return _DOTENV_FILE_VARS


def _api_key_configured_in_dotenv(key: str) -> bool:
    """
    判断某 API Key 是否在 .env 中显式配置。

    下拉列表只认 .env 文件里的配置，避免终端 export 的 Key 误显示模型。
    """
    val = _get_dotenv_file_vars().get(key)
    if val is None:
        return False
    val = str(val).strip()
    if not val or val.startswith("#"):
        return False
    if "..." in val or val.lower() in ("sk-xxx", "your_key", "your_token_here"):
        return False
    return True


def get_available_models() -> list[str]:
    """根据 .env 文件中已配置的 API Key 返回可选模型列表。"""
    models: list[str] = []
    if _api_key_configured_in_dotenv("DASHSCOPE_API_KEY"):
        models.extend(DASHSCOPE_MODELS)
    if _api_key_configured_in_dotenv("ANTHROPIC_API_KEY"):
        models.extend(ANTHROPIC_MODELS)
    if _api_key_configured_in_dotenv("OPENAI_API_KEY"):
        models.extend(OPENAI_MODELS)
    return models


def create_chat_model(model_name: str):
    """
    按模型所属平台创建 LangChain 聊天模型实例。

    百炼使用 ChatOpenAI + base_url（OpenAI 兼容模式）。
    """
    max_tokens = OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 8192})["max_tokens"]

    if model_name in DASHSCOPE_MODELS:
        return ChatOpenAI(
            model=model_name,
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            base_url=os.environ.get("DASHSCOPE_BASE_URL", DASHSCOPE_BASE_URL_DEFAULT),
            temperature=0.1,
            max_tokens=max_tokens,
        )
    if model_name in ANTHROPIC_MODELS:
        return ChatAnthropic(
            model=model_name,
            temperature=0.1,
            max_tokens=max_tokens,
        )
    return ChatOpenAI(
        model=model_name,
        temperature=0.1,
        max_tokens=max_tokens,
    )
