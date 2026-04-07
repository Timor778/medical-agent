from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tavily import TavilyClient

from medical_agent.config import get_settings


@dataclass
class RetrievalBundle:
    mode: str
    summary: str
    snippets: str
    sources: list[str]
    hit_count: int
    success: bool


class RetrievalTool(ABC):
    name: str

    @abstractmethod
    def retrieve(self, query: str) -> RetrievalBundle:
        raise NotImplementedError


class LocalRagTool(RetrievalTool):
    name = "rag"

    def __init__(self) -> None:
        data_path = Path(__file__).resolve().parent.parent / "data" / "local_knowledge.json"
        self.documents: list[dict[str, Any]] = json.loads(data_path.read_text(encoding="utf-8"))

    def retrieve(self, query: str) -> RetrievalBundle:
        matches: list[tuple[int, dict[str, Any]]] = []
        lowered_query = query.lower()

        for document in self.documents:
            keywords = document.get("keywords", [])
            score = sum(1 for keyword in keywords if keyword.lower() in lowered_query)
            if score > 0:
                matches.append((score, document))

        matches.sort(key=lambda item: item[0], reverse=True)
        top_matches = [item[1] for item in matches[:3]]
        snippets = []
        sources = []
        for index, item in enumerate(top_matches, start=1):
            snippets.append(
                f"[本地知识库{index}] {item['title']}\n"
                f"摘要: {item['content']}\n"
                f"适用场景: {item['scope']}"
            )
            sources.append(f"local://{item['id']}")

        success = len(top_matches) > 0
        summary = "命中本地知识库，可先基于本地资料回答。" if success else "本地知识库未命中足够信息。"
        return RetrievalBundle(
            mode=self.name,
            summary=summary,
            snippets="\n\n".join(snippets),
            sources=sources,
            hit_count=len(top_matches),
            success=success,
        )


class WebSearchTool(RetrievalTool):
    name = "web"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.tavily_api_key
        self.max_results = settings.search_max_results
        self.search_depth = settings.search_depth
        self.client = TavilyClient(api_key=self.api_key) if self.api_key else None

    def retrieve(self, query: str) -> RetrievalBundle:
        if not self.client:
            return RetrievalBundle(
                mode=self.name,
                summary="未配置 TAVILY_API_KEY，无法进行联网检索。",
                snippets="",
                sources=[],
                hit_count=0,
                success=False,
            )

        response = self.client.search(
            query=query,
            search_depth=self.search_depth,
            max_results=self.max_results,
            include_answer=True,
            include_raw_content=False,
        )

        results = response.get("results", [])
        summary = response.get("answer", "")
        formatted: list[str] = []
        sources: list[str] = []

        for index, item in enumerate(results, start=1):
            title = item.get("title", "未命名来源")
            url = item.get("url", "")
            snippet = (item.get("content") or "无摘要").strip()[:400]
            formatted.append(f"[联网来源{index}] {title}\nURL: {url}\n摘要: {snippet}")
            if url:
                sources.append(url)

        return RetrievalBundle(
            mode=self.name,
            summary=summary or "联网检索已完成。",
            snippets="\n\n".join(formatted),
            sources=sources,
            hit_count=len(sources),
            success=bool(sources),
        )
