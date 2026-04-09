#!/usr/bin/env python3
"""
WebDeepSearch - DuckDuckGo web search with deep search capabilities.

Searches DuckDuckGo, extracts content from sources, deduplicates,
and returns raw data JSON with sources containing title, url, snippet, content, and domain.

Usage:
    python3 WebSearchAgent.py --query "TypeScript 5.x features"
    python3 WebSearchAgent.py --query "React hooks" --max-sources 5 --deep-search true
"""

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# --- Dependency checks ---

try:
    from ddgs import DDGS

    DDG_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS

        DDG_AVAILABLE = True
    except ImportError:
        DDG_AVAILABLE = False

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# --- Constants ---

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CONTENT_SELECTORS = [
    "article",
    '[role="main"]',
    "main",
    ".post-content",
    ".article-content",
    ".content",
    "#content",
    ".entry-content",
    ".post-body",
    ".markdown-body",
    "prose",
]

STRIP_ELEMENTS = [
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "iframe",
    "noscript",
    "form",
    "button",
    ".sidebar",
    ".ad",
    ".advertisement",
    ".cookie",
]

DEFAULT_CONFIG = {
    "max_iterations": 5,
    "max_sources": 5,
    "min_confidence": 0.7,
    "timeout": 30,
    "max_content_length": 8000,
    "max_concurrent_fetches": 5,
}


class WebDeepSearch:
    """Web deep search agent with iterative refinement."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_CONFIG}
        if config:
            self.config.update(config)
        self.sources: List[Dict[str, Any]] = []
        self.seen_urls: set = set()
        self.iterations_used = 0

    def execute(
        self,
        query: str,
        max_sources: Optional[int] = None,
        deep_search: bool = True,
    ) -> Dict[str, Any]:
        """Execute web search and return raw data for AI evaluation."""
        self.sources = []
        self.seen_urls = set()
        self.iterations_used = 0
        max_sources = max_sources or self.config["max_sources"]
        current_query = query

        for _ in range(1, self.config["max_iterations"] + 1):
            self.iterations_used += 1
            results = self._search_ddg(current_query, max_sources)
            if not results:
                break

            new_urls = [r["url"] for r in results if r["url"] not in self.seen_urls]
            if new_urls:
                contents = self._extract_batch(new_urls)
                for url, content, result in zip(new_urls, contents, results):
                    if not content:
                        continue
                    self.sources.append(
                        {
                            "url": url,
                            "title": result.get("title", ""),
                            "snippet": result.get("snippet", ""),
                            "content": content,
                        }
                    )
                    self.seen_urls.add(url)

            if not deep_search:
                break
            if len(self.sources) >= max_sources * 2:
                break
            if self._calc_overall_confidence() >= self.config["min_confidence"]:
                break
            current_query = self._refine_query(query)

        return self._build_raw_response(query)

    def _search_ddg(self, query: str, max_results: int) -> List[Dict[str, str]]:
        if not DDG_AVAILABLE:
            print(
                "ERROR: duckduckgo-search not installed. Install with: pip install ddgs",
                file=sys.stderr,
            )
            return []
        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(
                    query, max_results=max_results, timeout=self.config["timeout"]
                ):
                    results.append(
                        {
                            "url": r.get("href", ""),
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                        }
                    )
        except Exception as e:
            print(f"Search error: {e}", file=sys.stderr)
        return results

    def _extract_batch(self, urls: List[str]) -> List[str]:
        if AIOHTTP_AVAILABLE:
            try:
                return asyncio.run(self._extract_batch_async(urls))
            except Exception:
                pass
        return [self._extract_content(url) for url in urls]

    async def _extract_batch_async(self, urls: List[str]) -> List[str]:
        semaphore = asyncio.Semaphore(self.config["max_concurrent_fetches"])
        timeout = aiohttp.ClientTimeout(total=self.config["timeout"])

        async def fetch(url, session):
            async with semaphore:
                return await self._extract_content_async_inner(url, session)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = [fetch(url, session) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return ["" if isinstance(r, Exception) else r for r in results]

    async def _extract_content_async_inner(self, url, session):
        if not BeautifulSoup or not requests:
            return ""
        try:
            async with session.get(
                url, headers={"User-Agent": USER_AGENT}, allow_redirects=True
            ) as resp:
                if resp.status != 200:
                    return ""
                return self._parse_html(await resp.text())
        except Exception:
            return ""

    def _extract_content(self, url: str) -> str:
        if not BeautifulSoup or not requests:
            return ""
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=self.config["timeout"],
                allow_redirects=True,
            )
            if resp.status_code != 200:
                return ""
            return self._parse_html(resp.text)
        except Exception:
            return ""

    def _parse_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for el in soup.select(", ".join(STRIP_ELEMENTS)):
            el.decompose()
        main = None
        for selector in CONTENT_SELECTORS:
            main = soup.select_one(selector)
            if main and len(main.get_text(strip=True)) > 100:
                break
        if not main:
            main = soup.body if soup.body else soup
        text = main.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)
        max_len = self.config["max_content_length"]
        if len(text) > max_len:
            text = text[:max_len] + "..."
        return text

    def _calc_overall_confidence(self) -> float:
        if not self.sources:
            return 0.0
        avg_len = sum(len(s.get("content", "")) for s in self.sources) / len(
            self.sources
        )
        source_factor = min(1.0, len(self.sources) / 5)
        content_factor = min(1.0, avg_len / 2000)
        return round(
            min(1.0, 0.5 * 0.5 + source_factor * 0.3 + content_factor * 0.2), 2
        )

    def _refine_query(self, query: str) -> str:
        if not self.sources:
            return f"{query} guide tutorial"
        all_words = []
        for s in self.sources:
            all_words.extend(re.findall(r"\b\w{4,}\b", s["title"].lower()))
        query_words = set(query.lower().split())
        new_words = [w for w in all_words if w not in query_words]
        if new_words:
            return f"{query} {Counter(new_words).most_common(1)[0][0]}"
        return query

    def _build_raw_response(self, query: str) -> Dict[str, Any]:
        sorted_sources = sorted(
            self.sources, key=lambda x: len(x.get("snippet", "")), reverse=True
        )
        clean_sources = []
        for s in sorted_sources:
            clean_sources.append(
                {
                    "title": s["title"],
                    "url": s["url"],
                    "snippet": s.get("snippet", ""),
                    "content": s.get("content", ""),
                    "domain": urlparse(s["url"]).netloc,
                }
            )
        return {
            "query": query,
            "sources": clean_sources,
            "iterations_used": self.iterations_used,
            "source_count": len(clean_sources),
            "domain_count": len(set(s["domain"] for s in clean_sources if s["domain"])),
        }


def main():
    parser = argparse.ArgumentParser(
        description="WebDeepSearch - DuckDuckGo web search with deep search"
    )
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument(
        "--max-sources", type=int, default=5, help="Max sources per iteration"
    )
    parser.add_argument(
        "--deep-search", type=str, default="true", help="Enable iterative search loop"
    )
    args = parser.parse_args()

    deep_search = args.deep_search.lower() == "true"
    agent = WebDeepSearch()
    result = agent.execute(
        query=args.query, max_sources=args.max_sources, deep_search=deep_search
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
