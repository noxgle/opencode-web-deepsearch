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
import ipaddress
import json
import random
import re
import socket
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

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
    ".prose",
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
    "connect_timeout": 10,
    "max_content_length": 8000,
    # Maximum indented UTF-8 JSON response size; keep below host tool limits.
    "response_budget_bytes": 10_000,
    "max_response_bytes": 2_000_000,
    "max_concurrent_fetches": 5,
    "search_retries": 3,
    "fetch_retries": 2,
    "retry_backoff_seconds": 0.6,
    "max_total_time": 60,
    "max_redirects": 5,
    "chunk_size": 65536,
}

STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "been",
    "being",
    "between",
    "could",
    "does",
    "from",
    "have",
    "into",
    "just",
    "more",
    "most",
    "over",
    "such",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "using",
    "what",
    "when",
    "which",
    "with",
    "your",
    "http",
    "https",
    "www",
    "com",
    "org",
    "guide",
    "tutorial",
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
        self.error_counts: Counter = Counter()
        self.skipped_url_reasons: Counter = Counter()
        self.fetch_stats: Dict[str, int] = {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "non_html": 0,
        }

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
        self.error_counts = Counter()
        self.skipped_url_reasons = Counter()
        self.fetch_stats = {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "non_html": 0,
        }
        max_sources = max_sources or self.config["max_sources"]
        start_time = time.monotonic()
        current_query = query

        for _ in range(1, self.config["max_iterations"] + 1):
            if time.monotonic() - start_time >= self.config["max_total_time"]:
                break
            self.iterations_used += 1
            results = self._search_ddg(current_query, max_sources)
            if not results:
                break

            new_items: List[Dict[str, str]] = []
            for r in results:
                url = (r.get("url") or "").strip()
                if not url:
                    self.skipped_url_reasons["empty_url"] += 1
                    continue
                if url in self.seen_urls:
                    self.skipped_url_reasons["duplicate_url"] += 1
                    continue
                new_items.append(
                    {
                        "url": url,
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", ""),
                    }
                )

            if new_items:
                new_urls = [item["url"] for item in new_items]
                self.fetch_stats["attempted"] += len(new_urls)
                contents = self._extract_batch(new_urls)
                for item, content in zip(new_items, contents):
                    self.seen_urls.add(item["url"])
                    if not content:
                        self.skipped_url_reasons["empty_content"] += 1
                        continue
                    self.sources.append(
                        {
                            "url": item["url"],
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "content": content,
                        }
                    )
                    self.fetch_stats["succeeded"] += 1

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
            self.error_counts["ddg_missing"] += 1
            return []
        retries = max(1, int(self.config.get("search_retries", 1)))
        for attempt in range(retries):
            results: List[Dict[str, str]] = []
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
                if results:
                    return results
                self.error_counts["search_empty"] += 1
            except Exception as e:
                self.error_counts["search_error"] += 1
                print("Search error; retrying", file=sys.stderr)

            if attempt < retries - 1:
                self._sleep_backoff(attempt)

        return []

    def _extract_batch(self, urls: List[str]) -> List[str]:
        if AIOHTTP_AVAILABLE:
            try:
                return asyncio.run(self._extract_batch_async(urls))
            except Exception:
                pass
        return [self._extract_content(url) for url in urls]

    async def _extract_batch_async(self, urls: List[str]) -> List[str]:
        semaphore = asyncio.Semaphore(self.config["max_concurrent_fetches"])
        timeout = aiohttp.ClientTimeout(
            total=self.config["timeout"], connect=self.config["connect_timeout"]
        )

        async def fetch(url, session):
            async with semaphore:
                return await self._extract_content_async_inner(url, session)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = [fetch(url, session) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return ["" if isinstance(r, Exception) else r for r in results]

    async def _extract_content_async_inner(self, url, session):
        if not BeautifulSoup:
            self.error_counts["bs4_missing"] += 1
            return ""
        current_url = url
        retries = max(1, int(self.config.get("fetch_retries", 1)))
        for _ in range(int(self.config.get("max_redirects", 5)) + 1):
            if not self._is_safe_url(current_url):
                self.skipped_url_reasons["unsafe_url"] += 1
                self.fetch_stats["failed"] += 1
                return ""
            for attempt in range(retries):
                try:
                    async with session.get(
                        current_url,
                        headers={"User-Agent": USER_AGENT},
                        allow_redirects=False,
                    ) as resp:
                        if resp.status in (301, 302, 303, 307, 308):
                            location = resp.headers.get("Location")
                            if not location:
                                self.fetch_stats["failed"] += 1
                                return ""
                            current_url = urljoin(current_url, location)
                            break
                        if resp.status != 200:
                            self.error_counts[f"http_status_{resp.status}"] += 1
                            if resp.status in {429, 500, 502, 503, 504} and attempt < retries - 1:
                                self._sleep_backoff(attempt)
                                continue
                            self.fetch_stats["failed"] += 1
                            return ""
                        content_type = (resp.headers.get("Content-Type") or "").lower()
                        if not self._is_html_content_type(content_type):
                            self.fetch_stats["non_html"] += 1
                            self.fetch_stats["failed"] += 1
                            self.skipped_url_reasons["non_html_content_type"] += 1
                            return ""
                        max_bytes = int(self.config.get("max_response_bytes", 2_000_000))
                        body_parts = []
                        total = 0
                        async for chunk in resp.content.iter_chunked(int(self.config.get("chunk_size", 65536))):
                            body_parts.append(chunk.decode("utf-8", errors="ignore"))
                            total += len(body_parts[-1])
                            if total >= max_bytes:
                                break
                        return self._parse_html("".join(body_parts))
                except Exception:
                    self.error_counts["fetch_async_error"] += 1
                    if attempt < retries - 1:
                        self._sleep_backoff(attempt)
                        continue
                    self.fetch_stats["failed"] += 1
                    return ""
            else:
                self.fetch_stats["failed"] += 1
                return ""
        self.fetch_stats["failed"] += 1
        return ""

    def _extract_content(self, url: str) -> str:
        if not BeautifulSoup or not requests:
            if not BeautifulSoup:
                self.error_counts["bs4_missing"] += 1
            if not requests:
                self.error_counts["requests_missing"] += 1
            return ""
        current_url = url
        retries = max(1, int(self.config.get("fetch_retries", 1)))
        for _ in range(int(self.config.get("max_redirects", 5)) + 1):
            if not self._is_safe_url(current_url):
                self.skipped_url_reasons["unsafe_url"] += 1
                self.fetch_stats["failed"] += 1
                return ""
            for attempt in range(retries):
                try:
                    resp = requests.get(
                        current_url,
                        headers={"User-Agent": USER_AGENT},
                        timeout=(
                            self.config["connect_timeout"],
                            self.config["timeout"],
                        ),
                        allow_redirects=False,
                        stream=True,
                    )
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("Location")
                        resp.close()
                        if not location:
                            self.fetch_stats["failed"] += 1
                            return ""
                        current_url = urljoin(current_url, location)
                        break
                    if resp.status_code != 200:
                        resp.close()
                        self.error_counts[f"http_status_{resp.status_code}"] += 1
                        if resp.status_code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                            self._sleep_backoff(attempt)
                            continue
                        self.fetch_stats["failed"] += 1
                        return ""
                    content_type = (resp.headers.get("Content-Type") or "").lower()
                    if not self._is_html_content_type(content_type):
                        resp.close()
                        self.fetch_stats["non_html"] += 1
                        self.fetch_stats["failed"] += 1
                        self.skipped_url_reasons["non_html_content_type"] += 1
                        return ""
                    max_bytes = int(self.config.get("max_response_bytes", 2_000_000))
                    body_parts = []
                    total = 0
                    try:
                        for chunk in resp.iter_content(chunk_size=int(self.config.get("chunk_size", 65536))):
                            if not chunk:
                                continue
                            body_parts.append(chunk.decode("utf-8", errors="ignore"))
                            total += len(body_parts[-1])
                            if total >= max_bytes:
                                break
                    finally:
                        resp.close()
                    return self._parse_html("".join(body_parts))
                except Exception:
                    self.error_counts["fetch_sync_error"] += 1
                    if attempt < retries - 1:
                        self._sleep_backoff(attempt)
                        continue
                    self.fetch_stats["failed"] += 1
                    return ""
            else:
                self.fetch_stats["failed"] += 1
                return ""
        self.fetch_stats["failed"] += 1
        return ""

    def _is_safe_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname == "localhost" or hostname.endswith(".localhost"):
            return False
        try:
            infos = socket.getaddrinfo(hostname, None)
        except Exception:
            return False
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.version == 6 and ip.ipv4_mapped is not None:
                ip = ip.ipv4_mapped
            if not ip.is_global:
                return False
        return True

    def _is_html_content_type(self, content_type: str) -> bool:
        if not content_type:
            return True
        return "text/html" in content_type or "application/xhtml+xml" in content_type

    def _sleep_backoff(self, attempt: int) -> None:
        base = float(self.config.get("retry_backoff_seconds", 0.6))
        jitter = random.uniform(0.8, 1.2)
        time.sleep(base * (2**attempt) * jitter)

    def _parse_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for el in soup.select(", ".join(STRIP_ELEMENTS)):
            el.decompose()
        main = None
        for candidate in soup.select(", ".join(CONTENT_SELECTORS)):
            if len(candidate.get_text(strip=True)) > 100:
                main = candidate
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
        source_factor = min(1.0, len(self.sources) / max(1, self.config["max_sources"]))
        content_factor = min(1.0, avg_len / 2000)
        unique_domains = len(
            set(urlparse(s.get("url", "")).netloc for s in self.sources if s.get("url"))
        )
        domain_factor = unique_domains / max(1, len(self.sources))
        score = source_factor * 0.4 + content_factor * 0.4 + domain_factor * 0.2
        return round(max(0.0, min(1.0, score)), 2)

    def _refine_query(self, query: str) -> str:
        if not self.sources:
            return f"{query} guide tutorial"
        all_words = []
        for s in self.sources:
            title_tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{3,}\b", s["title"].lower())
            snippet_tokens = re.findall(
                r"\b[a-zA-Z][a-zA-Z0-9_-]{3,}\b", s.get("snippet", "").lower()
            )
            all_words.extend(title_tokens)
            all_words.extend(snippet_tokens)
        query_words = set(query.lower().split())
        new_words = [
            w
            for w in all_words
            if w not in query_words
            and w not in STOPWORDS
            and not w.isdigit()
            and len(w) <= 24
        ]
        if new_words:
            top_words = [word for word, _ in Counter(new_words).most_common(2)]
            return f"{query} {' '.join(top_words)}"
        return query

    @staticmethod
    def _serialize_response(response: Dict[str, Any]) -> str:
        return json.dumps(response, indent=2, ensure_ascii=False)

    def _build_raw_response(self, query: str) -> Dict[str, Any]:
        # Stable ranking prevents async fetch completion order from selecting content.
        sorted_sources = sorted(
            self.sources,
            key=lambda source: (
                -len(source.get("snippet", "")),
                source.get("url", ""),
            ),
        )
        clean_sources = []
        total_content_length = 0
        for source in sorted_sources:
            content = source.get("content", "") or ""
            total_content_length += len(content)
            clean_sources.append(
                {
                    "title": source.get("title", ""),
                    "url": source.get("url", ""),
                    "snippet": source.get("snippet", ""),
                    "content": content,
                    "domain": urlparse(source.get("url", "")).netloc,
                }
            )

        base = {
            "query": query,
            "sources": clean_sources,
            "iterations_used": self.iterations_used,
            "source_count": len(clean_sources),
            "domain_count": len(set(s["domain"] for s in clean_sources if s["domain"])),
            "errors": dict(self.error_counts),
            "skipped_urls": dict(self.skipped_url_reasons),
            "fetch_stats": self.fetch_stats,
        }
        budget = max(1, int(self.config["response_budget_bytes"]))
        if len(self._serialize_response(base).encode("utf-8")) <= budget:
            return base

        compact_sources = []
        for source in clean_sources:
            compact_sources.append({
                "title": source["title"],
                "url": source["url"],
                "snippet": source["snippet"],
                "domain": source["domain"],
                "content_length": len(source["content"]),
                "content": "",
            })
        compact = {
            **base,
            "sources": compact_sources,
            "mode": "compact",
            "truncated": True,
            "retained_content_count": 0,
            "omitted_content_count": sum(bool(s["content"]) for s in clean_sources),
            "total_content_length": total_content_length,
            "recovery_hint": "Fetch source URLs separately to retrieve omitted page content.",
        }
        # Retain full content in deterministic priority order while remaining within budget.
        for index, original in enumerate(clean_sources):
            if not original["content"]:
                continue
            content = original["content"]
            # Find the largest prefix that fits; even a partial page is useful,
            # and its original content_length remains available for recovery.
            low, high = 1, len(content)
            best = ""
            while low <= high:
                middle = (low + high) // 2
                compact["sources"][index]["content"] = content[:middle]
                compact["retained_content_count"] = 1
                compact["omitted_content_count"] = sum(
                    bool(s["content"]) for s in clean_sources
                ) - 1
                size = len(self._serialize_response(compact).encode("utf-8"))
                if size <= budget:
                    best = content[:middle]
                    low = middle + 1
                else:
                    high = middle - 1
            if best:
                compact["sources"][index]["content"] = best
                compact["sources"][index]["content_truncated"] = len(best) < len(content)
            else:
                compact["sources"][index]["content"] = ""
                compact["retained_content_count"] = 0
                compact["omitted_content_count"] = sum(bool(s["content"]) for s in clean_sources)
            if best:
                break
        if len(self._serialize_response(compact).encode("utf-8")) <= budget:
            return compact

        # If metadata alone is too large, drop the lowest-priority sources until it fits.
        for source in compact["sources"]:
            source["title"] = source["title"][:256]
            source["snippet"] = source["snippet"][:512]
        compact["query"] = query[:256]
        while compact["sources"] and len(self._serialize_response(compact).encode("utf-8")) > budget:
            compact["sources"].pop()
            compact["source_count"] = len(compact["sources"])
            compact["domain_count"] = len(set(s["domain"] for s in compact["sources"] if s["domain"]))
            compact["omitted_content_count"] = sum(bool(s["content"]) for s in clean_sources) - compact["retained_content_count"]
        if len(self._serialize_response(compact).encode("utf-8")) > budget:
            raise ValueError("response_budget_bytes is too small for the response envelope")
        return compact


def main():
    parser = argparse.ArgumentParser(
        description="WebDeepSearch - DuckDuckGo web search with deep search"
    )
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument(
        "--max-sources", type=int, default=5, help="Max sources per iteration (1-50)"
    )
    parser.add_argument(
        "--deep-search", choices=("true", "false"), type=str.lower,
        default="true", help="Enable iterative search loop (default: true)"
    )
    parser.add_argument("--max-iterations", type=int, default=5, help="Maximum refinement rounds (1-10)")
    parser.add_argument("--max-content-length", type=int, default=8000, help="Maximum extracted characters per page (500-8000)")
    parser.add_argument("--timeout", type=int, default=30, help="Per-request timeout in seconds (5-60)")
    parser.add_argument("--max-total-time", type=int, default=60, help="Maximum total search time in seconds (10-120)")
    args = parser.parse_args()

    limits = {
        "max_sources": (1, 50, args.max_sources),
        "max_iterations": (1, 10, args.max_iterations),
        "max_content_length": (500, 8000, args.max_content_length),
        "timeout": (5, 60, args.timeout),
        "max_total_time": (10, 120, args.max_total_time),
    }
    for name, (minimum, maximum, value) in limits.items():
        if not minimum <= value <= maximum:
            parser.error(f"{name.replace('_', '-')} must be between {minimum} and {maximum}")

    deep_search = args.deep_search == "true"
    config = {
        "max_iterations": args.max_iterations,
        "max_content_length": args.max_content_length,
        "timeout": args.timeout,
        "max_total_time": args.max_total_time,
    }
    agent = WebDeepSearch(config)
    result = agent.execute(
        query=args.query, max_sources=args.max_sources, deep_search=deep_search
    )
    output = WebDeepSearch._serialize_response(result)
    budget = int(agent.config["response_budget_bytes"])
    if len(output.encode("utf-8")) > budget:
        raise RuntimeError("Response exceeded configured response budget")
    print(output)


if __name__ == "__main__":
    main()
