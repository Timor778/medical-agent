from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class LlmProfile:
    provider: str
    api_key: str
    base_url: str
    model_id: str


@dataclass(frozen=True)
class MysqlSettings:
    enabled: bool
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"


@dataclass(frozen=True)
class Settings:
    llm: LlmProfile
    tavily_api_key: str
    app_name: str = "Medical Consultation Agent"
    max_search_attempts: int = 1
    search_max_results: int = 3
    search_depth: str = "basic"
    temperature: float = 0.1
    answer_chunk_sleep_ms: int = 0
    mysql: MysqlSettings | None = None


def _get_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip().strip('"').strip("'")
        if value:
            return value
    return default


def _normalize_openai_compatible_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if not normalized:
        return "https://api.openai.com/v1"
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def _build_llm_profile() -> LlmProfile:
    provider = _get_env("LLM_PROVIDER", default="openai").lower()

    profiles: dict[str, LlmProfile] = {
        "openai": LlmProfile(
            provider="openai",
            api_key=_get_env("OPENAI_API_KEY", "LLM_API_KEY"),
            base_url=_normalize_openai_compatible_base_url(
                _get_env("OPENAI_BASE_URL", "LLM_BASE_URL", default="https://api.openai.com/v1")
            ),
            model_id=_get_env("OPENAI_MODEL_NAME", "MODEL_NAME", "LLM_MODEL_ID", default="gpt-4o-mini"),
        ),
        "deepseek": LlmProfile(
            provider="deepseek",
            api_key=_get_env("DEEPSEEK_API_KEY", "LLM_API_KEY"),
            base_url=_normalize_openai_compatible_base_url(
                _get_env("DEEPSEEK_BASE_URL", "LLM_BASE_URL", default="https://api.deepseek.com/v1")
            ),
            model_id=_get_env("DEEPSEEK_MODEL_NAME", "MODEL_NAME", "LLM_MODEL_ID", default="deepseek-chat"),
        ),
        "custom": LlmProfile(
            provider="custom",
            api_key=_get_env("LLM_API_KEY"),
            base_url=_normalize_openai_compatible_base_url(
                _get_env("LLM_BASE_URL", default="https://api.openai.com/v1")
            ),
            model_id=_get_env("LLM_MODEL_ID", default="gpt-4o-mini"),
        ),
    }

    if provider not in profiles:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    profile = profiles[provider]
    if not profile.api_key:
        raise ValueError(f"Missing API key for provider: {provider}")
    return profile


def _build_mysql_settings() -> MysqlSettings | None:
    enabled = _get_env("MYSQL_ENABLED", default="false").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None

    host = _get_env("MYSQL_HOST", default="127.0.0.1")
    port = int(_get_env("MYSQL_PORT", default="3306"))
    user = _get_env("MYSQL_USER", default="root")
    password = _get_env("MYSQL_PASSWORD")
    database = _get_env("MYSQL_DATABASE", default="medical_agent")

    if not password:
        raise ValueError("MYSQL_ENABLED=true but MYSQL_PASSWORD is missing.")

    return MysqlSettings(
        enabled=True,
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset=_get_env("MYSQL_CHARSET", default="utf8mb4"),
    )


def get_settings() -> Settings:
    return Settings(
        llm=_build_llm_profile(),
        tavily_api_key=_get_env("TAVILY_API_KEY"),
        max_search_attempts=int(_get_env("MAX_SEARCH_ATTEMPTS", default="1")),
        search_max_results=int(_get_env("SEARCH_MAX_RESULTS", default="3")),
        search_depth=_get_env("SEARCH_DEPTH", default="basic"),
        temperature=float(_get_env("LLM_TEMPERATURE", default="0.1")),
        answer_chunk_sleep_ms=int(_get_env("ANSWER_CHUNK_SLEEP_MS", default="0")),
        mysql=_build_mysql_settings(),
    )
