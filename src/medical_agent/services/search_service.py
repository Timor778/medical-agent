from __future__ import annotations

from dataclasses import dataclass

from medical_agent.services.retrieval_service import WebSearchTool


@dataclass
class SearchBundle:
    summary: str
    snippets: str
    sources: list[str]


class MedicalSearchService:
    def __init__(self) -> None:
        self.tool = WebSearchTool()

    def search(self, query: str) -> SearchBundle:
        bundle = self.tool.retrieve(query)
        return SearchBundle(
            summary=bundle.summary,
            snippets=bundle.snippets,
            sources=bundle.sources,
        )
