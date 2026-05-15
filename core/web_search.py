"""
web_search.py — Tavily web search integration.

Returns structured SearchResult objects and optionally appends
them to a topic's sources.md.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from tavily import TavilyClient

from groupthink import config
from groupthink.core.topic_manager import TopicManager

# Character limits for content snippets in the research prompt
_SNIPPET_CHARS    = 500    # brief mode
_FULL_CONTENT_CHARS = 3_000  # full-content mode (per result)


@dataclass
class SearchResult:
    query:        str
    results:      list[dict]       # raw Tavily result dicts
    answer:       Optional[str]    # Tavily's synthesized answer
    full_content: bool = False     # whether raw article text was requested
    error:        Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_markdown(self) -> str:
        lines = [f"## Web Search: {self.query}\n"]
        if not self.ok:
            return f"{lines[0]}\n**ERROR:** {self.error}\n"
        if self.answer:
            lines += [f"### Summary\n\n{self.answer}\n"]
        lines.append("### Sources\n")
        limit = _FULL_CONTENT_CHARS if self.full_content else _SNIPPET_CHARS
        for r in self.results:
            title   = r.get("title", "Untitled")
            url     = r.get("url", "")
            score   = r.get("score", 0)
            # Prefer raw_content (full article) when available, fall back to snippet
            content = r.get("raw_content") or r.get("content", "")
            excerpt = content[:limit].replace("\n", " ")
            lines.append(f"- **[{title}]({url})** (relevance: {score:.2f})\n  {excerpt}\n")
        return "\n".join(lines)

    def urls(self) -> list[str]:
        return [r.get("url", "") for r in self.results if r.get("url")]


class WebSearch:
    """
    Thin async wrapper around TavilyClient.

    Usage:
        ws = WebSearch()
        result = await ws.search("quantum computing breakthroughs 2025",
                                  max_results=10, full_content=True)
    """

    def __init__(self):
        if not config.TAVILY_API_KEY:
            raise RuntimeError("TAVILY_API_KEY is not set — web search is disabled.")
        self._client = TavilyClient(api_key=config.TAVILY_API_KEY)

    async def search(
        self,
        query:          str,
        max_results:    int  = 5,
        include_answer: bool = True,
        search_depth:   str  = "advanced",
        full_content:   bool = False,
    ) -> SearchResult:
        """
        Run a Tavily search and return a SearchResult.
        Never raises — errors are captured in SearchResult.error.
        """
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.search(
                    query=query,
                    max_results=max_results,
                    include_answer=include_answer,
                    search_depth=search_depth,
                    include_raw_content=full_content,
                ),
            )
            return SearchResult(
                query=query,
                results=response.get("results", []),
                answer=response.get("answer"),
                full_content=full_content,
            )
        except Exception as exc:
            return SearchResult(query=query, results=[], answer=None, error=str(exc))

    async def search_and_save(
        self,
        query:       str,
        topic:       TopicManager,
        max_results: int  = 5,
        full_content: bool = False,
    ) -> SearchResult:
        """Run a search and append the results to the topic's sources.md."""
        result = await self.search(
            query,
            max_results=max_results,
            include_answer=True,
            full_content=full_content,
        )
        if result.ok:
            ts   = datetime.now().strftime("%Y-%m-%d %H:%M")
            note = f"[{ts}] Web search: \"{query}\""
            if result.answer:
                note += f" — {result.answer[:120]}"
            for url in result.urls():
                topic.append_source(url, note)
        return result
