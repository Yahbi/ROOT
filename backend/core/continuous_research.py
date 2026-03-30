"""
Continuous Research Engine — ROOT's autonomous knowledge acquisition system.

This is what makes ROOT ALWAYS learning. The engine continuously explores
the web, fetches data, analyzes findings, and feeds knowledge back into
ROOT's memory and learning systems. It operates autonomously on a background
loop, rotating through research domains and discovering new knowledge
without human prompting.

Three modes of operation:
1. TARGETED — research_topic() for specific queries
2. EXPLORATORY — explore_domain() for broad domain coverage
3. CONTINUOUS — start_loop() for 24/7 autonomous learning

All discoveries flow into memory (MemoryEngine), experience (ExperienceMemory),
and learning (LearningEngine) systems, making ROOT progressively smarter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.research")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Immutable result types ────────────────────────────────────────


@dataclass(frozen=True)
class ResearchResult:
    """Immutable result from a research operation."""
    topic: str
    domain: str
    findings: tuple[str, ...]    # Key facts discovered
    sources: tuple[str, ...]     # Where data came from
    insights: tuple[str, ...]    # Actionable insights
    knowledge_stored: int        # How many memory entries created
    quality_score: float         # 0-1 self-assessed quality
    timestamp: str


# ── Research domains and sub-topics ───────────────────────────────

_DOMAIN_SUBTOPICS: dict[str, list[str]] = {
    "trading": [
        "algorithmic trading strategies 2025",
        "quantitative finance machine learning signals",
        "options trading volatility strategies",
        "crypto DeFi yield farming opportunities",
        "market microstructure and order flow analysis",
        "momentum vs mean reversion strategy performance",
        "risk management portfolio optimization techniques",
        "high frequency trading latency arbitrage",
    ],
    "AI": [
        "latest large language model releases and benchmarks",
        "AI agent frameworks autonomous systems",
        "multimodal AI vision language models",
        "efficient LLM inference quantization techniques",
        "RAG retrieval augmented generation improvements",
        "AI coding assistants and code generation",
        "reinforcement learning from human feedback advances",
        "open source AI models and fine-tuning",
    ],
    "markets": [
        "stock market trends sector rotation analysis",
        "cryptocurrency market analysis Bitcoin Ethereum",
        "commodities gold oil supply demand",
        "emerging markets investment opportunities",
        "IPO market and pre-IPO opportunities",
        "bond market yield curve analysis",
        "real estate market data analytics",
        "forex currency pair trends and analysis",
    ],
    "technology": [
        "cloud computing infrastructure innovations",
        "cybersecurity threats and defense strategies",
        "edge computing and IoT developments",
        "quantum computing progress and applications",
        "blockchain technology enterprise applications",
        "developer tools and productivity innovations",
        "API economy and microservices architecture",
        "no-code low-code platform developments",
    ],
    "science": [
        "breakthrough scientific discoveries this month",
        "biotechnology gene therapy advances",
        "materials science and nanotechnology",
        "space technology and satellite innovations",
        "climate technology and carbon capture",
        "neuroscience and brain-computer interfaces",
        "renewable energy efficiency improvements",
        "computational biology protein folding",
    ],
    "math": [
        "applied mathematics machine learning theory",
        "statistical methods for financial modeling",
        "graph theory and network analysis applications",
        "optimization algorithms for real-world problems",
        "Bayesian inference practical applications",
        "time series analysis forecasting methods",
        "information theory and data compression",
        "stochastic processes Monte Carlo methods",
    ],
    "economics": [
        "macroeconomic indicators and forecasts",
        "monetary policy central bank decisions",
        "inflation trends and predictions",
        "labor market employment data analysis",
        "trade policy and global supply chains",
        "digital economy and platform economics",
        "behavioral economics decision making",
        "economic models and simulation techniques",
    ],
    "crypto": [
        "DeFi protocol innovations and TVL trends",
        "NFT market evolution and utility tokens",
        "layer 2 scaling solutions Ethereum rollups",
        "crypto regulation and compliance updates",
        "stablecoin mechanisms and risks",
        "cross-chain interoperability protocols",
        "tokenomics design and governance models",
        "MEV and on-chain analytics tools",
    ],
    "startups": [
        "Y Combinator latest batch startup trends",
        "micro SaaS bootstrapped business ideas",
        "AI startup funding and valuations",
        "indie hacker revenue strategies",
        "product-led growth tactics and metrics",
        "startup automation and no-code tools",
        "developer tools market and API businesses",
        "remote work tools and collaboration platforms",
    ],
    "automation": [
        "business process automation with AI",
        "workflow automation tools and platforms",
        "robotic process automation RPA developments",
        "email marketing automation strategies",
        "social media automation and scheduling",
        "data pipeline automation ETL tools",
        "CI/CD deployment automation practices",
        "AI-powered customer support automation",
    ],
}

_BRIEFING_TOPICS = [
    "stock market major indices today performance",
    "cryptocurrency Bitcoin Ethereum price news today",
    "artificial intelligence AI news breakthroughs today",
    "technology industry news trends today",
    "trading opportunities signals market movers today",
    "startup funding news acquisitions today",
    "economic indicators data releases today",
]


# ── ContinuousResearch ───────────────────────────────────────────


class ContinuousResearch:
    """Autonomous research engine that continuously explores, learns, and stores.

    Integrates with ROOT's WebExplorer for web access, LLM for analysis,
    MemoryEngine for storage, ExperienceMemory for wisdom, LearningEngine
    for feedback, and MessageBus for broadcasting discoveries.
    """

    def __init__(
        self,
        llm=None,
        memory=None,
        experience_memory=None,
        learning=None,
        bus=None,
        plugins=None,
        document_analyzer=None,
    ) -> None:
        self._llm = llm                         # LLMService / OpenAILLMService
        self._memory = memory                    # MemoryEngine
        self._experience_memory = experience_memory  # ExperienceMemory
        self._learning = learning                # LearningEngine
        self._bus = bus                          # MessageBus
        self._plugins = plugins                  # PluginEngine
        self._document_analyzer = document_analyzer  # DocumentAnalyzer

        # Lazy-init web explorer (avoids circular import / init order issues)
        self._explorer = None

        # Background loop state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._domain_index = 0
        self._domains = list(_DOMAIN_SUBTOPICS.keys())

        # Stats
        self._topics_researched: int = 0
        self._knowledge_stored: int = 0
        self._errors: int = 0
        self._cycles: int = 0

    @property
    def explorer(self):
        """Lazy-initialize WebExplorer to avoid import-time dependency issues."""
        if self._explorer is None:
            from backend.core.web_explorer import WebExplorer
            self._explorer = WebExplorer(
                plugins=self._plugins,
                llm=self._llm,
                memory=self._memory,
            )
        return self._explorer

    # ── Targeted research ─────────────────────────────────────────

    async def research_topic(
        self,
        topic: str,
        depth: str = "standard",
    ) -> ResearchResult:
        """Research a specific topic and store findings in memory.

        Depth levels:
        - "quick"    — single search, extract key facts
        - "standard" — search + fetch top pages + synthesize
        - "deep"     — deep search with link following + full analysis

        Steps:
        1. Web search for topic
        2. Fetch and extract key information from results
        3. LLM synthesizes findings into structured knowledge
        4. Store findings in memory engine with proper tags
        5. Record experience (success/failure/lesson)
        6. Return structured result
        """
        logger.info("Researching topic: '%s' (depth=%s)", topic, depth)
        domain = self._classify_domain(topic)
        findings: list[str] = []
        sources: list[str] = []
        insights: list[str] = []
        knowledge_count = 0
        quality = 0.0

        try:
            # Step 1-2: search and fetch based on depth
            if depth == "quick":
                search_results = await self.explorer.search(topic, max_results=5)
                for r in search_results:
                    if r.snippet:
                        findings.append(r.snippet)
                    if r.url:
                        sources.append(r.url)

            elif depth == "deep":
                deep = await self.explorer.deep_search(topic, follow_links=5)
                findings.extend(deep.key_findings)
                sources.extend(deep.sources)

            else:  # standard
                deep = await self.explorer.deep_search(topic, follow_links=3)
                findings.extend(deep.key_findings)
                sources.extend(deep.sources)

            # Step 3: LLM synthesis — extract insights
            if self._llm and findings:
                insights = await self._synthesize_insights(topic, findings)
                quality = await self._assess_quality(topic, findings, insights)

            # Step 4: store findings in memory
            knowledge_count = await self._store_findings(
                topic, domain, findings, insights, sources,
            )

            # Step 5: record experience
            self._record_success(topic, domain, knowledge_count)

            self._topics_researched += 1
            self._knowledge_stored += knowledge_count

            logger.info(
                "Research complete: '%s' — %d findings, %d insights, %d stored",
                topic, len(findings), len(insights), knowledge_count,
            )

        except Exception as exc:
            self._errors += 1
            logger.error("Research failed for '%s': %s", topic, exc)
            self._record_failure(topic, domain, str(exc))
            quality = 0.0

        return ResearchResult(
            topic=topic,
            domain=domain,
            findings=tuple(findings),
            sources=tuple(sources),
            insights=tuple(insights),
            knowledge_stored=knowledge_count,
            quality_score=quality,
            timestamp=_now_iso(),
        )

    async def _synthesize_insights(
        self, topic: str, findings: list[str],
    ) -> list[str]:
        """Use LLM (+ DocumentAnalyzer when available) to extract actionable insights."""
        findings_text = "\n".join(f"- {f}" for f in findings[:15])

        # Use DocumentAnalyzer for structured analysis of findings if available
        doc_analysis_context = ""
        if self._document_analyzer and findings_text and len(findings_text) > 50:
            try:
                analysis_result = await self._document_analyzer.analyze_text(
                    findings_text,
                    analysis_type="general",
                )
                if analysis_result and hasattr(analysis_result, "summary"):
                    doc_analysis_context = (
                        f"\n\nDocument analysis (structured):\n{analysis_result.summary[:400]}"
                    )
                    if hasattr(analysis_result, "key_points") and analysis_result.key_points:
                        doc_analysis_context += "\nKey points: " + "; ".join(
                            str(p)[:80] for p in analysis_result.key_points[:5]
                        )
            except Exception as da_exc:
                logger.debug("DocumentAnalyzer in research synthesis failed: %s", da_exc)

        prompt = (
            f"Topic: {topic}\n\n"
            f"Research findings:\n{findings_text}\n"
            f"{doc_analysis_context}\n\n"
            "Extract 3-5 actionable insights. Each should be:\n"
            "- Specific and concrete (not vague)\n"
            "- Relevant to AI development, trading, automation, or business\n"
            "- Something ROOT can act on or learn from\n\n"
            "Return ONLY a numbered list of insights."
        )
        response = await self._llm.complete(
            system=(
                "You are ROOT's research analyst. Extract actionable insights "
                "that help ROOT become smarter and generate value."
            ),
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            max_tokens=500,
        )
        insights = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line and len(line) > 15:
                cleaned = line.lstrip("0123456789.-) ").strip()
                if cleaned:
                    insights.append(cleaned)
        return insights[:5]

    async def _assess_quality(
        self, topic: str, findings: list[str], insights: list[str],
    ) -> float:
        """Self-assess the quality of research results (0-1)."""
        # Heuristic scoring — no LLM call needed
        score = 0.0

        # Findings count (0-0.3)
        if len(findings) >= 5:
            score += 0.3
        elif len(findings) >= 3:
            score += 0.2
        elif len(findings) >= 1:
            score += 0.1

        # Insights quality (0-0.3)
        if len(insights) >= 3:
            score += 0.3
        elif len(insights) >= 1:
            score += 0.15

        # Content richness — average finding length (0-0.2)
        if findings:
            avg_len = sum(len(f) for f in findings) / len(findings)
            if avg_len > 100:
                score += 0.2
            elif avg_len > 50:
                score += 0.1

        # Diversity of findings (0-0.2)
        if findings:
            unique_words = set()
            for f in findings:
                unique_words.update(f.lower().split()[:10])
            if len(unique_words) > 30:
                score += 0.2
            elif len(unique_words) > 15:
                score += 0.1

        return min(1.0, score)

    async def _store_findings(
        self,
        topic: str,
        domain: str,
        findings: list[str],
        insights: list[str],
        sources: list[str],
    ) -> int:
        """Store research findings in memory engine. Returns count of entries stored."""
        if not self._memory:
            return 0

        from backend.models.memory import MemoryEntry, MemoryType

        stored = 0
        tags = ["research", domain, "auto_research"]

        # Store each significant finding as FACT
        for finding in findings[:10]:
            if len(finding) < 20:
                continue
            try:
                self._memory.store(MemoryEntry(
                    content=f"[Research:{topic}] {finding}",
                    memory_type=MemoryType.FACT,
                    tags=[*tags, "finding"],
                    source="continuous_research",
                    confidence=0.7,
                ))
                stored += 1
            except Exception as exc:
                logger.debug("Failed to store finding: %s", exc)

        # Store insights as LEARNING
        for insight in insights[:5]:
            if len(insight) < 20:
                continue
            try:
                self._memory.store(MemoryEntry(
                    content=f"[Insight:{topic}] {insight}",
                    memory_type=MemoryType.LEARNING,
                    tags=[*tags, "insight"],
                    source="continuous_research",
                    confidence=0.75,
                ))
                stored += 1
            except Exception as exc:
                logger.debug("Failed to store insight: %s", exc)

        # Store a research summary as OBSERVATION
        if findings:
            summary = (
                f"Researched '{topic}' ({domain}): "
                f"{len(findings)} findings, {len(insights)} insights. "
                f"Sources: {', '.join(sources[:3])}"
            )
            try:
                self._memory.store(MemoryEntry(
                    content=summary,
                    memory_type=MemoryType.OBSERVATION,
                    tags=[*tags, "summary"],
                    source="continuous_research",
                    confidence=0.8,
                ))
                stored += 1
            except Exception as exc:
                logger.debug("Failed to store summary: %s", exc)

        return stored

    def _record_success(self, topic: str, domain: str, count: int) -> None:
        """Record successful research as experience."""
        if not self._experience_memory:
            return
        try:
            self._experience_memory.record_experience(
                experience_type="success",
                domain=domain,
                title=f"Research: {topic}",
                description=f"Successfully researched '{topic}', stored {count} knowledge entries.",
                context={"topic": topic, "knowledge_stored": count},
                confidence=0.8,
                tags=["research", "auto_research", domain],
            )
        except Exception as exc:
            logger.debug("Failed to record success experience: %s", exc)

    def _record_failure(self, topic: str, domain: str, error: str) -> None:
        """Record failed research as experience."""
        if not self._experience_memory:
            return
        try:
            self._experience_memory.record_experience(
                experience_type="failure",
                domain=domain,
                title=f"Research failed: {topic}",
                description=f"Research on '{topic}' failed: {error[:200]}",
                context={"topic": topic, "error": error[:200]},
                confidence=0.9,
                tags=["research", "failure", domain],
            )
        except Exception as exc:
            logger.debug("Failed to record failure experience: %s", exc)

    def _classify_domain(self, topic: str) -> str:
        """Classify a topic into a research domain based on keyword matching."""
        topic_lower = topic.lower()
        domain_keywords: dict[str, list[str]] = {
            "trading": ["trading", "stock", "options", "forex", "hedge", "portfolio", "signal"],
            "AI": ["ai", "llm", "machine learning", "neural", "gpt", "model", "transformer"],
            "markets": ["market", "index", "s&p", "nasdaq", "dow", "commodity", "bond"],
            "technology": ["tech", "software", "cloud", "devops", "api", "framework"],
            "science": ["science", "biology", "physics", "chemistry", "research paper"],
            "math": ["math", "statistics", "algorithm", "optimization", "probability"],
            "economics": ["economy", "inflation", "gdp", "monetary", "fiscal", "unemployment"],
            "crypto": ["crypto", "bitcoin", "ethereum", "defi", "nft", "blockchain", "token"],
            "startups": ["startup", "saas", "founder", "funding", "vc", "bootstrap", "indie"],
            "automation": ["automation", "workflow", "rpa", "bot", "pipeline", "ci/cd"],
        }
        best_domain = "general"
        best_score = 0
        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in topic_lower)
            if score > best_score:
                best_score = score
                best_domain = domain
        return best_domain

    # ── Exploratory research ──────────────────────────────────────

    async def explore_domain(self, domain: str) -> list[ResearchResult]:
        """Research a domain broadly by generating sub-topics and researching each.

        Valid domains: trading, AI, markets, technology, science, math,
                      economics, crypto, startups, automation
        """
        logger.info("Exploring domain: %s", domain)

        # Get sub-topics — from predefined list or generate via LLM
        subtopics = await self._generate_subtopics(domain)

        # Research each sub-topic (limit concurrency to avoid rate limits)
        results: list[ResearchResult] = []
        semaphore = asyncio.Semaphore(3)

        async def _bounded_research(topic: str) -> Optional[ResearchResult]:
            async with semaphore:
                try:
                    return await self.research_topic(topic, depth="standard")
                except Exception as exc:
                    logger.warning("Sub-topic research failed (%s): %s", topic, exc)
                    return None

        tasks = [_bounded_research(t) for t in subtopics]
        raw_results = await asyncio.gather(*tasks)

        for r in raw_results:
            if r is not None:
                results.append(r)

        logger.info(
            "Domain exploration '%s': %d/%d sub-topics researched",
            domain, len(results), len(subtopics),
        )
        return results

    async def _generate_subtopics(self, domain: str) -> list[str]:
        """Generate 5-10 sub-topics for a domain.

        Uses predefined topics first, with LLM augmentation if available.
        """
        # Start with predefined sub-topics
        predefined = _DOMAIN_SUBTOPICS.get(domain, [])

        if self._llm and len(predefined) > 0:
            # Pick a random subset and ask LLM for additional related topics
            seed_topics = random.sample(predefined, min(3, len(predefined)))
            try:
                prompt = (
                    f"Domain: {domain}\n"
                    f"Existing topics: {', '.join(seed_topics)}\n\n"
                    "Generate 5 more specific, timely research topics in this domain. "
                    "Focus on what's happening RIGHT NOW — recent developments, "
                    "emerging trends, and actionable opportunities. "
                    "Return ONLY a numbered list of topics."
                )
                response = await self._llm.complete(
                    system="You are a research director. Generate specific, timely research topics.",
                    messages=[{"role": "user", "content": prompt}],
                    model_tier="fast",
                    max_tokens=300,
                )
                llm_topics = []
                for line in response.strip().split("\n"):
                    line = line.strip()
                    if line and len(line) > 10:
                        cleaned = line.lstrip("0123456789.-) ").strip()
                        if cleaned:
                            llm_topics.append(cleaned)

                # Combine: 3 predefined + up to 5 LLM-generated
                combined = seed_topics + llm_topics[:5]
                random.shuffle(combined)
                return combined[:8]
            except Exception as exc:
                logger.warning("LLM sub-topic generation failed: %s", exc)

        # Fallback: random selection from predefined
        if predefined:
            return random.sample(predefined, min(7, len(predefined)))
        return [f"{domain} latest developments and trends"]

    # ── Daily briefing ────────────────────────────────────────────

    async def daily_briefing(self) -> str:
        """Generate a concise daily briefing by scanning key topics.

        Searches for: market news, AI developments, trading opportunities,
        tech trends. Synthesizes into a brief report and stores in memory.
        """
        logger.info("Generating daily briefing")

        all_findings: list[str] = []
        all_sources: list[str] = []

        # Search each briefing topic concurrently
        semaphore = asyncio.Semaphore(3)

        async def _search_topic(query: str) -> None:
            async with semaphore:
                try:
                    results = await self.explorer.search(query, max_results=3)
                    for r in results:
                        if r.snippet:
                            all_findings.append(f"[{query.split()[0]}] {r.snippet}")
                        if r.url:
                            all_sources.append(r.url)
                except Exception as exc:
                    logger.warning("Briefing search failed for '%s': %s", query, exc)

        await asyncio.gather(*[_search_topic(q) for q in _BRIEFING_TOPICS])

        # Synthesize briefing with LLM
        briefing = ""
        if self._llm and all_findings:
            findings_text = "\n".join(f"- {f}" for f in all_findings[:25])
            try:
                briefing = await self._llm.complete(
                    system=(
                        "You are ROOT's intelligence briefing officer. Create a "
                        "concise daily briefing for Yohan. Focus on: market status, "
                        "AI news, trading opportunities, tech trends. "
                        "Use bullet points. Be specific with numbers and data."
                    ),
                    messages=[{"role": "user", "content": (
                        f"Today's raw intelligence:\n{findings_text}\n\n"
                        "Create a concise daily briefing. Sections: "
                        "Markets, AI/Tech, Opportunities, Action Items."
                    )}],
                    model_tier="fast",
                    max_tokens=800,
                )
            except Exception as exc:
                logger.warning("Briefing synthesis failed: %s", exc)
                briefing = "Briefing synthesis unavailable.\n" + "\n".join(
                    f"- {f}" for f in all_findings[:10]
                )
        else:
            briefing = "Daily Briefing (raw):\n" + "\n".join(
                f"- {f}" for f in all_findings[:10]
            )

        # Store briefing in memory as OBSERVATION
        if self._memory and briefing:
            from backend.models.memory import MemoryEntry, MemoryType
            try:
                self._memory.store(MemoryEntry(
                    content=f"Daily Briefing ({_now_iso()[:10]}): {briefing[:500]}",
                    memory_type=MemoryType.OBSERVATION,
                    tags=["briefing", "daily", "markets", "AI", "auto_research"],
                    source="continuous_research",
                    confidence=0.8,
                ))
            except Exception as exc:
                logger.debug("Failed to store briefing: %s", exc)

        logger.info("Daily briefing generated: %d chars", len(briefing))
        return briefing

    # ── Analyze and learn ─────────────────────────────────────────

    async def analyze_and_learn(
        self, content: str, source: str = "",
    ) -> dict:
        """Analyze content and extract knowledge for storage.

        1. LLM extracts key facts, patterns, actionable insights
        2. Each fact stored as a separate memory entry
        3. Patterns stored as LEARNING type
        4. Return count of new knowledge items
        """
        if not self._llm:
            return {"facts": 0, "patterns": 0, "insights": 0, "total": 0}

        logger.info("Analyzing content from source: %s", source or "unknown")

        # Extract structured knowledge via LLM
        prompt = (
            "Analyze this content and extract:\n"
            "1. KEY FACTS — specific, verifiable pieces of information\n"
            "2. PATTERNS — recurring themes, trends, or correlations\n"
            "3. ACTIONABLE INSIGHTS — things ROOT can do or decide based on this\n\n"
            f"Source: {source}\n"
            f"Content:\n{content[:5000]}\n\n"
            "Respond in JSON format:\n"
            '{"facts": ["fact1", ...], "patterns": ["pattern1", ...], "insights": ["insight1", ...]}'
        )

        try:
            response = await self._llm.complete(
                system="You are a knowledge extraction engine. Return valid JSON only.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                max_tokens=600,
            )

            # Parse JSON response
            parsed = self._parse_json_response(response)
            facts = parsed.get("facts", [])
            patterns = parsed.get("patterns", [])
            insights = parsed.get("insights", [])

        except Exception as exc:
            logger.warning("Content analysis failed: %s", exc)
            return {"facts": 0, "patterns": 0, "insights": 0, "total": 0}

        # Store in memory
        stored_facts = 0
        stored_patterns = 0
        stored_insights = 0

        if self._memory:
            from backend.models.memory import MemoryEntry, MemoryType

            src_tag = source.replace(" ", "_").lower() if source else "analysis"
            base_tags = ["analyzed", src_tag]

            for fact in facts[:10]:
                if len(fact) < 15:
                    continue
                try:
                    self._memory.store(MemoryEntry(
                        content=f"[Fact] {fact}",
                        memory_type=MemoryType.FACT,
                        tags=[*base_tags, "fact"],
                        source="continuous_research",
                        confidence=0.7,
                    ))
                    stored_facts += 1
                except Exception:
                    pass

            for pattern in patterns[:5]:
                if len(pattern) < 15:
                    continue
                try:
                    self._memory.store(MemoryEntry(
                        content=f"[Pattern] {pattern}",
                        memory_type=MemoryType.LEARNING,
                        tags=[*base_tags, "pattern"],
                        source="continuous_research",
                        confidence=0.65,
                    ))
                    stored_patterns += 1
                except Exception:
                    pass

            for insight in insights[:5]:
                if len(insight) < 15:
                    continue
                try:
                    self._memory.store(MemoryEntry(
                        content=f"[Insight] {insight}",
                        memory_type=MemoryType.LEARNING,
                        tags=[*base_tags, "insight"],
                        source="continuous_research",
                        confidence=0.7,
                    ))
                    stored_insights += 1
                except Exception:
                    pass

        total = stored_facts + stored_patterns + stored_insights
        self._knowledge_stored += total
        logger.info(
            "Analysis complete: %d facts, %d patterns, %d insights stored",
            stored_facts, stored_patterns, stored_insights,
        )

        return {
            "facts": stored_facts,
            "patterns": stored_patterns,
            "insights": stored_insights,
            "total": total,
        }

    def _parse_json_response(self, response: str) -> dict:
        """Parse a JSON response from LLM, handling common formatting issues."""
        text = response.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
        logger.debug("Failed to parse JSON from LLM response")
        return {}

    # ── Hypothesis testing ────────────────────────────────────────

    async def backtest_hypothesis(
        self, hypothesis: str, data_context: str = "",
    ) -> dict:
        """Test a hypothesis against web evidence.

        1. LLM generates testable predictions from hypothesis
        2. Search for historical evidence
        3. Score hypothesis against evidence
        4. Store result in prediction_ledger pattern
        """
        if not self._llm:
            return {
                "hypothesis": hypothesis,
                "predictions": [],
                "evidence_score": 0.0,
                "verdict": "untestable",
            }

        logger.info("Backtesting hypothesis: %s", hypothesis[:100])

        # Step 1: generate testable predictions
        try:
            pred_prompt = (
                f"Hypothesis: {hypothesis}\n"
                + (f"Context: {data_context}\n" if data_context else "")
                + "\nGenerate 3-5 specific, testable predictions from this hypothesis. "
                "Each prediction should be something we can verify by searching the web. "
                "Return ONLY a numbered list of predictions."
            )
            pred_response = await self._llm.complete(
                system="You are a hypothesis testing engine. Generate testable predictions.",
                messages=[{"role": "user", "content": pred_prompt}],
                model_tier="fast",
                max_tokens=400,
            )
            predictions = []
            for line in pred_response.strip().split("\n"):
                line = line.strip()
                if line and len(line) > 15:
                    cleaned = line.lstrip("0123456789.-) ").strip()
                    if cleaned:
                        predictions.append(cleaned)
            predictions = predictions[:5]
        except Exception as exc:
            logger.warning("Prediction generation failed: %s", exc)
            return {
                "hypothesis": hypothesis,
                "predictions": [],
                "evidence_score": 0.0,
                "verdict": "generation_failed",
            }

        if not predictions:
            return {
                "hypothesis": hypothesis,
                "predictions": [],
                "evidence_score": 0.0,
                "verdict": "no_predictions",
            }

        # Step 2: search for evidence for each prediction
        evidence: list[dict] = []
        for prediction in predictions:
            try:
                results = await self.explorer.search(prediction, max_results=3)
                snippets = [r.snippet for r in results if r.snippet]
                evidence.append({
                    "prediction": prediction,
                    "evidence_found": len(results),
                    "snippets": snippets[:3],
                })
            except Exception as exc:
                logger.debug("Evidence search failed for prediction: %s", exc)
                evidence.append({
                    "prediction": prediction,
                    "evidence_found": 0,
                    "snippets": [],
                })

        # Step 3: score hypothesis against evidence
        try:
            evidence_text = ""
            for e in evidence:
                evidence_text += f"\nPrediction: {e['prediction']}\n"
                evidence_text += f"Evidence found: {e['evidence_found']} results\n"
                for s in e["snippets"]:
                    evidence_text += f"  - {s[:150]}\n"

            score_prompt = (
                f"Hypothesis: {hypothesis}\n\n"
                f"Evidence gathered:\n{evidence_text}\n\n"
                "Score this hypothesis on a scale of 0.0 to 1.0 based on the evidence. "
                "Also provide a one-sentence verdict. "
                'Respond in JSON: {"score": 0.X, "verdict": "..."}'
            )
            score_response = await self._llm.complete(
                system="You are an evidence evaluator. Score hypotheses objectively.",
                messages=[{"role": "user", "content": score_prompt}],
                model_tier="fast",
                max_tokens=200,
            )
            score_data = self._parse_json_response(score_response)
            evidence_score = float(score_data.get("score", 0.5))
            verdict = score_data.get("verdict", "inconclusive")
        except Exception as exc:
            logger.warning("Hypothesis scoring failed: %s", exc)
            evidence_score = 0.5
            verdict = "scoring_failed"

        # Step 4: store result
        result = {
            "hypothesis": hypothesis,
            "predictions": predictions,
            "evidence": evidence,
            "evidence_score": evidence_score,
            "verdict": verdict,
            "timestamp": _now_iso(),
        }

        # Store as experience
        if self._experience_memory:
            try:
                exp_type = "success" if evidence_score >= 0.6 else "lesson"
                self._experience_memory.record_experience(
                    experience_type=exp_type,
                    domain="research",
                    title=f"Hypothesis test: {hypothesis[:80]}",
                    description=(
                        f"Tested hypothesis with {len(predictions)} predictions. "
                        f"Score: {evidence_score:.2f}. Verdict: {verdict}"
                    ),
                    context={"score": evidence_score, "predictions_count": len(predictions)},
                    confidence=min(0.9, evidence_score),
                    tags=["hypothesis", "backtest", "research"],
                )
            except Exception as exc:
                logger.debug("Failed to record hypothesis experience: %s", exc)

        # Store as memory
        if self._memory:
            from backend.models.memory import MemoryEntry, MemoryType
            try:
                self._memory.store(MemoryEntry(
                    content=(
                        f"[Hypothesis Test] {hypothesis} — "
                        f"Score: {evidence_score:.2f}, Verdict: {verdict}"
                    ),
                    memory_type=MemoryType.LEARNING,
                    tags=["hypothesis", "backtest", "research"],
                    source="continuous_research",
                    confidence=min(0.9, evidence_score),
                ))
            except Exception as exc:
                logger.debug("Failed to store hypothesis result: %s", exc)

        logger.info(
            "Hypothesis test complete: score=%.2f, verdict=%s",
            evidence_score, verdict,
        )
        return result

    # ── Background loop ───────────────────────────────────────────

    async def start_loop(self, interval: int = 1800) -> None:
        """Start the continuous research background loop.

        Rotates through research domains, picks topics based on curiosity
        or random selection, researches them, and broadcasts findings.

        Args:
            interval: Seconds between research cycles (default 30 min).
        """
        if self._running:
            logger.warning("Research loop already running")
            return

        self._running = True
        logger.info("Starting continuous research loop (interval=%ds)", interval)

        self._task = asyncio.create_task(self._loop(interval))

    async def _loop(self, interval: int) -> None:
        """Main research loop — runs until stopped."""
        while self._running:
            try:
                self._cycles += 1
                domain = self._next_domain()
                logger.info(
                    "Research cycle %d: exploring domain '%s'",
                    self._cycles, domain,
                )

                # Pick a topic from the domain
                subtopics = _DOMAIN_SUBTOPICS.get(domain, [])
                if subtopics:
                    topic = random.choice(subtopics)
                else:
                    topic = f"{domain} latest developments and trends"

                # Research the topic
                result = await self.research_topic(topic, depth="standard")

                # Broadcast findings via message bus
                if self._bus and result.findings:
                    try:
                        from backend.core.message_bus import BusMessage, MessagePriority
                        await self._bus.publish(BusMessage(
                            id=f"msg_{uuid.uuid4().hex[:12]}",
                            topic="system.learning",
                            sender="continuous_research",
                            payload={
                                "type": "research_finding",
                                "domain": domain,
                                "topic": topic,
                                "findings_count": len(result.findings),
                                "insights_count": len(result.insights),
                                "knowledge_stored": result.knowledge_stored,
                                "quality_score": result.quality_score,
                            },
                            priority=MessagePriority.BACKGROUND,
                        ))
                    except Exception as exc:
                        logger.debug("Failed to broadcast research findings: %s", exc)

                # Run daily briefing every 12 cycles (~6 hours at 30min interval)
                if self._cycles % 12 == 0:
                    try:
                        await self.daily_briefing()
                    except Exception as exc:
                        logger.warning("Daily briefing failed: %s", exc)

            except asyncio.CancelledError:
                logger.info("Research loop cancelled")
                break
            except Exception as exc:
                self._errors += 1
                logger.error("Research loop error: %s", exc)

            # Wait for next cycle
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("Research loop cancelled during sleep")
                break

        self._running = False
        logger.info("Continuous research loop stopped")

    def _next_domain(self) -> str:
        """Get the next domain to research in round-robin order."""
        domain = self._domains[self._domain_index % len(self._domains)]
        self._domain_index += 1
        return domain

    # ── Control ───────────────────────────────────────────────────

    def stop(self) -> None:
        """Stop the continuous research loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        logger.info("Continuous research stopped")

    def stats(self) -> dict:
        """Return research statistics."""
        explorer_stats = self.explorer.stats() if self._explorer else {}
        return {
            "running": self._running,
            "cycles": self._cycles,
            "topics_researched": self._topics_researched,
            "knowledge_stored": self._knowledge_stored,
            "errors": self._errors,
            "current_domain_index": self._domain_index,
            "domains": self._domains,
            "explorer": explorer_stats,
        }
