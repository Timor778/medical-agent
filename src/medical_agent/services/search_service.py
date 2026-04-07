from __future__ import annotations

from dataclasses import dataclass

from tavily import TavilyClient

from medical_agent.config import get_settings


@dataclass
class SearchBundle:
    summary: str
    snippets: str
    sources: list[str]


class MedicalSearchService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = TavilyClient(api_key=settings.tavily_api_key)
        self.max_results = settings.search_max_results

    def search(self, query: str) -> SearchBundle:
        response = self.client.search(
            query=query,
            search_depth="advanced",
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
            snippet = (item.get("content") or "无摘要").strip()[:500]
            formatted.append(f"[来源{index}] {title}\nURL: {url}\n摘要: {snippet}")
            if url:
                sources.append(url)

        return SearchBundle(summary=summary, snippets="\n\n".join(formatted), sources=sources)
