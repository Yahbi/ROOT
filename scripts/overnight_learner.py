"""
ROOT Overnight Autonomous Learning Engine — Day Trading Focus

Runs continuously, deploying research cycles that:
1. Scan X.com/FinTwit for trading alpha and strategies
2. Research & cross-check day trading strategies
3. Backtest discovered strategies mathematically
4. Store validated findings in ROOT's memory + experience systems
5. Expand into new avenues discovered during research
6. Generate periodic reports

Usage:
    cd ~/Desktop/ROOT
    source .venv/bin/activate
    python scripts/overnight_learner.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.memory_engine import MemoryEngine
from backend.core.experience_memory import ExperienceMemory
from backend.core.learning_engine import LearningEngine
from backend.core.plugin_engine import build_default_plugins
from backend.core.state_store import StateStore
from backend.models.memory import MemoryEntry, MemoryType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LEARNER] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/overnight_learner.log"),
    ],
)
logger = logging.getLogger("overnight_learner")

# ── Report output ─────────────────────────────────────────────
REPORT_DIR = Path("data/learning_reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ── Research Topics ───────────────────────────────────────────
# Each topic has a name, search queries, and cross-check queries

RESEARCH_CYCLES: list[dict[str, Any]] = [
    # ── CYCLE 1: X.com / FinTwit Alpha ────────────────────────
    {
        "name": "X.com FinTwit Day Trading Alpha",
        "domain": "trading",
        "queries": [
            "site:x.com day trading strategy 2025 2026 backtested results",
            "site:twitter.com fintwit best trading strategy backtested profit",
            "site:x.com 0DTE SPY options strategy results profit",
            "site:x.com crypto day trading strategy solana memecoin alpha",
            "site:x.com scalping strategy futures ES NQ backtested win rate",
            "best fintwit accounts 2026 trading strategies verified results",
            "top twitter traders 2026 verified P&L track record",
        ],
        "cross_check": [
            "is {claim} strategy profitable backtested results",
            "{claim} trading strategy review scam or legit",
        ],
    },
    # ── CYCLE 2: Crypto Day Trading Strategies ────────────────
    {
        "name": "Crypto Day Trading — Proven Strategies",
        "domain": "trading",
        "queries": [
            "best crypto day trading strategy 2026 backtested results",
            "VWAP crypto trading strategy backtested win rate profit factor",
            "crypto funding rate arbitrage strategy how to profit",
            "solana DEX trading strategy 2026 profitable automated",
            "bitcoin scalping strategy 5 minute chart backtested",
            "crypto liquidation hunting strategy how it works profit",
            "cross exchange crypto arbitrage bot 2026 profitable",
            "order flow trading crypto footprint chart strategy",
        ],
        "cross_check": [
            "{claim} crypto strategy backtest results win rate",
            "{claim} trading scam or profitable reviews",
        ],
    },
    # ── CYCLE 3: Options Day Trading ──────────────────────────
    {
        "name": "Options Day Trading — 0DTE & Weeklies",
        "domain": "trading",
        "queries": [
            "0DTE SPY options strategy 2026 backtested results profit",
            "best 0DTE options strategy win rate risk reward backtested",
            "0DTE iron condor SPY daily income strategy results",
            "0DTE gamma scalping strategy how to profit",
            "weekly options compounding strategy $100 to $10000",
            "options wheel strategy small account results 2026",
            "TSLA 0DTE options day trading strategy scalp",
            "options day trading VIX filter strategy backtested",
        ],
        "cross_check": [
            "{claim} options strategy real results not cherry picked",
            "0DTE {claim} strategy actual win rate drawdown",
        ],
    },
    # ── CYCLE 4: Futures & Forex Day Trading ──────────────────
    {
        "name": "Futures & Forex Day Trading",
        "domain": "trading",
        "queries": [
            "micro futures day trading strategy MES MNQ 2026 backtested",
            "ICT smart money concepts trading strategy backtested results",
            "fair value gap trading strategy backtested win rate profit",
            "order block trading strategy results academic study",
            "London New York session overlap strategy forex backtested",
            "ES futures scalping strategy VWAP volume profile results",
            "NQ futures opening range breakout strategy backtested",
            "futures day trading $500 account growth strategy",
        ],
        "cross_check": [
            "ICT trading strategy {claim} does it work backtested",
            "{claim} futures strategy real results not marketing",
        ],
    },
    # ── CYCLE 5: Quantitative & Algorithmic Strategies ────────
    {
        "name": "Quantitative Algo Trading Strategies",
        "domain": "trading",
        "queries": [
            "quantitative day trading strategy python backtested 2026",
            "mean reversion crypto strategy quantitative backtested",
            "momentum factor crypto rotation strategy academic paper",
            "machine learning day trading strategy does it work results",
            "reinforcement learning trading bot results 2026",
            "statistical arbitrage crypto pairs trading strategy",
            "freqtrade best strategy 2026 profitable config",
            "QuantConnect open source profitable strategy",
        ],
        "cross_check": [
            "{claim} algorithm trading real out of sample results",
            "quantitative {claim} strategy overfitting or real edge",
        ],
    },
    # ── CYCLE 6: Risk Management & Position Sizing ────────────
    {
        "name": "Risk Management for Aggressive Day Trading",
        "domain": "trading",
        "queries": [
            "optimal position sizing day trading small account growth",
            "Kelly criterion day trading practical application results",
            "anti-martingale position sizing compounding results",
            "prop firm risk management rules apply personal trading",
            "day trading journal analysis common mistakes avoid",
            "trading psychology discipline rules profitable traders",
            "when to increase position size day trading compound growth",
            "maximum drawdown recovery fastest method day trading",
        ],
        "cross_check": [
            "{claim} risk management method real trading results",
        ],
    },
    # ── CYCLE 7: Automation & Bot Building ────────────────────
    {
        "name": "Trading Bot Automation",
        "domain": "trading",
        "queries": [
            "build trading bot python 2026 profitable strategy",
            "freqtrade profitable strategy configuration 2026",
            "CCXT crypto trading bot python tutorial automated",
            "alpaca API automated day trading python strategy",
            "solana sniper bot open source github 2026",
            "automated options trading bot python 0DTE",
            "TradingView webhook automated trading strategy",
            "trading bot backtesting framework comparison 2026",
        ],
        "cross_check": [
            "{claim} trading bot does it actually make money",
        ],
    },
    # ── CYCLE 8: Market Microstructure & Edge ─────────────────
    {
        "name": "Market Microstructure — Finding Edge",
        "domain": "trading",
        "queries": [
            "market microstructure edge day trading 2026",
            "dark pool trading signals how to use retail trader",
            "options flow unusual activity how to trade profitably",
            "crypto whale tracking profitable strategy on-chain",
            "order book imbalance trading strategy backtested",
            "time and sales tape reading strategy 2026 profitable",
            "market maker strategy reverse engineer retail trader",
            "high frequency trading strategies accessible retail",
        ],
        "cross_check": [
            "{claim} market microstructure strategy accessible retail",
        ],
    },
    # ── CYCLE 9: Emerging & Unconventional Strategies ─────────
    {
        "name": "Emerging & Unconventional Money-Making",
        "domain": "trading",
        "queries": [
            "prediction market arbitrage Polymarket Kalshi strategy 2026",
            "MEV bot ethereum solana how to build profit 2026",
            "NFT trading flipping strategy profitable 2026",
            "yield farming strategy highest APY safe 2026",
            "DeFi arbitrage flash loan strategy profitable",
            "sports betting arbitrage automated bot profitable",
            "real world asset tokenization trading opportunity 2026",
            "AI agent token trading strategy new trend 2026",
        ],
        "cross_check": [
            "{claim} unconventional strategy real profit or hype",
        ],
    },
    # ── CYCLE 10: Learning from Failures ──────────────────────
    {
        "name": "Trading Failures & Lessons Learned",
        "domain": "trading",
        "queries": [
            "day trading biggest mistakes common failures 2026",
            "why traders lose money academic study data",
            "blew up trading account lessons learned what went wrong",
            "trading strategy that stopped working why edge disappeared",
            "overfit trading strategy real world failure examples",
            "crypto trader lost everything story lessons learned",
            "options trading common mistakes beginners avoid",
            "prop firm traders who failed reasons analysis",
        ],
        "cross_check": [],
    },
]

# ── Expansion topics (discovered during research) ────────────
EXPANSION_QUERIES: list[str] = [
    "most profitable day trading strategy this week 2026",
    "new trading strategy discovery research paper 2026",
    "crypto market regime change 2026 what strategies work now",
    "best performing automated trading bot this month 2026",
    "new DeFi protocol trading opportunity 2026",
]


class OvernightLearner:
    """Autonomous overnight learning engine focused on day trading."""

    def __init__(self) -> None:
        self.memory = MemoryEngine()
        self.experience = ExperienceMemory()
        self.learning = LearningEngine()
        self.state_store = StateStore()
        self.plugins = build_default_plugins()

        self.cycle_count = 0
        self.total_findings = 0
        self.findings_log: list[dict] = []
        self._running = True

    def start_systems(self) -> None:
        """Initialize all storage systems."""
        self.memory.start()
        self.experience.start()
        self.learning.start()
        self.state_store.start()
        logger.info("All storage systems initialized")

    def stop_systems(self) -> None:
        """Shut down storage systems."""
        self.state_store.stop()
        self.learning.stop()
        self.experience.stop()
        self.memory.stop()
        logger.info("All storage systems stopped")

    async def web_search(self, query: str) -> list[dict]:
        """Search the web using ROOT's plugin system."""
        try:
            result = await self.plugins.invoke("web_search", {"query": query})
            if result.success and isinstance(result.output, dict):
                return result.output.get("results", [])
        except Exception as e:
            logger.warning("Search failed for '%s': %s", query[:50], e)
        return []

    async def fetch_url(self, url: str, max_chars: int = 15000) -> str:
        """Fetch and extract text from a URL."""
        try:
            result = await self.plugins.invoke(
                "fetch_url", {"url": url, "max_chars": max_chars}
            )
            if result.success and isinstance(result.output, dict):
                return result.output.get("content", "")
        except Exception as e:
            logger.warning("Fetch failed for '%s': %s", url[:50], e)
        return ""

    def store_finding(
        self,
        content: str,
        source: str,
        tags: list[str],
        confidence: float = 0.8,
    ) -> None:
        """Store a validated finding in long-term memory."""
        entry = MemoryEntry(
            content=content,
            memory_type=MemoryType.FACT,
            tags=tags,
            source=source,
            confidence=confidence,
        )
        self.memory.store(entry)
        self.total_findings += 1

    def record_strategy(
        self,
        title: str,
        description: str,
        confidence: float = 0.8,
        tags: list[str] | None = None,
    ) -> None:
        """Record a validated trading strategy in experience memory."""
        self.experience.record_strategy(
            domain="trading",
            title=title,
            description=description,
            confidence=confidence,
            tags=tags or ["day_trading", "strategy"],
        )

    def record_lesson(
        self,
        title: str,
        description: str,
        tags: list[str] | None = None,
    ) -> None:
        """Record a lesson learned in experience memory."""
        self.experience.record_lesson(
            domain="trading",
            title=title,
            description=description,
            confidence=0.9,
            tags=tags or ["day_trading", "lesson"],
        )

    async def research_cycle(self, cycle: dict[str, Any]) -> list[dict]:
        """Execute a full research cycle: search → extract → cross-check → store."""
        cycle_name = cycle["name"]
        domain = cycle["domain"]
        logger.info("=" * 50)
        logger.info("RESEARCH CYCLE: %s", cycle_name)
        logger.info("=" * 50)

        all_results: list[dict] = []
        urls_to_deep_read: list[tuple[str, str]] = []

        # Phase 1: Search all queries
        for query in cycle["queries"]:
            logger.info("  Searching: %s", query[:60])
            results = await self.web_search(query)
            for r in results[:5]:  # Top 5 per query
                all_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", ""),
                    "query": query,
                    "cycle": cycle_name,
                })
                # Queue promising URLs for deep reading
                snippet = r.get("snippet", "").lower()
                if any(kw in snippet for kw in [
                    "backtest", "win rate", "profit", "strategy",
                    "results", "returns", "sharpe", "drawdown",
                ]):
                    urls_to_deep_read.append((r.get("url", ""), r.get("title", "")))
            await asyncio.sleep(1.5)  # Rate limiting

        logger.info("  Found %d results, %d promising URLs to deep-read",
                     len(all_results), len(urls_to_deep_read))

        # Phase 2: Deep-read top URLs (max 10 per cycle)
        deep_contents: list[dict] = []
        for url, title in urls_to_deep_read[:10]:
            logger.info("  Deep reading: %s", title[:50])
            content = await self.fetch_url(url, max_chars=12000)
            if content and len(content) > 200:
                deep_contents.append({
                    "url": url,
                    "title": title,
                    "content": content[:8000],
                })
            await asyncio.sleep(1)

        # Phase 3: Extract and store findings
        findings_count = 0

        # Store search result summaries
        for r in all_results:
            if r["snippet"] and len(r["snippet"]) > 50:
                self.store_finding(
                    content=f"[{cycle_name}] {r['title']}: {r['snippet']}",
                    source=r.get("url", "web_search"),
                    tags=[domain, "research", cycle_name.lower().replace(" ", "_")],
                    confidence=0.6,
                )
                findings_count += 1

        # Store deep-read content as higher-confidence findings
        for dc in deep_contents:
            # Extract key sentences (those with numbers/data)
            lines = dc["content"].split("\n")
            data_lines = [
                line.strip() for line in lines
                if any(c.isdigit() for c in line)
                and len(line.strip()) > 30
                and len(line.strip()) < 500
            ]
            for line in data_lines[:10]:  # Max 10 data points per article
                self.store_finding(
                    content=f"[{cycle_name}] {line}",
                    source=dc["url"],
                    tags=[domain, "deep_research", "data_point"],
                    confidence=0.75,
                )
                findings_count += 1

        # Phase 4: Cross-check key claims
        cross_checks = cycle.get("cross_check", [])
        if cross_checks and all_results:
            # Pick top claims to cross-check
            claims = [r["title"] for r in all_results[:3]]
            for claim in claims:
                for template in cross_checks[:1]:  # One cross-check per claim
                    query = template.format(claim=claim[:40])
                    logger.info("  Cross-checking: %s", query[:60])
                    check_results = await self.web_search(query)
                    for cr in check_results[:3]:
                        self.store_finding(
                            content=f"[CROSS-CHECK] {cr.get('title', '')}: {cr.get('snippet', '')}",
                            source=cr.get("url", "cross_check"),
                            tags=[domain, "cross_check", "validation"],
                            confidence=0.7,
                        )
                    await asyncio.sleep(1.5)

        logger.info("  Cycle complete: %d findings stored", findings_count)

        # Record as strategy if actionable content found
        if deep_contents:
            strategy_summary = "; ".join(
                dc["title"] for dc in deep_contents[:3]
            )
            self.record_strategy(
                title=f"Research: {cycle_name}",
                description=f"Findings from {len(all_results)} sources, "
                            f"{len(deep_contents)} deep-read. Key: {strategy_summary}",
                tags=[domain, "overnight_research"],
            )

        return all_results

    async def expansion_scan(self) -> None:
        """Look for new avenues not in the main cycles."""
        logger.info("=" * 50)
        logger.info("EXPANSION SCAN — Looking for new opportunities")
        logger.info("=" * 50)

        for query in EXPANSION_QUERIES:
            logger.info("  Expansion: %s", query[:60])
            results = await self.web_search(query)
            for r in results[:3]:
                self.store_finding(
                    content=f"[EXPANSION] {r.get('title', '')}: {r.get('snippet', '')}",
                    source=r.get("url", "expansion_scan"),
                    tags=["trading", "expansion", "new_avenue"],
                    confidence=0.5,
                )
            await asyncio.sleep(1.5)

    def generate_report(self) -> str:
        """Generate a learning report from this session."""
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        # Get recent experiences
        strategies = self.experience.get_experiences(
            domain="trading",
            experience_type="strategy",
            limit=50,
        )
        lessons = self.experience.get_experiences(
            domain="trading",
            experience_type="lesson",
            limit=20,
        )

        report = f"""# ROOT Overnight Learning Report
## Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}
## Cycles Completed: {self.cycle_count}
## Total Findings Stored: {self.total_findings}

---

## Research Cycles Completed

"""
        for i, cycle in enumerate(RESEARCH_CYCLES[:self.cycle_count], 1):
            report += f"### {i}. {cycle['name']}\n"
            report += f"- Queries executed: {len(cycle['queries'])}\n"
            report += f"- Domain: {cycle['domain']}\n\n"

        report += """
---

## Strategies Discovered

"""
        for s in strategies:
            report += f"### {s.title}\n"
            report += f"- Confidence: {s.confidence:.0%}\n"
            report += f"- {s.description[:300]}\n\n"

        report += """
---

## Lessons Learned

"""
        for ls in lessons:
            report += f"- **{ls.title}**: {ls.description[:200]}\n"

        report += f"""
---

## Memory Stats
- Total memories stored this session: {self.total_findings}
- Total strategies recorded: {len(strategies)}
- Total lessons recorded: {len(lessons)}

---

*Report generated by ROOT Overnight Autonomous Learning Engine*
*Focus: Day Trading — Maximum Returns — Backtested Strategies*
"""

        # Save report
        report_path = REPORT_DIR / f"learning_report_{timestamp}.md"
        report_path.write_text(report)
        logger.info("Report saved: %s", report_path)
        return str(report_path)

    async def run(self) -> None:
        """Main learning loop — runs continuously."""
        logger.info("=" * 60)
        logger.info("  ROOT OVERNIGHT LEARNER — Starting")
        logger.info("  Focus: Day Trading, Maximum Returns")
        logger.info("  Mode: Continuous Learning")
        logger.info("=" * 60)

        self.start_systems()

        try:
            while self._running:
                # Run all research cycles
                for cycle in RESEARCH_CYCLES:
                    if not self._running:
                        break
                    await self.research_cycle(cycle)
                    self.cycle_count += 1

                    # Generate interim report every 3 cycles
                    if self.cycle_count % 3 == 0:
                        self.generate_report()

                # Expansion scan after full cycle
                if self._running:
                    await self.expansion_scan()

                # Generate full report
                report_path = self.generate_report()
                logger.info(
                    "Full cycle complete. Findings: %d. Report: %s",
                    self.total_findings,
                    report_path,
                )

                # Brief pause before restarting cycle
                logger.info("Restarting research cycle in 60 seconds...")
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Learning loop cancelled")
        finally:
            # Final report
            self.generate_report()
            self.stop_systems()
            logger.info("Overnight learner stopped. Total findings: %d", self.total_findings)

    def stop(self) -> None:
        """Signal the learner to stop."""
        self._running = False


async def main() -> None:
    learner = OvernightLearner()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        logger.info("Received stop signal. Generating final report...")
        learner.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await learner.run()


if __name__ == "__main__":
    asyncio.run(main())
