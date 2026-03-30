"""
Continuous Learning Engine — ensures every agent is always learning.

Rotates through all 162+ civilization agents, assigning each a learning
task tailored to their specialty. Agents research, discover, and store
findings in experience memory — building collective intelligence 24/7.

Design:
- Runs as a background loop (configurable interval, default 10 min)
- Processes agents in batches (default 3 concurrent) to avoid LLM overload
- Each agent gets a learning task generated from their capabilities
- Results are stored in experience memory as strategies/lessons
- Tracks per-agent learning stats (cycles, findings, last_learned)
- Division-round-robin ensures balanced coverage across all divisions
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

logger = logging.getLogger("root.continuous_learning")


# ── Learning task templates by capability domain ─────────────────

_LEARNING_DOMAINS: dict[str, list[str]] = {
    "research": [
        "Search for the latest breakthroughs in {topic}. Find 3 specific, verifiable findings with sources.",
        "Investigate emerging trends in {topic}. What changed in the last 30 days? Include data points.",
        "Find the top 3 most impactful papers or articles about {topic} published recently. Summarize key insights.",
    ],
    "trading": [
        "Research a new trading strategy for {topic}. Include backtest criteria, expected Sharpe ratio, and risk parameters.",
        "Analyze current market conditions for {topic}. What signals are strongest? Include specific price levels or metrics.",
        "Find successful traders or funds using {topic} strategies. What can we learn from their approach?",
    ],
    "engineering": [
        "Research best practices for {topic} in production systems. Find 3 concrete patterns with code examples.",
        "Investigate new tools or libraries for {topic}. Compare top 3 options with pros/cons.",
        "Find common pitfalls and anti-patterns in {topic}. How do top engineering teams avoid them?",
    ],
    "business": [
        "Research successful micro-SaaS products in {topic}. What's their MRR, pricing, and growth strategy?",
        "Find 3 monetization opportunities in {topic}. Include TAM estimates and competitive landscape.",
        "Analyze the competitive landscape for {topic}. Who's winning, why, and where are the gaps?",
    ],
    "content": [
        "Research top-performing content about {topic}. What formats, angles, and distribution channels work best?",
        "Find successful creators or newsletters in {topic}. What's their audience size, engagement, and monetization?",
        "Analyze SEO opportunities for {topic}. What keywords have high volume and low competition?",
    ],
    "security": [
        "Research the latest security threats and vulnerabilities in {topic}. What defenses are recommended?",
        "Find best practices for {topic} security. What do OWASP and industry leaders recommend?",
        "Investigate recent security incidents related to {topic}. What lessons can we apply?",
    ],
    "data": [
        "Research new data sources and APIs for {topic}. What's available, what's the quality, what does it cost?",
        "Find best practices for {topic} data pipelines. What architectures scale best?",
        "Investigate data quality patterns for {topic}. How do leading teams ensure accuracy?",
    ],
    "strategy": [
        "Analyze strategic opportunities in {topic}. What's the 6-month outlook? Include specific actionable steps.",
        "Research how successful companies approach {topic}. What strategies drive the best ROI?",
        "Find emerging opportunities at the intersection of {topic} and AI automation. What can be built?",
    ],
    "infrastructure": [
        "Research cost optimization strategies for {topic}. Where are the biggest savings opportunities?",
        "Find best practices for {topic} reliability. What SLOs do top teams target?",
        "Investigate new cloud services or tools for {topic}. What reduces operational burden?",
    ],
    "general": [
        "Research the latest developments in {topic}. What are the 3 most important things to know right now?",
        "Find practical applications of {topic} that could generate revenue or save costs. Be specific.",
        "Investigate what experts are saying about {topic}. Summarize the consensus and any contrarian views.",
    ],
}

# Map agent capabilities to learning domains
_CAPABILITY_DOMAIN_MAP: dict[str, str] = {
    "web_search": "research", "research": "research", "paper_search": "research",
    "paper_synthesis": "research", "github_scan": "research", "patent_search": "research",
    "trend_analysis": "research", "market_research": "research", "data_collection": "research",
    "fact_checking": "research", "source_discovery": "research", "competitive_intel": "research",
    "signal_detection": "research", "innovation_scan": "research", "emerging_tech": "research",
    "strategy_research": "trading", "backtesting": "trading", "market_analysis": "trading",
    "paper_trading": "trading", "trading_signals": "trading", "position_management": "trading",
    "financial_analysis": "trading", "financial_forecasting": "trading", "portfolio_analysis": "trading",
    "code_generation": "engineering", "code_review": "engineering", "debugging": "engineering",
    "refactoring": "engineering", "testing": "engineering", "deployment": "engineering",
    "architecture": "engineering", "backend_dev": "engineering", "frontend_dev": "engineering",
    "api_dev": "engineering", "devops": "engineering", "plugin_dev": "engineering",
    "lead_generation": "business", "startup_analysis": "business", "opportunity_scan": "business",
    "pricing_analysis": "business", "revenue_optimization": "business", "sales": "business",
    "writing": "content", "copywriting": "content", "article_writing": "content",
    "video_scripting": "content", "newsletter_creation": "content", "seo": "content",
    "content_marketing": "content", "social_media": "content",
    "security_audit": "security", "security_engineering": "security", "compliance": "security",
    "system_integrity": "security", "anomaly_detection": "security",
    "knowledge_graphs": "data", "data_pipeline": "data", "data_quality": "data",
    "data_analysis": "data", "data_mining": "data", "indexing": "data",
    "strategic_planning": "strategy", "decision_making": "strategy", "forecasting": "strategy",
    "scenario_simulation": "strategy", "risk_assessment": "strategy", "risk_modeling": "strategy",
    "health_monitoring": "infrastructure", "monitoring": "infrastructure", "ci_cd": "infrastructure",
    "infrastructure": "infrastructure", "disaster_recovery": "infrastructure",
    "cost_optimization": "infrastructure", "network_monitoring": "infrastructure",
}


@dataclass(frozen=True)
class AgentLearningRecord:
    """Immutable record of an agent's learning activity."""
    agent_id: str
    task: str
    domain: str
    finding_summary: str
    success: bool
    tools_used: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContinuousLearningEngine:
    """Ensures every agent in the civilization is always learning.

    Rotates through agents division by division, generates learning tasks
    from their capabilities, executes via the collaboration engine, and
    stores findings in experience memory.
    """

    DEFAULT_INTERVAL = 300  # 5 minutes between batches (free models = no cost concern)
    DEFAULT_BATCH_SIZE = 5  # Agents learning concurrently (free models can handle more)
    TASK_TIMEOUT = 120.0    # Per-agent learning task timeout

    def __init__(
        self,
        registry: Any = None,
        collab: Any = None,
        experience_memory: Any = None,
        memory: Any = None,
        bus: Any = None,
        state_store: Any = None,
        llm: Any = None,
        directive_engine: Any = None,
        learning_engine: Any = None,
    ) -> None:
        self._registry = registry
        self._collab = collab
        self._experience = experience_memory
        self._memory = memory
        self._bus = bus
        self._state_store = state_store
        self._llm = llm
        self._directive_engine = directive_engine
        self._learning_engine = learning_engine

        # Rotation state
        self._division_queue: list[str] = []
        self._agent_queue: list[str] = []
        self._current_division_idx = 0

        # Stats
        self._cycle_count = 0
        self._total_findings = 0
        self._agent_stats: dict[str, dict[str, Any]] = {}  # agent_id -> stats
        self._recent_records: list[AgentLearningRecord] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self, interval: Optional[int] = None) -> None:
        """Start the continuous learning loop."""
        if self._running:
            return
        self._running = True

        # Build division rotation queue
        if self._registry:
            divisions = self._registry.list_divisions()
            self._division_queue = list(divisions.keys())
            random.shuffle(self._division_queue)

        # Restore state
        if self._state_store:
            self._cycle_count = int(
                self._state_store.get_meta("continuous_learning_cycles", "0")
            )
            self._total_findings = int(
                self._state_store.get_meta("continuous_learning_findings", "0")
            )

        actual_interval = interval or self.DEFAULT_INTERVAL
        self._task = asyncio.create_task(self._loop(actual_interval))
        logger.info(
            "Continuous learning started (interval=%ds, divisions=%d)",
            actual_interval, len(self._division_queue),
        )

    def stop(self) -> None:
        """Stop the learning loop."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Continuous learning stopped")

    async def run_cycle(self) -> dict[str, Any]:
        """Run a single learning cycle — pick agents, assign tasks, store results."""
        self._cycle_count += 1
        cycle_start = datetime.now(timezone.utc)

        # Pick next batch of agents from rotation
        agents = self._pick_next_batch()
        if not agents:
            logger.info("Continuous learning: no agents available this cycle")
            return {"cycle": self._cycle_count, "agents_taught": 0, "findings": 0}

        # Generate and execute learning tasks concurrently
        tasks = []
        for agent_id in agents:
            tasks.append(self._teach_agent(agent_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        findings = 0
        agents_taught = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Learning task failed for %s: %s", agents[i], result
                )
                continue
            if result and result.success:
                findings += 1
                agents_taught += 1

        self._total_findings += findings

        # Persist state
        if self._state_store:
            self._state_store.set_meta(
                "continuous_learning_cycles", str(self._cycle_count)
            )
            self._state_store.set_meta(
                "continuous_learning_findings", str(self._total_findings)
            )

        # Broadcast learning activity
        if self._bus and findings > 0:
            msg = self._bus.create_message(
                topic="system.learning",
                sender="continuous_learning",
                payload={
                    "type": "learning_cycle",
                    "cycle": self._cycle_count,
                    "agents_taught": agents_taught,
                    "findings": findings,
                    "agents": agents,
                },
            )
            await self._bus.publish(msg)

        # Auto-create directives from significant findings
        await self._create_directives_from_findings(findings, agents)

        # Auto-adjust routing weights from learning performance
        await self._update_routing_from_findings()

        elapsed = (
            datetime.now(timezone.utc) - cycle_start
        ).total_seconds()
        logger.info(
            "Continuous learning cycle #%d: %d agents taught, %d findings (%.1fs)",
            self._cycle_count, agents_taught, findings, elapsed,
        )

        return {
            "cycle": self._cycle_count,
            "agents_taught": agents_taught,
            "findings": findings,
            "agents": agents,
            "elapsed_seconds": round(elapsed, 1),
        }

    # ── Agent selection ──────────────────────────────────────────

    def _pick_next_batch(self) -> list[str]:
        """Pick the next batch of agents using division round-robin.

        Ensures balanced coverage: cycles through divisions, picks agents
        from each. Agents that haven't learned recently get priority.
        """
        if not self._registry or not self._division_queue:
            return []

        batch: list[str] = []
        attempts = 0
        max_attempts = len(self._division_queue) * 2

        while len(batch) < self.DEFAULT_BATCH_SIZE and attempts < max_attempts:
            # Get next division
            div_name = self._division_queue[
                self._current_division_idx % len(self._division_queue)
            ]
            self._current_division_idx += 1
            attempts += 1

            # Get agents in this division
            div_agents = self._registry.list_division(div_name)
            if not div_agents:
                continue

            # Sort by least recently learned (prioritize agents that haven't learned)
            agent_ids = [a.id for a in div_agents]
            agent_ids.sort(
                key=lambda aid: self._agent_stats.get(aid, {}).get(
                    "last_learned", ""
                )
            )

            # Pick one agent from this division
            for aid in agent_ids:
                if aid not in batch:
                    batch.append(aid)
                    break

        return batch

    # ── Learning task execution ──────────────────────────────────

    async def _teach_agent(self, agent_id: str) -> AgentLearningRecord:
        """Generate and execute a learning task for a specific agent."""
        agent = self._registry.get(agent_id) if self._registry else None
        if not agent:
            return AgentLearningRecord(
                agent_id=agent_id, task="", domain="unknown",
                finding_summary="Agent not found", success=False,
            )

        # Determine learning domain from agent capabilities
        domain = self._get_agent_domain(agent)
        topic = self._get_learning_topic(agent)
        task_text = self._generate_learning_task(agent, domain, topic)

        logger.info("[%s] Learning task: %s", agent_id, task_text[:100])

        # Execute via collaboration engine
        try:
            result = await asyncio.wait_for(
                self._collab.delegate(
                    from_agent="continuous_learning",
                    to_agent=agent_id,
                    task=task_text,
                ),
                timeout=self.TASK_TIMEOUT,
            )
            finding = result.final_result or ""
            success = bool(finding and len(finding) > 50)
        except asyncio.TimeoutError:
            finding = "Learning task timed out"
            success = False
        except Exception as exc:
            finding = f"Error: {str(exc)[:200]}"
            success = False
            logger.error("[%s] Learning error: %s", agent_id, exc)

        # Store in experience memory
        if success and self._experience and finding:
            await self._store_learning(agent_id, agent.name, domain, topic, finding)

        # Store in regular memory too
        if success and self._memory and finding:
            self._store_memory(agent_id, domain, finding)

        # Update agent stats
        now = datetime.now(timezone.utc).isoformat()
        prev = self._agent_stats.get(agent_id, {
            "cycles": 0, "findings": 0, "last_learned": "",
        })
        self._agent_stats[agent_id] = {
            "cycles": prev["cycles"] + 1,
            "findings": prev["findings"] + (1 if success else 0),
            "last_learned": now,
            "last_domain": domain,
            "last_topic": topic,
        }

        record = AgentLearningRecord(
            agent_id=agent_id,
            task=task_text[:300],
            domain=domain,
            finding_summary=finding[:500] if finding else "",
            success=success,
        )
        self._recent_records = [*self._recent_records[-99:], record]
        return record

    def _get_agent_domain(self, agent: Any) -> str:
        """Determine the primary learning domain for an agent."""
        if not agent.capabilities:
            return "general"

        # Count domain votes from capabilities
        domain_votes: dict[str, int] = {}
        for cap in agent.capabilities:
            domain = _CAPABILITY_DOMAIN_MAP.get(cap.name, "general")
            domain_votes[domain] = domain_votes.get(domain, 0) + 1

        # Return most-voted domain
        return max(domain_votes, key=lambda d: domain_votes[d])

    def _get_learning_topic(self, agent: Any) -> str:
        """Generate a learning topic from the agent's role and capabilities."""
        parts = []
        if agent.role:
            parts.append(agent.role)
        if agent.capabilities:
            # Pick 1-2 random capabilities for variety
            caps = random.sample(
                agent.capabilities,
                min(2, len(agent.capabilities)),
            )
            parts.extend(c.name.replace("_", " ") for c in caps)
        return ", ".join(parts) if parts else agent.name

    def _generate_learning_task(
        self, agent: Any, domain: str, topic: str
    ) -> str:
        """Generate a specific learning task for this agent."""
        templates = _LEARNING_DOMAINS.get(domain, _LEARNING_DOMAINS["general"])
        template = random.choice(templates)
        task = template.format(topic=topic)

        return (
            f"LEARNING TASK for {agent.name} ({agent.role}):\n\n"
            f"{task}\n\n"
            f"Requirements:\n"
            f"- Use web_search and other tools to find REAL, current data\n"
            f"- Include specific numbers, dates, URLs, and sources\n"
            f"- Cross-check facts across multiple sources\n"
            f"- Summarize your findings in a structured format\n"
            f"- End with 2-3 actionable insights for Yohan's goals\n"
            f"- If you find something important, use propose_direction to flag it"
        )

    # ── Storage ──────────────────────────────────────────────────

    async def _store_learning(
        self, agent_id: str, agent_name: str, domain: str,
        topic: str, finding: str,
    ) -> None:
        """Store learning result in experience memory."""
        try:
            self._experience.record_experience(
                experience_type="strategy",
                domain=domain,
                title=f"[{agent_name}] Learning: {topic[:80]}",
                description=finding[:2000],
                context={"agent_id": agent_id, "source": "continuous_learning"},
                tags=["continuous_learning", domain, agent_id],
                confidence=0.7,
            )
        except Exception as exc:
            logger.error("Failed to store learning for %s: %s", agent_id, exc)

    def _store_memory(
        self, agent_id: str, domain: str, finding: str,
    ) -> None:
        """Store a concise version in regular memory."""
        try:
            from backend.models.memory import MemoryEntry, MemoryType
            self._memory.store(MemoryEntry(
                content=f"[Continuous Learning/{agent_id}] {finding[:500]}",
                memory_type=MemoryType.LEARNING,
                tags=["continuous_learning", domain, agent_id],
                source=f"continuous_learning/{agent_id}",
                confidence=0.65,
            ))
        except Exception as exc:
            logger.error("Failed to store memory for %s: %s", agent_id, exc)

    # ── Feedback: Learning → Directives ────────────────────────────

    async def _create_directives_from_findings(
        self, findings: int, agents: list[str],
    ) -> None:
        """When learning produces significant findings, auto-create directives.

        Closes the feedback loop: learning discoveries → strategic action.
        """
        if not self._directive_engine or findings < 2:
            return

        # Every 5 cycles with findings, create a directive to act on them
        if self._cycle_count % 5 != 0:
            return

        try:
            import uuid
            from backend.core.directive_engine import Directive

            # Get recent findings summary
            recent = self.get_recent_records(limit=10)
            successful = [r for r in recent if r.get("success")]
            if not successful:
                return

            domains = list({r.get("domain", "general") for r in successful})
            summaries = [r.get("finding_summary", "")[:100] for r in successful[:5]]

            directive = Directive(
                id=f"dir_{uuid.uuid4().hex[:12]}",
                title=f"Act on learning findings: {', '.join(domains[:3])}",
                rationale=(
                    f"Continuous learning cycle #{self._cycle_count} produced "
                    f"{findings} findings across {len(domains)} domains"
                ),
                priority=5,
                category="learning",
                assigned_agents=tuple(agents[:2]) if agents else ("researcher",),
                collab_pattern="delegate",
                task_description=(
                    f"Recent learning discoveries to act on:\n"
                    + "\n".join(f"- {s}" for s in summaries)
                    + "\n\nPropose specific actions ROOT should take based on these findings."
                ),
                source_signals=("continuous_learning", "actuator"),
            )
            self._directive_engine._store_directive(directive)
            logger.info(
                "Created directive from learning findings: %s", directive.id,
            )
        except Exception as exc:
            logger.warning("Failed to create directive from findings: %s", exc)

    async def _update_routing_from_findings(self) -> None:
        """Auto-adjust routing weights based on agent learning performance."""
        if not self._learning_engine:
            return

        # Agents that consistently produce good findings should be routed more
        for agent_id, stats in self._agent_stats.items():
            total_cycles = stats.get("cycles", 0)
            total_findings = stats.get("findings", 0)
            if total_cycles < 3:
                continue

            success_rate = total_findings / total_cycles
            domain = stats.get("last_domain", "general")

            if success_rate > 0.7:
                # High performer: boost routing weight
                try:
                    self._learning_engine.boost_routing_weight(
                        agent_id, domain, amount=0.02,
                    )
                except Exception as exc:
                    logger.warning("Failed to boost routing weight for %s/%s: %s", agent_id, domain, exc)
            elif success_rate < 0.2 and total_cycles >= 5:
                # Low performer: reduce routing weight
                try:
                    self._learning_engine.boost_routing_weight(
                        agent_id, domain, amount=-0.02,
                    )
                except Exception as exc:
                    logger.warning("Failed to reduce routing weight for %s/%s: %s", agent_id, domain, exc)

    # ── Background loop ──────────────────────────────────────────

    async def _loop(self, interval: int) -> None:
        """Main background loop."""
        await asyncio.sleep(180)  # Initial delay — let other systems start

        while self._running:
            try:
                await self.run_cycle()
            except Exception as exc:
                logger.error("Continuous learning error: %s", exc)
            await asyncio.sleep(interval)

    # ── Status & API ─────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Get learning engine statistics."""
        agents_with_learning = sum(
            1 for s in self._agent_stats.values() if s.get("findings", 0) > 0
        )
        return {
            "running": self._running,
            "cycles": self._cycle_count,
            "total_findings": self._total_findings,
            "agents_tracked": len(self._agent_stats),
            "agents_with_findings": agents_with_learning,
            "divisions_in_rotation": len(self._division_queue),
            "recent_records": len(self._recent_records),
        }

    def get_agent_stats(self, agent_id: Optional[str] = None) -> Any:
        """Get per-agent learning stats."""
        if agent_id:
            return self._agent_stats.get(agent_id, {})
        return dict(self._agent_stats)

    def get_recent_records(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent learning records."""
        records = self._recent_records[-limit:]
        return [
            {
                "agent_id": r.agent_id,
                "task": r.task,
                "domain": r.domain,
                "finding_summary": r.finding_summary[:200],
                "success": r.success,
                "timestamp": r.timestamp,
            }
            for r in reversed(records)
        ]

    def get_division_coverage(self) -> dict[str, dict[str, Any]]:
        """Get learning coverage per division."""
        if not self._registry:
            return {}

        coverage: dict[str, dict[str, Any]] = {}
        for div_name in self._division_queue:
            agents = self._registry.list_division(div_name)
            total = len(agents)
            learned = sum(
                1 for a in agents
                if self._agent_stats.get(a.id, {}).get("findings", 0) > 0
            )
            total_findings = sum(
                self._agent_stats.get(a.id, {}).get("findings", 0)
                for a in agents
            )
            coverage[div_name] = {
                "total_agents": total,
                "agents_learned": learned,
                "coverage_pct": round(learned / max(total, 1) * 100, 1),
                "total_findings": total_findings,
            }
        return coverage
