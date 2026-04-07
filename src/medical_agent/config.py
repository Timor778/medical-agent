from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model_id: str
    tavily_api_key: str
    app_name: str = "Medical Consultation Agent"
    max_search_attempts: int = 1
    search_max_results: int = 3
    search_depth: str = "basic"
    temperature: float = 0.1
    answer_chunk_sleep_ms: int = 0


def _get_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip().strip('"').strip("'")
        if value:
            return value
    return default


def get_settings() -> Settings:
    llm_api_key = _get_env("LLM_API_KEY", "OPENAI_API_KEY")
    if not llm_api_key:
        raise ValueError("Missing LLM_API_KEY or OPENAI_API_KEY.")

    return Settings(
        llm_api_key=llm_api_key,
        llm_base_url=_get_env("LLM_BASE_URL", "OPENAI_BASE_URL", default="https://api.openai.com/v1"),
        llm_model_id=_get_env("LLM_MODEL_ID", "MODEL_NAME", default="gpt-4o-mini"),
        tavily_api_key=_get_env("TAVILY_API_KEY"),
        max_search_attempts=int(_get_env("MAX_SEARCH_ATTEMPTS", default="1")),
        search_max_results=int(_get_env("SEARCH_MAX_RESULTS", default="3")),
        search_depth=_get_env("SEARCH_DEPTH", default="basic"),
        temperature=float(_get_env("LLM_TEMPERATURE", default="0.1")),
        answer_chunk_sleep_ms=int(_get_env("ANSWER_CHUNK_SLEEP_MS", default="0")),
    )
