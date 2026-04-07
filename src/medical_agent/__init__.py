"""Medical consultation agent package."""

# 对外暴露的核心能力只有一个: 创建并返回可执行的 LangGraph 应用。
from .graph.builder import create_medical_agent

__all__ = ["create_medical_agent"]
