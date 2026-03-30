"""
Web Explorer — autonomous web browsing and data extraction engine.

Uses ROOT's existing web_search and fetch_url plugin tools to explore
the internet systematically. Provides structured search, deep crawling,
source monitoring, and market/news scanning capabilities.

This is ROOT's eyes on the web — it sees everything, fetches what matters,
and extracts the signal from the noise.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.web_explorer")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Immutable result types ────────────────────────────────────────


@dataclass(frozen=True)
class WebResult:
    """A single search result from the web."""
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebContent:
    """Fetched and extracted page content."""
    url: str
    title: str
    text: str  # extracted main content
    key_facts: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeepSearchResult:
    """Result of a multi-layer deep search."""
    query: str
    results_found: int
    pages_fetched: int
    key_findings: tuple[str, ...]
    sources: tuple[str, ...]


# ── WebExplorer ───────────────────────────────────────────────────


class WebExplorer:
    """Autonomous web browsing and data extraction engine.

    Wraps ROOT's DuckDuckGo (web_search) and httpx (fetch_url) plugin
    tools into higher-level exploration primitives: search, fetch+extract,
    deep search, source monitoring, and market/news scanning.
    """

    def __init__(
        self,
        plugins=None,
        llm=None,
        memory=None,
    ) -> None:
        self._plugins = plugins       # PluginEngine instance
        self._llm = llm               # LLMService / OpenAILLMService
        self._memory = memory          # MemoryEngine (optional, for caching)
        self._searches: int = 0
        self._pages_fetched: int = 0
        self._errors: int = 0

    # ── Core: search ──────────────────────────────────────────────

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        """Search the web via DuckDuckGo plugin and return structured results.

        Uses the web.web_search plugin tool. Falls back to direct DDGS
        import if plugins are unavailable.
        """
        if not query.strip():
            return []

        results: list[WebResult] = []
        try:
            if self._plugins:
                pr = await self._plugins.invoke(
                    "web_search", {"query": query},
                )
                if pr.success and pr.output:
                    raw = pr.output.get("results", [])
                    for item in raw[:max_results]:
                        results.append(WebResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("snippet", ""),
                        ))
                elif pr.error:
                    logger.warning("web_search plugin error: %s", pr.error)
            else:
                # Direct fallback — import ddgs
                results = await self._search_direct(query, max_results)

            self._searches += 1
            logger.debug("Search '%s' returned %d results", query, len(results))
        except Exception as exc:
            self._errors += 1
            logger.error("Search failed for '%s': %s", query, exc)

        return results

    async def _search_direct(self, query: str, max_results: int) -> list[WebResult]:
        """Direct DuckDuckGo search without plugin engine."""
        try:
            from ddgs import DDGS

            def _run():
                return DDGS().text(query, max_results=max_results)

            raw = await asyncio.to_thread(_run)
            return [
                WebResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                )
                for r in raw
            ]
        except Exception as exc:
            logger.error("Direct DDGS search failed: %s", exc)
            return []

    # ── Core: fetch and extract ───────────────────────────────────

    async def fetch_and_extract(self, url: str) -> WebContent:
        """Fetch a URL and use LLM to extract key information.

        Uses the web.fetch_url plugin tool for fetching, then optionally
        runs LLM extraction to pull out key facts.
        """
        if not url.strip():
            return WebContent(url=url, title="", text="")

        raw_text = ""
        try:
            if self._plugins:
                pr = await self._plugins.invoke(
                    "fetch_url", {"url": url, "max_chars": 20000},
                )
                if pr.success and pr.output:
                    raw_text = pr.output.get("content", "")
                elif pr.error:
                    logger.warning("fetch_url error for %s: %s", url, pr.error)
            else:
                raw_text = await self._fetch_direct(url)

            self._pages_fetched += 1
        except Exception as exc:
            self._errors += 1
            logger.error("Fetch failed for %s: %s", url, exc)
            return WebContent(url=url, title="", text="")

        # Extract title from first meaningful line
        title = ""
        for line in raw_text.split("."):
            candidate = line.strip()[:120]
            if len(candidate) > 10:
                title = candidate
                break

        # LLM extraction of key facts
        key_facts: tuple[str, ...] = ()
        if self._llm and raw_text and len(raw_text) > 100:
            try:
                key_facts = await self._extract_facts(raw_text, url)
            except Exception as exc:
                logger.warning("Fact extraction failed for %s: %s", url, exc)

        return WebContent(
            url=url,
            title=title,
            text=raw_text[:10000],
            key_facts=key_facts,
        )

    async def _fetch_direct(self, url: str) -> str:
        """Direct URL fetch without plugin engine."""
        import re
        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True,
            ) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        ),
                    },
                )
                raw = resp.text[:40000]
                cleaned = re.sub(
                    r"<(script|style)[^>]*>[\s\S]*?</\1>", "", raw,
                    flags=re.IGNORECASE,
                )
                cleaned = re.sub(r"<[^>]+>", " ", cleaned)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()[:20000]
                return cleaned
        except Exception as exc:
            logger.error("Direct fetch failed for %s: %s", url, exc)
            return ""

    async def _extract_facts(self, text: str, url: str) -> tuple[str, ...]:
        """Use LLM to extract key facts from page content."""
        prompt = (
            "Extract the 3-5 most important facts from this web content. "
            "Return ONLY a numbered list of facts, one per line. Be concise.\n\n"
            f"Source: {url}\n"
            f"Content:\n{text[:5000]}"
        )
        response = await self._llm.complete(
            system="You are a fact extraction engine. Return only numbered facts.",
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            max_tokens=400,
        )
        facts = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line and len(line) > 10:
                # Strip leading numbering like "1. " or "- "
                cleaned = line.lstrip("0123456789.-) ").strip()
                if cleaned:
                    facts.append(cleaned)
        return tuple(facts[:5])

    # ── Deep search ───────────────────────────────────────────────

    async def deep_search(
        self,
        query: str,
        follow_links: int = 3,
    ) -> DeepSearchResult:
        """Multi-layer deep search: search -> fetch top results -> synthesize.

        1. Initial search for query
        2. For top results, fetch full content
        3. Extract key facts and synthesize findings
        """
        # Step 1: initial search
        search_results = await self.search(query, max_results=5)
        if not search_results:
            return DeepSearchResult(
                query=query,
                results_found=0,
                pages_fetched=0,
                key_findings=(),
                sources=(),
            )

        # Step 2: fetch top pages concurrently (up to follow_links)
        urls_to_fetch = [r.url for r in search_results[:follow_links] if r.url]
        fetch_tasks = [self.fetch_and_extract(url) for url in urls_to_fetch]
        pages: list[WebContent] = await asyncio.gather(
            *fetch_tasks, return_exceptions=False,
        ) if fetch_tasks else []

        # Collect all facts and sources
        all_facts: list[str] = []
        all_sources: list[str] = []

        for result in search_results:
            if result.snippet:
                all_facts.append(result.snippet)
            if result.url:
                all_sources.append(result.url)

        for page in pages:
            if isinstance(page, WebContent):
                all_facts.extend(page.key_facts)

        # Step 3: synthesize with LLM if available
        key_findings: tuple[str, ...]
        if self._llm and all_facts:
            try:
                key_findings = await self._synthesize_findings(
                    query, all_facts, all_sources,
                )
            except Exception as exc:
                logger.warning("Deep search synthesis failed: %s", exc)
                key_findings = tuple(all_facts[:10])
        else:
            key_findings = tuple(all_facts[:10])

        return DeepSearchResult(
            query=query,
            results_found=len(search_results),
            pages_fetched=len([p for p in pages if isinstance(p, WebContent)]),
            key_findings=key_findings,
            sources=tuple(all_sources),
        )

    async def _synthesize_findings(
        self,
        query: str,
        facts: list[str],
        sources: list[str],
    ) -> tuple[str, ...]:
        """Use LLM to synthesize raw facts into key findings."""
        facts_text = "\n".join(f"- {f}" for f in facts[:20])
        prompt = (
            f"Query: {query}\n\n"
            f"Raw facts collected from web search:\n{facts_text}\n\n"
            "Synthesize these into 3-7 key findings. Each finding should be a "
            "concise, actionable statement. Remove duplicates. "
            "Return ONLY a numbered list."
        )
        response = await self._llm.complete(
            system="You are a research synthesis engine. Distill facts into key findings.",
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            max_tokens=500,
        )
        findings = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line and len(line) > 10:
                cleaned = line.lstrip("0123456789.-) ").strip()
                if cleaned:
                    findings.append(cleaned)
        return tuple(findings[:7])

    # ── Source monitoring ─────────────────────────────────────────

    async def monitor_source(
        self,
        source_name: str,
        url: str,
        keywords: list[str],
    ) -> list[dict]:
        """Fetch a URL and check for keyword matches.

        Useful for monitoring news sites, RSS feeds, data sources.
        Returns list of matching items with context.
        """
        if not url or not keywords:
            return []

        matches: list[dict] = []
        try:
            content = await self.fetch_and_extract(url)
            if not content.text:
                return []

            text_lower = content.text.lower()
            for keyword in keywords:
                kw_lower = keyword.lower()
                if kw_lower in text_lower:
                    # Extract context around the keyword
                    idx = text_lower.find(kw_lower)
                    start = max(0, idx - 100)
                    end = min(len(content.text), idx + len(keyword) + 200)
                    context = content.text[start:end].strip()
                    matches.append({
                        "source": source_name,
                        "url": url,
                        "keyword": keyword,
                        "context": context,
                        "timestamp": _now_iso(),
                    })

            logger.debug(
                "Monitor '%s': %d keyword matches in %s",
                source_name, len(matches), url,
            )
        except Exception as exc:
            self._errors += 1
            logger.error("Monitor source '%s' failed: %s", source_name, exc)

        return matches

    # ── Market scanning ───────────────────────────────────────────

    async def scan_markets(self) -> dict:
        """Quick scan of major market data: indices, crypto, commodities.

        Uses web search for each category and returns structured results.
        """
        categories = {
            "indices": "S&P 500 Nasdaq Dow Jones stock market today price",
            "crypto": "Bitcoin Ethereum cryptocurrency price today",
            "commodities": "gold oil price today commodity market",
            "forex": "USD EUR GBP forex exchange rate today",
        }

        market_data: dict[str, Any] = {"timestamp": _now_iso()}

        async def _scan_category(name: str, query: str) -> None:
            try:
                results = await self.search(query, max_results=3)
                market_data[name] = [
                    {"title": r.title, "snippet": r.snippet, "url": r.url}
                    for r in results
                ]
            except Exception as exc:
                logger.warning("Market scan '%s' failed: %s", name, exc)
                market_data[name] = []

        await asyncio.gather(
            *[_scan_category(name, query) for name, query in categories.items()]
        )

        logger.info("Market scan complete: %d categories", len(categories))
        return market_data

    # ── News scanning ─────────────────────────────────────────────

    async def scan_news(
        self,
        categories: Optional[list[str]] = None,
    ) -> list[dict]:
        """Search for latest news across categories.

        Default categories: markets, AI, technology, crypto, economy.
        Returns structured news items.
        """
        cats = categories or ["markets", "AI", "technology", "crypto", "economy"]

        _CATEGORY_QUERIES = {
            "markets": "stock market news today latest developments",
            "AI": "artificial intelligence AI news today latest breakthroughs",
            "technology": "technology news today latest innovations",
            "crypto": "cryptocurrency crypto news today latest developments",
            "economy": "economy news today GDP inflation interest rates",
            "startups": "startup news funding rounds today",
            "trading": "trading strategies market signals today",
            "science": "science breakthrough discovery today",
        }

        news_items: list[dict] = []

        async def _scan_category(category: str) -> None:
            query = _CATEGORY_QUERIES.get(
                category, f"{category} news today latest",
            )
            try:
                results = await self.search(query, max_results=3)
                for r in results:
                    news_items.append({
                        "category": category,
                        "title": r.title,
                        "snippet": r.snippet,
                        "url": r.url,
                        "timestamp": _now_iso(),
                    })
            except Exception as exc:
                logger.warning("News scan '%s' failed: %s", category, exc)

        await asyncio.gather(*[_scan_category(cat) for cat in cats])

        logger.info("News scan: %d items across %d categories", len(news_items), len(cats))
        return news_items

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return usage statistics for the web explorer."""
        return {
            "searches": self._searches,
            "pages_fetched": self._pages_fetched,
            "errors": self._errors,
            "has_plugins": self._plugins is not None,
            "has_llm": self._llm is not None,
            "has_memory": self._memory is not None,
        }
