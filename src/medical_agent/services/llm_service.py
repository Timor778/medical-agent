from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from medical_agent.config import get_settings


def build_llm(*, streaming: bool = False) -> ChatOpenAI:
    settings = get_settings()
    profile = settings.llm
    return ChatOpenAI(
        model=profile.model_id,
        api_key=profile.api_key,
        base_url=profile.base_url,
        temperature=settings.temperature,
        streaming=streaming,
    )


def current_llm_profile() -> dict[str, str]:
    profile = get_settings().llm
    return {
        "provider": profile.provider,
        "model_id": profile.model_id,
        "base_url": profile.base_url,
    }


def extract_text(message: BaseMessage | AIMessage | Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part)
    return str(content)


def parse_json_object(raw_text: str) -> dict[str, Any]:
    raw_text = raw_text.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw_text[start : end + 1])
    raise ValueError(f"Failed to parse JSON from model output: {raw_text}")


def invoke_text(messages: Sequence[BaseMessage]) -> str:
    return extract_text(build_llm().invoke(list(messages)))


def stream_text(messages: Sequence[BaseMessage]) -> Iterable[str]:
    try:
        for chunk in build_llm(streaming=True).stream(list(messages)):
            text = extract_text(chunk)
            if text:
                yield text
    except (httpx.HTTPError, OSError) as exc:
        # 某些 OpenAI-compatible 提供方在流式输出时会中途断开连接。
        # 这里自动回退到非流式调用，避免整次问答直接失败。
        fallback_text = invoke_text(messages)
        if fallback_text:
            yield fallback_text
