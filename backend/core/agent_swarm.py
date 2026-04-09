"""
Agent Swarm — Continuous activation engine for all 172 civilization agents.

Ensures agents are never idle by rotating tasks across all 10 divisions.
Every cycle dispatches 6-8 tasks to random agents, cycles through divisions,
and cross-pollinates knowledge between agents in different divisions.

Background loop runs every 2 minutes:
1. Pick 3-4 random divisions
2. For each, pick 1-2 random tasks
3. Dispatch to agents in that division
4. Record outcomes in memory + experience memory
5. Cross-pollinate between agents from different divisions
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.swarm")


# ── Division task catalog ───────────────────────────────────────────

DIVISION_TASKS: dict[str, list[str]] = {
    "Strategy Council": [
        "Analyze ROOT's current strategic position and recommend 3 improvements",
        "Evaluate market opportunities for the next 24 hours",
        "Review all active goals and assess priority alignment",
        "Identify emerging technology trends that ROOT should monitor",
        "Assess competitive landscape for AI trading systems",
    ],
    "Research Division": [
        "Search for latest academic papers on multi-agent systems",
        "Research new quantitative trading strategies published this month",
        "Find patent filings related to autonomous AI trading",
        "Investigate latest machine learning techniques for time series prediction",
        "Research options trading strategies and their risk profiles",
    ],
    "Engineering Division": [
        "Review ROOT's backend code for performance bottlenecks",
        "Analyze error patterns in recent logs and suggest fixes",
        "Evaluate database query efficiency and suggest optimizations",
        "Review API endpoint security and suggest hardening",
        "Assess system architecture for scalability improvements",
    ],
    "Data & Memory Division": [
        "Analyze memory quality and identify low-confidence entries for pruning",
        "Build knowledge graph connections between related memories",
        "Identify gaps in ROOT's knowledge base and prioritize filling them",
        "Evaluate embedding quality and suggest improvements",
        "Analyze learning engine routing weights for optimization",
    ],
    "Learning & Improvement": [
        "Analyze recent experiment results and extract lessons",
        "Evaluate which autonomous actions have highest ROI",
        "Review prediction accuracy and suggest calibration improvements",
        "Design new experiments to test trading hypotheses",
        "Analyze skill execution success rates and improve matching",
    ],
    "Economic Engine": [
        "Scan for new revenue opportunities using ROOT's capabilities",
        "Analyze current market conditions for trading signals",
        "Evaluate SaaS product ideas based on ROOT's data assets",
        "Research pricing strategies for AI-powered services",
        "Identify automation opportunities that generate recurring revenue",
    ],
    "Content Network": [
        "Draft a market analysis report based on ROOT's latest findings",
        "Create a summary of trading insights from this week",
        "Write documentation for ROOT's newest features",
        "Generate content ideas for a newsletter about AI trading",
    ],
    "Automation Business": [
        "Identify processes that can be automated with ROOT's plugins",
        "Design workflow automation for data collection",
        "Evaluate lead generation strategies using web scraping",
        "Research chatbot deployment for customer acquisition",
    ],
    "Infrastructure Operations": [
        "Monitor system health metrics and report anomalies",
        "Analyze database growth patterns and project capacity needs",
        "Evaluate backup and recovery procedures",
        "Review cost optimization opportunities for LLM usage",
    ],
    "Governance & Safety": [
        "Audit recent autonomous decisions for alignment with Yohan's interests",
        "Review trading risk exposure and suggest adjustments",
        "Evaluate data privacy and security compliance",
        "Assess ethical implications of current autonomous behaviors",
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Agent Swarm ─────────────────────────────────────────────────────


class AgentSwarm:
    """Continuous activation engine — keeps all 172 agents busy with
    rotating tasks matched to their division and capabilities."""

    def __init__(
        self,
        collab: Any = None,
        registry: Any = None,
        bus: Any = None,
        memory: Any = None,
        learning: Any = None,
        experience_memory: Any = None,
        llm: Any = None,
    ) -> None:
        self.collab = collab
        self.registry = registry
        self.bus = bus
        self.memory = memory
        self.learning = learning
        self.experience_memory = experience_memory
        self.llm = llm

        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._total_dispatches = 0
        self._divisions_activated: set[str] = set()
        self._cross_pollinations = 0
        self._by_division: dict[str, int] = defaultdict(int)

    # ── Division activation ─────────────────────────────────────────

    async def activate_division(self, division: str) -> list[dict[str, Any]]:
        """Dispatch all tasks for a division to random agents within it.

        Returns a list of result dicts for each dispatched task.
        """
        tasks = DIVISION_TASKS.get(division)
        if not tasks:
            logger.warning("Unknown division: %s", division)
            return []

        agents = self._get_division_agents(division)
        if not agents:
            logger.warning("No agents registered for division: %s", division)
            return []

        results: list[dict[str, Any]] = []
        dispatch_coros = []

        for task in tasks:
            agent = random.choice(agents)
            dispatch_coros.append(self._dispatch_task(division, agent, task))

        # Parallel dispatch
        outcomes = await asyncio.gather(*dispatch_coros, return_exceptions=True)
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                logger.error("Dispatch error in %s: %s", division, outcome)
                results.append({"division": division, "status": "error", "error": str(outcome)})
            else:
                results.append(outcome)

        self._divisions_activated.add(division)
        return results

    async def _dispatch_task(
        self, division: str, agent_id: str, task: str
    ) -> dict[str, Any]:
        """Delegate a single task to an agent, store results, publish to bus."""
        dispatch_id = f"swarm_{uuid.uuid4().hex[:10]}"
        started = _now_iso()
        result_text = ""
        status = "completed"

        try:
            # Delegate via collaboration protocol
            if self.collab:
                workflow = await self.collab.delegate(
                    from_agent="agent_swarm",
                    to_agent=agent_id,
                    task=task,
                    timeout_seconds=120,
                )
                result_text = (
                    workflow.steps[-1].result
                    if workflow.steps and workflow.steps[-1].result
                    else "No result returned"
                )
            else:
                logger.debug("No collab engine — skipping delegation for %s", agent_id)
                result_text = "collab unavailable"
                status = "skipped"
        except Exception as exc:
            logger.error("Delegation failed [%s -> %s]: %s", division, agent_id, exc)
            result_text = f"error: {exc}"
            status = "failed"

        outcome = {
            "dispatch_id": dispatch_id,
            "division": division,
            "agent_id": agent_id,
            "task": task,
            "result": result_text,
            "status": status,
            "started_at": started,
            "completed_at": _now_iso(),
        }

        self._total_dispatches += 1
        self._by_division[division] += 1

        # Persist to memory
        await self._store_result(outcome)

        # Publish to bus (triggers Neural Galaxy signals)
        await self._publish_result(outcome)

        # Publish swarm.dispatch event for Neural Galaxy visualization
        if self.bus:
            try:
                msg = self.bus.create_message(
                    topic="swarm.dispatch",
                    sender="agent_swarm",
                    payload={
                        "division": division,
                        "from_agent": "agent_swarm",
                        "to_agent": agent_id,
                        "task": task[:100],
                    },
                )
                await self.bus.publish(msg)
            except Exception as exc:
                logger.debug("swarm.dispatch bus publish failed: %s", exc)

        return outcome

    async def _store_result(self, outcome: dict[str, Any]) -> None:
        """Store dispatch result in memory and experience memory."""
        try:
            if self.memory:
                from backend.models.memory import MemoryEntry, MemoryType

                entry = MemoryEntry(
                    content=(
                        f"[Swarm/{outcome['division']}] Agent {outcome['agent_id']} "
                        f"completed task: {outcome['task'][:100]}... "
                        f"Result: {outcome['result'][:200]}"
                    ),
                    memory_type=MemoryType.LEARNING,
                    source="agent_swarm",
                    confidence=0.6,
                    tags=["swarm", "dispatch", outcome["division"].lower().replace(" ", "_")],
                )
                self.memory.store(entry)
        except Exception as exc:
            logger.error("Memory store failed: %s", exc)

        try:
            if self.experience_memory and outcome["status"] == "completed":
                self.experience_memory.record_experience(
                    experience_type="strategy",
                    domain="agent_swarm",
                    title=f"Swarm dispatch: {outcome['division']}",
                    description=(
                        f"Agent {outcome['agent_id']} executed: {outcome['task'][:150]}. "
                        f"Result: {outcome['result'][:300]}"
                    ),
                    context={
                        "dispatch_id": outcome["dispatch_id"],
                        "division": outcome["division"],
                        "agent_id": outcome["agent_id"],
                    },
                )
        except Exception as exc:
            logger.error("Experience memory store failed: %s", exc)

    async def _publish_result(self, outcome: dict[str, Any]) -> None:
        """Publish dispatch result to the message bus."""
        try:
            if self.bus:
                from backend.core.message_bus import BusMessage, MessagePriority

                msg = BusMessage(
                    id=outcome["dispatch_id"],
                    topic=f"swarm.{outcome['division'].lower().replace(' ', '_')}.result",
                    sender="agent_swarm",
                    payload={
                        "agent_id": outcome["agent_id"],
                        "task": outcome["task"],
                        "result": outcome["result"],
                        "status": outcome["status"],
                    },
                    priority=MessagePriority.BACKGROUND,
                )
                await self.bus.publish(msg)
        except Exception as exc:
            logger.error("Bus publish failed: %s", exc)

    # ── Cross-pollination ───────────────────────────────────────────

    async def cross_pollinate(self) -> dict[str, Any]:
        """Pair agents from different divisions to share knowledge.

        Picks 2 agents from different divisions.  Agent A summarizes what
        it learned recently; Agent B responds with how it connects to
        their domain.  Both findings are stored in memory.
        """
        divisions = list(DIVISION_TASKS.keys())
        if len(divisions) < 2:
            return {"status": "skipped", "reason": "not enough divisions"}

        div_a, div_b = random.sample(divisions, 2)
        agents_a = self._get_division_agents(div_a)
        agents_b = self._get_division_agents(div_b)

        if not agents_a or not agents_b:
            return {"status": "skipped", "reason": "empty division(s)"}

        agent_a = random.choice(agents_a)
        agent_b = random.choice(agents_b)

        pollination_id = f"xpol_{uuid.uuid4().hex[:8]}"
        summary_a = ""
        response_b = ""

        try:
            # Agent A summarizes recent learnings
            if self.collab:
                wf_a = await self.collab.delegate(
                    from_agent="agent_swarm",
                    to_agent=agent_a,
                    task=(
                        "Summarize the most important thing you learned or "
                        "worked on recently. Be specific and concise."
                    ),
                    timeout_seconds=90,
                )
                summary_a = (
                    wf_a.steps[-1].result
                    if wf_a.steps and wf_a.steps[-1].result
                    else "No summary available"
                )

                # Agent B responds with cross-domain connection
                wf_b = await self.collab.delegate(
                    from_agent="agent_swarm",
                    to_agent=agent_b,
                    task=(
                        f"An agent from {div_a} shared this insight: '{summary_a[:500]}'. "
                        f"How does this connect to your work in {div_b}? "
                        f"What actionable idea does this spark?"
                    ),
                    timeout_seconds=90,
                )
                response_b = (
                    wf_b.steps[-1].result
                    if wf_b.steps and wf_b.steps[-1].result
                    else "No response available"
                )
        except Exception as exc:
            logger.error("Cross-pollination failed [%s <-> %s]: %s", div_a, div_b, exc)
            return {
                "pollination_id": pollination_id,
                "status": "error",
                "error": str(exc),
            }

        self._cross_pollinations += 1

        # Store findings in memory
        try:
            if self.memory:
                from backend.models.memory import MemoryEntry, MemoryType

                entry = MemoryEntry(
                    content=(
                        f"[Cross-pollination] {div_a} ({agent_a}) -> {div_b} ({agent_b}): "
                        f"Insight: {summary_a[:200]}. "
                        f"Connection: {response_b[:200]}"
                    ),
                    memory_type=MemoryType.LEARNING,
                    source="agent_swarm",
                    confidence=0.65,
                    tags=["swarm", "cross_pollination", div_a.lower().replace(" ", "_"),
                          div_b.lower().replace(" ", "_")],
                )
                self.memory.store(entry)
        except Exception as exc:
            logger.error("Cross-pollination memory store failed: %s", exc)

        try:
            if self.experience_memory:
                self.experience_memory.record_experience(
                    experience_type="lesson",
                    domain="agent_swarm",
                    title=f"Cross-pollination: {div_a} <-> {div_b}",
                    description=(
                        f"Agent {agent_a} ({div_a}) shared: {summary_a[:200]}. "
                        f"Agent {agent_b} ({div_b}) connected: {response_b[:200]}"
                    ),
                    context={
                        "pollination_id": pollination_id,
                        "agent_a": agent_a,
                        "agent_b": agent_b,
                        "division_a": div_a,
                        "division_b": div_b,
                    },
                )
        except Exception as exc:
            logger.error("Cross-pollination experience store failed: %s", exc)

        # Publish to bus
        try:
            if self.bus:
                from backend.core.message_bus import BusMessage, MessagePriority

                msg = BusMessage(
                    id=pollination_id,
                    topic="swarm.cross_pollination",
                    sender="agent_swarm",
                    payload={
                        "agent_a": agent_a,
                        "agent_b": agent_b,
                        "division_a": div_a,
                        "division_b": div_b,
                        "summary": summary_a[:300],
                        "connection": response_b[:300],
                    },
                    priority=MessagePriority.BACKGROUND,
                )
                await self.bus.publish(msg)
        except Exception as exc:
            logger.error("Cross-pollination bus publish failed: %s", exc)

        return {
            "pollination_id": pollination_id,
            "status": "completed",
            "agent_a": agent_a,
            "agent_b": agent_b,
            "division_a": div_a,
            "division_b": div_b,
            "summary_a": summary_a[:300],
            "response_b": response_b[:300],
        }

    # ── Background loop ─────────────────────────────────────────────

    async def start(self, interval: int = 120) -> None:
        """Start the background activation loop.

        Every *interval* seconds (default 120 = 2 minutes):
        1. Pick 3-4 random divisions
        2. For each, pick 1-2 random tasks
        3. Dispatch to agents in that division
        4. Run one cross-pollination round
        """
        if self._running:
            logger.warning("Agent swarm already running")
            return

        self._running = True
        logger.info("Agent swarm started (interval=%ds)", interval)

        async def _loop() -> None:
            while self._running:
                try:
                    await self._run_cycle()
                except Exception as exc:
                    logger.error("Swarm cycle error: %s", exc)

                try:
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        """Stop the background activation loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("except asyncio.CancelledError suppressed", exc_info=True)
        logger.info("Agent swarm stopped")

    async def _run_cycle(self) -> None:
        """Execute one swarm cycle: dispatch tasks + cross-pollinate."""
        divisions = list(DIVISION_TASKS.keys())

        # Pick 3-4 random divisions
        num_divisions = random.randint(3, 4)
        selected_divisions = random.sample(divisions, min(num_divisions, len(divisions)))

        dispatch_coros = []
        for division in selected_divisions:
            agents = self._get_division_agents(division)
            if not agents:
                continue

            # Pick 1-2 random tasks per division
            division_tasks = DIVISION_TASKS[division]
            num_tasks = random.randint(1, 2)
            selected_tasks = random.sample(
                division_tasks, min(num_tasks, len(division_tasks))
            )

            for task in selected_tasks:
                agent_id = random.choice(agents)
                dispatch_coros.append(self._dispatch_task(division, agent_id, task))

        # Parallel dispatch of all tasks (~6-8 tasks)
        if dispatch_coros:
            outcomes = await asyncio.gather(*dispatch_coros, return_exceptions=True)
            completed = sum(
                1 for o in outcomes if not isinstance(o, Exception)
                and isinstance(o, dict) and o.get("status") == "completed"
            )
            logger.info(
                "Swarm cycle: dispatched %d tasks, %d completed",
                len(dispatch_coros), completed,
            )

        # Cross-pollinate
        try:
            xpol = await self.cross_pollinate()
            if xpol.get("status") == "completed":
                logger.info(
                    "Cross-pollination: %s (%s) <-> %s (%s)",
                    xpol.get("agent_a"), xpol.get("division_a"),
                    xpol.get("agent_b"), xpol.get("division_b"),
                )
        except Exception as exc:
            logger.error("Cross-pollination error: %s", exc)

    # ── Stats ───────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return current swarm statistics."""
        return {
            "running": self._running,
            "total_dispatches": self._total_dispatches,
            "divisions_activated": sorted(self._divisions_activated),
            "cross_pollinations": self._cross_pollinations,
            "by_division": dict(self._by_division),
        }

    # ── Helpers ─────────────────────────────────────────────────────

    def _get_division_agents(self, division: str) -> list[str]:
        """Get agent IDs for a division from the registry."""
        if not self.registry:
            return []
        try:
            agents = self.registry.list_division(division)
            return [a.id for a in agents] if agents else []
        except Exception as exc:
            logger.error("Registry lookup failed for %s: %s", division, exc)
            return []
