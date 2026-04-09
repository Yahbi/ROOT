"""
Perpetual Intelligence — MASTER orchestrator that keeps ALL agents working.

This is the heartbeat of ROOT's civilization. Every 60 seconds it runs a full
intelligence cycle that coordinates research, analysis, trading, coding, and
vision waves across all available agents. No agent is ever idle — there is
always knowledge to acquire, patterns to find, opportunities to evaluate,
code to improve, and strategy to refine.

Waves execute sequentially so each builds on the previous, but within each
wave tasks fan out via asyncio.gather for maximum parallelism. All delegation
goes through AgentCollaboration.delegate() which generates real message bus
events that the Neural Galaxy visualizes in real time.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.perpetual")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Immutable result types ───────────────────────────────────────


@dataclass(frozen=True)
class WaveResult:
    """Immutable result from a single intelligence wave."""
    wave: str
    success: bool
    findings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class CycleResult:
    """Immutable result from a full intelligence cycle."""
    cycle_number: int
    waves: tuple[WaveResult, ...] = ()
    total_duration_seconds: float = 0.0
    timestamp: str = field(default_factory=_now_iso)


# ── Research topics ──────────────────────────────────────────────

_RESEARCH_TOPICS: list[str] = [
    # Markets & Trading
    "latest trading strategies 2026",
    "options flow analysis techniques",
    "market microstructure patterns",
    "quantitative trading algorithms",
    "machine learning for stock prediction",
    "sentiment analysis trading",
    # Patents & Innovation
    "AI trading system patents 2026",
    "autonomous agent architecture patents",
    "predictive analytics methodology patents",
    # Academic
    "arxiv quantitative finance latest papers",
    "machine learning financial markets thesis",
    "multi-agent systems research papers",
    # Real-time Market
    "SPY market analysis today",
    "VIX volatility analysis current",
    "crypto market trends today",
    "earnings surprises this week",
    "Federal Reserve latest decisions",
    "economic indicators latest",
    # Technology
    "latest AI developments 2026",
    "LLM optimization techniques",
    "autonomous systems architecture",
    "real-time data processing",
]

# Core modules eligible for code review
_CORE_MODULES: list[str] = [
    "memory_engine", "brain", "agent_collab", "hedge_fund",
    "learning_engine", "autonomous_loop", "continuous_research",
    "message_bus", "orchestrator", "reflection", "proactive_engine",
    "skill_engine", "directive_engine", "revenue_engine",
    "self_writing_code", "planning_engine", "experience_memory",
]


class PerpetualIntelligence:
    """Master orchestrator that keeps all agents constantly working.

    Runs a background loop executing sequential intelligence waves:
    research -> analysis -> trading -> coding -> vision -> communication.
    Each wave delegates to specialized agents via the collaboration protocol,
    generating bus events that power the Neural Galaxy visualization.
    """

    def __init__(
        self,
        llm=None,
        collab=None,
        bus=None,
        memory=None,
        experience_memory=None,
        learning=None,
        registry=None,
        skills=None,
        plugins=None,
        state_store=None,
        web_explorer=None,
        document_analyzer=None,
        hedge_fund=None,
        planning_engine=None,
    ) -> None:
        self._llm = llm
        self._collab = collab
        self._bus = bus
        self._memory = memory
        self._experience_memory = experience_memory
        self._learning = learning
        self._registry = registry
        self._skills = skills
        self._plugins = plugins
        self._state_store = state_store
        self._web_explorer = web_explorer
        self._document_analyzer = document_analyzer
        self._hedge_fund = hedge_fund
        self._planning_engine = planning_engine

        # State
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._cycle_count: int = 0

        # Stats
        self._research_count: int = 0
        self._analysis_count: int = 0
        self._trade_count: int = 0
        self._code_count: int = 0
        self._vision_count: int = 0

    # ── Public API ───────────────────────────────────────────────

    async def start(self, interval: int = 60) -> None:
        """Start perpetual intelligence cycle."""
        self._running = True
        self._task = asyncio.create_task(self._loop(interval))
        logger.info("Perpetual intelligence started (interval=%ds)", interval)

    async def stop(self) -> None:
        """Stop the perpetual intelligence cycle."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("Perpetual intelligence task cancelled during shutdown")
        logger.info("Perpetual intelligence stopped after %d cycles", self._cycle_count)

    def stats(self) -> dict:
        """Return current perpetual intelligence statistics."""
        return {
            "running": self._running,
            "cycles": self._cycle_count,
            "research_findings": self._research_count,
            "analysis_insights": self._analysis_count,
            "trades_evaluated": self._trade_count,
            "code_reviews": self._code_count,
            "vision_plans": self._vision_count,
        }

    # ── Core cycle ───────────────────────────────────────────────

    async def run_cycle(self) -> dict:
        """Execute one full intelligence cycle across all waves.

        Waves run sequentially so each builds on the results of the previous.
        Within each wave, tasks fan out in parallel via asyncio.gather.
        """
        import time

        cycle_start = time.monotonic()
        wave_results: list[WaveResult] = []

        # 1. RESEARCH WAVE
        research = await self._run_wave("research", self._research_wave)
        wave_results.append(research)
        if self._bus:
            msg = self._bus.create_message(
                topic="intelligence.research",
                sender="perpetual_intelligence",
                payload={
                    "wave": "research",
                    "cycle": self._cycle_count,
                    "findings": len(research.findings),
                    "from_agent": "perpetual_intelligence",
                    "to_agent": "researcher",
                },
            )
            await self._bus.publish(msg)

        # 2. ANALYSIS WAVE
        analysis = await self._run_wave("analysis", self._analysis_wave)
        wave_results.append(analysis)
        if self._bus:
            msg = self._bus.create_message(
                topic="intelligence.analysis",
                sender="perpetual_intelligence",
                payload={
                    "wave": "analysis",
                    "cycle": self._cycle_count,
                    "findings": len(analysis.findings),
                    "from_agent": "perpetual_intelligence",
                    "to_agent": "analyst",
                },
            )
            await self._bus.publish(msg)

        # 3. TRADING WAVE
        trading = await self._run_wave("trading", self._trading_wave)
        wave_results.append(trading)
        if self._bus:
            msg = self._bus.create_message(
                topic="intelligence.trading",
                sender="perpetual_intelligence",
                payload={
                    "wave": "trading",
                    "cycle": self._cycle_count,
                    "findings": len(trading.findings),
                    "from_agent": "perpetual_intelligence",
                    "to_agent": "swarm",
                },
            )
            await self._bus.publish(msg)

        # 4. CODING WAVE
        coding = await self._run_wave("coding", self._coding_wave)
        wave_results.append(coding)
        if self._bus:
            msg = self._bus.create_message(
                topic="intelligence.coding",
                sender="perpetual_intelligence",
                payload={
                    "wave": "coding",
                    "cycle": self._cycle_count,
                    "findings": len(coding.findings),
                    "from_agent": "perpetual_intelligence",
                    "to_agent": "coder",
                },
            )
            await self._bus.publish(msg)

        # 5. VISION WAVE
        vision = await self._run_wave("vision", self._vision_wave)
        wave_results.append(vision)
        if self._bus:
            msg = self._bus.create_message(
                topic="intelligence.vision",
                sender="perpetual_intelligence",
                payload={
                    "wave": "vision",
                    "cycle": self._cycle_count,
                    "findings": len(vision.findings),
                    "from_agent": "perpetual_intelligence",
                    "to_agent": "vision_architect",
                },
            )
            await self._bus.publish(msg)

        # 6. COMMUNICATION WAVE
        comm = await self._run_wave("communication", self._communication_wave, wave_results)
        wave_results.append(comm)

        total_duration = time.monotonic() - cycle_start

        result = CycleResult(
            cycle_number=self._cycle_count + 1,
            waves=tuple(wave_results),
            total_duration_seconds=round(total_duration, 2),
        )

        logger.info(
            "Intelligence cycle #%d completed in %.1fs — research=%d analysis=%d trading=%d code=%d vision=%d",
            result.cycle_number,
            total_duration,
            self._research_count,
            self._analysis_count,
            self._trade_count,
            self._code_count,
            self._vision_count,
        )

        return {
            "cycle": result.cycle_number,
            "duration": result.total_duration_seconds,
            "waves": len(wave_results),
            "successes": sum(1 for w in wave_results if w.success),
            "findings": sum(len(w.findings) for w in wave_results),
        }

    # ── Wave implementations ─────────────────────────────────────

    async def _research_wave(self) -> WaveResult:
        """Research wave: explore new knowledge across diverse topics."""
        if not self._collab:
            return WaveResult(wave="research", success=False, errors=("No collab engine",))

        topics = random.sample(_RESEARCH_TOPICS, min(5, len(_RESEARCH_TOPICS)))
        findings: list[str] = []
        errors: list[str] = []

        async def research_topic(topic: str) -> Optional[str]:
            try:
                result = await self._collab.delegate(
                    from_agent="perpetual_intelligence",
                    to_agent="researcher",
                    task=(
                        f"Research the following topic and provide key findings, "
                        f"insights, and actionable intelligence: {topic}"
                    ),
                )
                text = result.final_result or ""
                if text and len(text) > 20:
                    # Store in memory
                    await self._store_finding(topic, text, "research")
                    return text
            except Exception as exc:
                errors.append(f"Research '{topic}': {exc}")
                logger.debug("Research wave error for '%s': %s", topic, exc)
            return None

        results = await asyncio.gather(
            *[research_topic(t) for t in topics],
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, str) and r:
                findings.append(r[:200])
                self._research_count += 1
            elif isinstance(r, Exception):
                errors.append(str(r))

        return WaveResult(
            wave="research",
            success=len(findings) > 0,
            findings=tuple(findings),
            errors=tuple(errors),
        )

    async def _analysis_wave(self) -> WaveResult:
        """Analysis wave: find patterns in recent knowledge."""
        if not self._collab or not self._memory:
            return WaveResult(wave="analysis", success=False, errors=("Missing collab or memory",))

        findings: list[str] = []
        errors: list[str] = []

        try:
            # Get recent memories for analysis
            from backend.models.memory import MemoryQuery
            recent = self._memory.search(MemoryQuery(query="", limit=20))
            recent_text = "\n".join(
                f"- {m.content[:150]}" for m in recent[:20] if hasattr(m, "content")
            )
        except Exception as exc:
            logger.debug("Failed to fetch recent memories: %s", exc)
            recent_text = "No recent memories available."

        async def analyze_patterns() -> Optional[str]:
            try:
                result = await self._collab.delegate(
                    from_agent="perpetual_intelligence",
                    to_agent="analyst",
                    task=(
                        f"Analyze these recent knowledge entries and find patterns, "
                        f"correlations, and actionable insights:\n{recent_text}"
                    ),
                )
                text = result.final_result or ""
                if text and len(text) > 20:
                    await self._store_finding("pattern_analysis", text, "analysis")
                    return text
            except Exception as exc:
                errors.append(f"Analyst: {exc}")
            return None

        async def predict_from_data() -> Optional[str]:
            try:
                result = await self._collab.delegate(
                    from_agent="perpetual_intelligence",
                    to_agent="miro",
                    task=(
                        f"Based on these recent observations, make predictions about "
                        f"likely near-term developments and opportunities:\n{recent_text}"
                    ),
                )
                text = result.final_result or ""
                if text and len(text) > 20:
                    await self._store_finding("predictions", text, "analysis")
                    return text
            except Exception as exc:
                errors.append(f"MiRo: {exc}")
            return None

        results = await asyncio.gather(
            analyze_patterns(),
            predict_from_data(),
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, str) and r:
                findings.append(r[:200])
                self._analysis_count += 1
            elif isinstance(r, Exception):
                errors.append(str(r))

        return WaveResult(
            wave="analysis",
            success=len(findings) > 0,
            findings=tuple(findings),
            errors=tuple(errors),
        )

    async def _trading_wave(self) -> WaveResult:
        """Trading wave: evaluate market opportunities."""
        if not self._collab:
            return WaveResult(wave="trading", success=False, errors=("No collab engine",))

        findings: list[str] = []
        errors: list[str] = []

        async def market_research() -> Optional[str]:
            try:
                result = await self._collab.delegate(
                    from_agent="perpetual_intelligence",
                    to_agent="swarm",
                    task=(
                        "Research current market conditions for SPY and major indices. "
                        "Identify key support/resistance levels, unusual options activity, "
                        "and potential trade setups for the next session."
                    ),
                )
                text = result.final_result or ""
                if text and len(text) > 20:
                    await self._store_finding("market_conditions", text, "trading")
                    return text
            except Exception as exc:
                errors.append(f"Swarm: {exc}")
            return None

        async def risk_assessment() -> Optional[str]:
            try:
                result = await self._collab.delegate(
                    from_agent="perpetual_intelligence",
                    to_agent="analyst",
                    task=(
                        "Evaluate current portfolio risk exposure and market risk factors. "
                        "Consider VIX levels, sector rotation, and macro events. "
                        "Provide risk/reward assessment for active positions."
                    ),
                )
                text = result.final_result or ""
                if text and len(text) > 20:
                    await self._store_finding("risk_assessment", text, "trading")
                    return text
            except Exception as exc:
                errors.append(f"Analyst risk: {exc}")
            return None

        results = await asyncio.gather(
            market_research(),
            risk_assessment(),
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, str) and r:
                findings.append(r[:200])
                self._trade_count += 1
            elif isinstance(r, Exception):
                errors.append(str(r))

        # Feed into hedge fund for signal generation
        if self._hedge_fund and findings:
            try:
                signals = self._hedge_fund.stats() if hasattr(self._hedge_fund, "stats") else {}
                findings.append(f"Hedge fund status: {signals}")
            except Exception as exc:
                errors.append(f"Hedge fund: {exc}")

        return WaveResult(
            wave="trading",
            success=len(findings) > 0,
            findings=tuple(findings),
            errors=tuple(errors),
        )

    async def _coding_wave(self) -> WaveResult:
        """Coding wave: review and improve ROOT's codebase."""
        if not self._collab:
            return WaveResult(wave="coding", success=False, errors=("No collab engine",))

        findings: list[str] = []
        errors: list[str] = []

        # Pick a random core module to review
        module = random.choice(_CORE_MODULES)

        try:
            result = await self._collab.delegate(
                from_agent="perpetual_intelligence",
                to_agent="coder",
                task=(
                    f"Review the ROOT core module '{module}' "
                    f"(backend/core/{module}.py) for potential improvements. "
                    f"Look for: performance optimizations, error handling gaps, "
                    f"code duplication, missing edge cases, and architectural improvements. "
                    f"Provide specific, actionable improvement proposals."
                ),
            )
            text = result.final_result or ""
            if text and len(text) > 20:
                await self._store_finding(f"code_review_{module}", text, "coding")
                findings.append(text[:200])
                self._code_count += 1
        except Exception as exc:
            errors.append(f"Coder review '{module}': {exc}")
            logger.debug("Coding wave error for module '%s': %s", module, exc)

        return WaveResult(
            wave="coding",
            success=len(findings) > 0,
            findings=tuple(findings),
            errors=tuple(errors),
        )

    async def _vision_wave(self) -> WaveResult:
        """Vision wave: strategic planning and opportunity scanning."""
        if not self._collab:
            return WaveResult(wave="vision", success=False, errors=("No collab engine",))

        findings: list[str] = []
        errors: list[str] = []

        async def strategic_direction() -> Optional[str]:
            try:
                result = await self._collab.delegate(
                    from_agent="perpetual_intelligence",
                    to_agent="vision_architect",
                    task=(
                        "Assess ROOT's current strategic direction. "
                        "What capabilities should we build next? "
                        "What are the highest-impact improvements to prioritize? "
                        "Consider market conditions, technology trends, and revenue goals."
                    ),
                )
                text = result.final_result or ""
                if text and len(text) > 20:
                    await self._store_finding("strategic_direction", text, "vision")
                    return text
            except Exception as exc:
                errors.append(f"Vision architect: {exc}")
            return None

        async def opportunity_scan() -> Optional[str]:
            try:
                result = await self._collab.delegate(
                    from_agent="perpetual_intelligence",
                    to_agent="opportunity_hunter",
                    task=(
                        "Scan for new revenue opportunities, partnership possibilities, "
                        "and emerging market niches that ROOT could exploit. "
                        "Focus on actionable opportunities with clear ROI potential."
                    ),
                )
                text = result.final_result or ""
                if text and len(text) > 20:
                    await self._store_finding("opportunities", text, "vision")
                    return text
            except Exception as exc:
                errors.append(f"Opportunity hunter: {exc}")
            return None

        async def risk_evaluation() -> Optional[str]:
            try:
                result = await self._collab.delegate(
                    from_agent="perpetual_intelligence",
                    to_agent="risk_strategist",
                    task=(
                        "Evaluate ROOT's current risk exposure across all dimensions: "
                        "trading risk, operational risk, technology risk, and market risk. "
                        "Identify the top 3 risks and recommend mitigations."
                    ),
                )
                text = result.final_result or ""
                if text and len(text) > 20:
                    await self._store_finding("risk_evaluation", text, "vision")
                    return text
            except Exception as exc:
                errors.append(f"Risk strategist: {exc}")
            return None

        results = await asyncio.gather(
            strategic_direction(),
            opportunity_scan(),
            risk_evaluation(),
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, str) and r:
                findings.append(r[:200])
                self._vision_count += 1
            elif isinstance(r, Exception):
                errors.append(str(r))

        return WaveResult(
            wave="vision",
            success=len(findings) > 0,
            findings=tuple(findings),
            errors=tuple(errors),
        )

    async def _communication_wave(self, previous_waves: list[WaveResult] = None) -> WaveResult:
        """Communication wave: broadcast all findings via message bus."""
        if not self._bus:
            return WaveResult(wave="communication", success=False, errors=("No message bus",))

        errors: list[str] = []
        published = 0
        previous_waves = previous_waves or []

        wave_topics = {
            "research": "intelligence.research",
            "analysis": "intelligence.analysis",
            "trading": "intelligence.trading",
            "coding": "intelligence.coding",
            "vision": "intelligence.vision",
        }

        for wave_result in previous_waves:
            if not wave_result.findings:
                continue
            topic = wave_topics.get(wave_result.wave, f"intelligence.{wave_result.wave}")
            try:
                msg = self._bus.create_message(
                    topic=topic,
                    sender="perpetual_intelligence",
                    payload={
                        "wave": wave_result.wave,
                        "findings_count": len(wave_result.findings),
                        "findings": [f[:300] for f in wave_result.findings],
                        "cycle": self._cycle_count + 1,
                    },
                )
                await self._bus.publish(msg)
                published += 1
            except Exception as exc:
                errors.append(f"Publish {wave_result.wave}: {exc}")

        return WaveResult(
            wave="communication",
            success=published > 0,
            findings=(f"Published {published} wave broadcasts",),
            errors=tuple(errors),
        )

    # ── Helpers ──────────────────────────────────────────────────

    async def _run_wave(self, name: str, wave_fn, *args) -> WaveResult:
        """Execute a wave with timing and error isolation."""
        import time

        start = time.monotonic()
        try:
            result = await wave_fn(*args) if args else await wave_fn()
            duration = time.monotonic() - start
            # Return a new frozen instance with duration set
            return WaveResult(
                wave=result.wave,
                success=result.success,
                findings=result.findings,
                errors=result.errors,
                duration_seconds=round(duration, 2),
            )
        except Exception as exc:
            duration = time.monotonic() - start
            logger.error("Wave '%s' failed: %s", name, exc)
            return WaveResult(
                wave=name,
                success=False,
                errors=(str(exc),),
                duration_seconds=round(duration, 2),
            )

    async def _store_finding(self, topic: str, content: str, tag: str) -> None:
        """Store a finding in memory with appropriate tags."""
        if not self._memory:
            return
        try:
            from backend.models.memory import MemoryEntry, MemoryType

            self._memory.store(MemoryEntry(
                content=f"[Perpetual:{topic}] {content[:2000]}",
                memory_type=MemoryType.FACT if tag == "research" else MemoryType.LEARNING,
                tags=["perpetual_intelligence", tag, topic],
                source="perpetual_intelligence",
                confidence=0.7,
            ))
        except Exception as exc:
            logger.debug("Failed to store finding '%s': %s", topic, exc)

    # ── Background loop ──────────────────────────────────────────

    async def _loop(self, interval: int) -> None:
        """Main background loop — runs forever until stopped."""
        # Let other systems initialize first
        await asyncio.sleep(30)

        while self._running:
            try:
                cycle_result = await self.run_cycle()
                self._cycle_count += 1

                # Publish cycle completion to bus
                if self._bus:
                    msg = self._bus.create_message(
                        topic="system.intelligence",
                        sender="perpetual_intelligence",
                        payload={
                            "cycle": self._cycle_count,
                            "result": cycle_result,
                        },
                    )
                    await self._bus.publish(msg)
            except Exception as e:
                logger.error("Perpetual intelligence cycle error: %s", e)

            await asyncio.sleep(interval)
