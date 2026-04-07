from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from medical_agent.config import get_settings


def build_llm() -> ChatOpenAI:
    # 统一在这里创建模型客户端，方便后续切换模型或 base_url。
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model_id,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.temperature,
    )


def extract_text(message: BaseMessage | AIMessage) -> str:
    # LangChain message.content 可能是字符串，也可能是结构化多段内容。
    # 这里统一抽成普通文本，减少上层节点的分支判断。
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(part for part in parts if part)
    return str(content)


def parse_json_object(raw_text: str) -> dict[str, Any]:
    # 模型理想情况下会直接返回 JSON，
    # 但有时会在前后夹带解释文本，所以这里做一次容错提取。
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
