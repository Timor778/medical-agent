from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    # 项目运行所需配置统一放在这里，避免散落在各个模块。
    llm_api_key: str
    llm_base_url: str
    llm_model_id: str
    tavily_api_key: str
    serpapi_api_key: str
    app_name: str = "Medical Consultation Agent"
    max_search_attempts: int = 2
    search_max_results: int = 5
    temperature: float = 0.2


def _get_env(*names: str, default: str = "") -> str:
    # 允许同一配置兼容多个环境变量名，减少迁移成本。
    for name in names:
        value = os.getenv(name, "").strip().strip('"').strip("'")
        if value:
            return value
    return default


def get_settings() -> Settings:
    # 启动时提前校验关键配置，避免运行到一半才发现缺密钥。
    llm_api_key = _get_env("LLM_API_KEY", "OPENAI_API_KEY")
    tavily_api_key = _get_env("TAVILY_API_KEY")
    if not llm_api_key:
        raise ValueError("Missing LLM_API_KEY or OPENAI_API_KEY.")
    if not tavily_api_key:
        raise ValueError("Missing TAVILY_API_KEY.")

    return Settings(
        llm_api_key=llm_api_key,
        llm_base_url=_get_env("LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.openai.com/v1"),
        llm_model_id=_get_env("LLM_MODEL_ID", "MODEL_NAME", default="gpt-4o-mini"),
        tavily_api_key=tavily_api_key,
        serpapi_api_key=_get_env("SERPAPI_API_KEY"),
        max_search_attempts=int(_get_env("MAX_SEARCH_ATTEMPTS", default="2")),
        search_max_results=int(_get_env("SEARCH_MAX_RESULTS", default="5")),
        temperature=float(_get_env("LLM_TEMPERATURE", default="0.2")),
    )
