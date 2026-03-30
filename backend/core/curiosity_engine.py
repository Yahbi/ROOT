"""
Curiosity Engine — ROOT's intrinsic desire to learn.

This is not a scheduled task runner. This is ROOT's inner drive — the part
that *wants* to learn, that notices gaps in its own knowledge and feels
compelled to fill them. It generates learning goals from:

1. Failed tasks (what went wrong? how to avoid next time?)
2. Knowledge gaps (questions ROOT couldn't answer)
3. Trending topics (what's new in AI, markets, tech?)
4. Cross-pollination (connecting insights across domains)
5. Self-assessment (where am I weakest? what should I study?)

The engine creates a prioritized "curiosity queue" that feeds into the
continuous learning engine, autonomous loop, and directive engine.
It ensures ROOT is never idle — always exploring, always growing.

Philosophy: A truly autonomous AI doesn't wait to be told what to learn.
It identifies its own blind spots and pursues knowledge independently.
"""

from __future__ import annotations

import logging
import random
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.curiosity")


@dataclass(frozen=True)
class CuriosityItem:
    """An item ROOT is curious about — wants to learn."""
    id: str
    question: str
    domain: str
    source: str  # "failed_task", "knowledge_gap", "trending", "cross_pollination", "self_assessment"
    priority: float  # 0.0 to 1.0 — how urgently ROOT wants to know this
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved: bool = False
    resolution: str = ""


# Questions ROOT asks itself to drive learning
_SELF_ASSESSMENT_QUESTIONS = [
    "What topics did I fail to answer well recently? What should I study?",
    "Which of my agents have the lowest success rates? What training do they need?",
    "What new AI models, techniques, or tools have been released that I should learn about?",
    "What market opportunities am I missing because I lack knowledge in some area?",
    "What skills do top AI systems have that I don't? How can I acquire them?",
    "What patterns do I see across my recent failures? Is there a systemic gap?",
    "What would make Yohan's life easier that I haven't thought of yet?",
    "What emerging technologies could I integrate to become more capable?",
    "What do I know that's probably outdated? What needs refreshing?",
    "How could I combine knowledge from two different domains to create something new?",
]

# Domains ROOT proactively explores
_EXPLORATION_TOPICS = {
    "ai_frontier": [
        "latest open-source LLM releases and benchmarks",
        "new AI agent frameworks and architectures",
        "multimodal AI breakthroughs",
        "AI safety and alignment research",
        "efficient fine-tuning and quantization techniques",
        "RAG and retrieval improvements",
        "AI coding assistants and developer tools",
    ],
    "market_intelligence": [
        "cryptocurrency market trends and signals",
        "stock market anomalies and opportunities",
        "emerging startup sectors with high growth",
        "SaaS market trends and pricing strategies",
        "passive income automation strategies",
    ],
    "engineering_excellence": [
        "new Python libraries and frameworks",
        "database optimization techniques",
        "API design best practices",
        "performance optimization patterns",
        "observability and monitoring innovations",
    ],
    "business_growth": [
        "successful indie hacker case studies",
        "content monetization strategies",
        "automated lead generation techniques",
        "micro-SaaS success patterns",
        "AI consulting market trends",
    ],
    "self_improvement": [
        "how to build better autonomous AI systems",
        "self-improving code architectures",
        "knowledge graph construction techniques",
        "memory and retrieval optimization",
        "multi-agent coordination patterns",
    ],
}


class CuriosityEngine:
    """ROOT's inner drive to learn — generates curiosity from gaps, failures, and exploration.

    This engine ensures ROOT is never passive. It constantly:
    - Monitors for failed tasks and extracts learning questions
    - Identifies knowledge gaps from unanswered queries
    - Explores trending topics in AI, markets, and tech
    - Cross-pollinates ideas across different domains
    - Generates self-assessment questions to find blind spots
    """

    CYCLE_INTERVAL = 300  # 5 minutes — ROOT checks its curiosity often
    MAX_QUEUE_SIZE = 100
    ITEMS_PER_CYCLE = 5  # Generate up to 5 curiosity items per cycle

    def __init__(
        self,
        memory: Any = None,
        learning_engine: Any = None,
        experience_memory: Any = None,
        state_store: Any = None,
        bus: Any = None,
        llm: Any = None,
    ) -> None:
        self._memory = memory
        self._learning = learning_engine
        self._experience = experience_memory
        self._state_store = state_store
        self._bus = bus
        self._llm = llm

        self._queue: list[CuriosityItem] = []
        self._resolved: list[CuriosityItem] = []
        self._cycle_count = 0
        self._failure_count: int = 0
        self._total_questions_generated = 0
        self._total_questions_resolved = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Track what we've already explored to avoid repetition
        self._explored_topics: set[str] = set()
        self._failed_task_ids: set[str] = set()

    async def start(self) -> None:
        """Start the curiosity loop."""
        if self._running:
            return
        self._running = True

        # Restore state
        if self._state_store:
            self._cycle_count = int(self._state_store.get_meta("curiosity_cycles", "0"))
            self._total_questions_generated = int(self._state_store.get_meta("curiosity_questions", "0"))
            self._total_questions_resolved = int(self._state_store.get_meta("curiosity_resolved", "0"))

        self._task = asyncio.create_task(self._loop())
        logger.info("Curiosity engine started — ROOT's desire to learn is ACTIVE")

    def stop(self) -> None:
        """Stop the curiosity loop."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Curiosity engine stopped")

    async def _loop(self) -> None:
        """Main curiosity loop — runs every 5 minutes."""
        await asyncio.sleep(60)  # Let other systems start first

        while self._running:
            try:
                await self.run_cycle()
                self._failure_count = 0
            except Exception as exc:
                self._failure_count = self._failure_count + 1
                logger.error("Curiosity cycle error: %s", exc)
                if self._failure_count >= 5:
                    logger.critical(
                        "Curiosity engine: %d consecutive failures — backing off 300s",
                        self._failure_count,
                    )
                    self._failure_count = 0
                    await asyncio.sleep(300)
                    continue
            await asyncio.sleep(self.CYCLE_INTERVAL)

    async def run_cycle(self) -> dict[str, Any]:
        """Run a curiosity cycle — generate questions and feed them to learning systems."""
        self._cycle_count += 1

        # 1. Generate curiosity from multiple sources
        new_items: list[CuriosityItem] = []

        # Source 1: Self-assessment (every cycle)
        new_items.extend(self._generate_self_assessment())

        # Source 2: Failed tasks (check recent failures)
        new_items.extend(await self._learn_from_failures())

        # Source 3: Knowledge gaps (from unanswered questions)
        new_items.extend(self._identify_knowledge_gaps())

        # Source 4: Exploration (proactively explore new topics)
        new_items.extend(self._generate_exploration_topics())

        # Source 5: Cross-pollination (connect different domains)
        new_items.extend(self._cross_pollinate())

        # Add to queue (deduplicated, priority-sorted)
        added = 0
        for item in new_items:
            if not self._is_duplicate(item) and len(self._queue) < self.MAX_QUEUE_SIZE:
                self._queue.append(item)
                added += 1
                self._total_questions_generated += 1

        # Sort by priority (highest first)
        self._queue.sort(key=lambda x: x.priority, reverse=True)

        # 2. Feed top items to learning systems
        fed = await self._feed_to_learning()

        # 3. Persist state
        if self._state_store:
            self._state_store.set_meta("curiosity_cycles", str(self._cycle_count))
            self._state_store.set_meta("curiosity_questions", str(self._total_questions_generated))
            self._state_store.set_meta("curiosity_resolved", str(self._total_questions_resolved))

        # 4. Broadcast curiosity activity
        if self._bus and added > 0:
            msg = self._bus.create_message(
                topic="system.curiosity",
                sender="curiosity_engine",
                payload={
                    "type": "curiosity_cycle",
                    "cycle": self._cycle_count,
                    "new_questions": added,
                    "queue_size": len(self._queue),
                    "fed_to_learning": fed,
                },
            )
            await self._bus.publish(msg)

        logger.info(
            "Curiosity cycle #%d: +%d questions, %d in queue, %d fed to learning",
            self._cycle_count, added, len(self._queue), fed,
        )

        return {
            "cycle": self._cycle_count,
            "new_questions": added,
            "queue_size": len(self._queue),
            "fed_to_learning": fed,
        }

    # ── Source 1: Self-Assessment ─────────────────────────────────

    def _generate_self_assessment(self) -> list[CuriosityItem]:
        """ROOT asks itself what it needs to learn."""
        items: list[CuriosityItem] = []

        # Pick 1 self-assessment question per cycle
        question = _SELF_ASSESSMENT_QUESTIONS[
            self._cycle_count % len(_SELF_ASSESSMENT_QUESTIONS)
        ]

        items.append(CuriosityItem(
            id=f"curiosity_self_{self._cycle_count}",
            question=question,
            domain="self_improvement",
            source="self_assessment",
            priority=0.8,
        ))

        return items

    # ── Source 2: Learning from Failures ──────────────────────────

    async def _learn_from_failures(self) -> list[CuriosityItem]:
        """Extract learning questions from recent task failures."""
        items: list[CuriosityItem] = []

        if not self._experience:
            return items

        try:
            # Query recent failures from experience memory
            failures = self._experience.get_experiences(
                experience_type="failure",
                limit=10,
            )
            for f in failures:
                fid = getattr(f, "id", "") or ""
                if fid in self._failed_task_ids:
                    continue
                self._failed_task_ids.add(fid)

                desc = (getattr(f, "description", "") or "")[:200]
                domain = getattr(f, "domain", "general") or "general"

                items.append(CuriosityItem(
                    id=f"curiosity_fail_{fid[:12]}",
                    question=f"Why did this fail and how to prevent it: {desc}",
                    domain=domain,
                    source="failed_task",
                    priority=0.9,  # High priority — learn from mistakes
                ))

                if len(items) >= 2:
                    break
        except Exception as exc:
            logger.debug("Failed to extract failures: %s", exc)

        return items

    # ── Source 3: Knowledge Gaps ──────────────────────────────────

    def _identify_knowledge_gaps(self) -> list[CuriosityItem]:
        """Find topics ROOT has been asked about but couldn't answer well."""
        items: list[CuriosityItem] = []

        if not self._learning:
            return items

        try:
            # Find agents/domains with low success rates
            stats = self._learning.stats()
            weights = stats.get("routing_weights", {})

            for domain, weight_info in weights.items():
                if isinstance(weight_info, dict):
                    # Low-weight domains indicate weak performance
                    for agent_id, weight in weight_info.items():
                        if isinstance(weight, (int, float)) and weight < 0.3:
                            items.append(CuriosityItem(
                                id=f"curiosity_gap_{domain}_{agent_id}",
                                question=f"How to improve {agent_id}'s performance in {domain}? Current routing weight is very low.",
                                domain=domain,
                                source="knowledge_gap",
                                priority=0.7,
                            ))
                            if len(items) >= 2:
                                return items
        except Exception as exc:
            logger.debug("Failed to identify knowledge gaps: %s", exc)

        return items

    # ── Source 4: Proactive Exploration ────────────────────────────

    def _generate_exploration_topics(self) -> list[CuriosityItem]:
        """Proactively explore new topics ROOT should know about."""
        items: list[CuriosityItem] = []

        # Pick a random domain to explore
        domain = random.choice(list(_EXPLORATION_TOPICS.keys()))
        topics = _EXPLORATION_TOPICS[domain]

        # Pick a topic we haven't explored recently
        unexplored = [t for t in topics if t not in self._explored_topics]
        if not unexplored:
            # Reset explored set for this domain
            self._explored_topics -= set(topics)
            unexplored = topics

        topic = random.choice(unexplored)
        self._explored_topics.add(topic)

        items.append(CuriosityItem(
            id=f"curiosity_explore_{self._cycle_count}_{domain}",
            question=f"Research and learn about: {topic}. What's new, what's important, what can ROOT use?",
            domain=domain,
            source="trending",
            priority=0.6,
        ))

        return items

    # ── Source 5: Cross-Pollination ───────────────────────────────

    def _cross_pollinate(self) -> list[CuriosityItem]:
        """Connect insights across different domains to spark innovation."""
        items: list[CuriosityItem] = []

        # Only cross-pollinate every 3 cycles
        if self._cycle_count % 3 != 0:
            return items

        domains = list(_EXPLORATION_TOPICS.keys())
        if len(domains) < 2:
            return items

        d1, d2 = random.sample(domains, 2)
        t1 = random.choice(_EXPLORATION_TOPICS[d1])
        t2 = random.choice(_EXPLORATION_TOPICS[d2])

        items.append(CuriosityItem(
            id=f"curiosity_cross_{self._cycle_count}",
            question=f"How could insights from '{t1}' ({d1}) be applied to '{t2}' ({d2})? Find unexpected connections.",
            domain="cross_domain",
            source="cross_pollination",
            priority=0.5,
        ))

        return items

    # ── Feed to Learning Systems ──────────────────────────────────

    async def _feed_to_learning(self) -> int:
        """Feed top curiosity items to the learning systems for resolution."""
        if not self._llm or not self._queue:
            return 0

        fed = 0
        items_to_resolve = self._queue[:3]  # Process top 3

        for item in items_to_resolve:
            try:
                # Use the LLM to research the question (via free model)
                response = await self._llm.complete(
                    messages=[{"role": "user", "content": item.question}],
                    system=(
                        "You are ROOT's curiosity engine. Research this question thoroughly. "
                        "Provide specific, actionable findings with data points. "
                        "Be concise but informative. Include sources where possible."
                    ),
                    model_tier="fast",  # Use fast/free tier for curiosity
                    method="proactive",  # Routes to free providers
                )

                if response and len(response) > 50:
                    # Store the learning
                    resolved_item = CuriosityItem(
                        id=item.id,
                        question=item.question,
                        domain=item.domain,
                        source=item.source,
                        priority=item.priority,
                        created_at=item.created_at,
                        resolved=True,
                        resolution=response[:2000],
                    )

                    # Store in experience memory
                    if self._experience:
                        try:
                            self._experience.record_experience(
                                experience_type="strategy",
                                domain=item.domain,
                                title=f"[Curiosity] {item.question[:80]}",
                                description=response[:2000],
                                context={"source": item.source, "curiosity_id": item.id},
                                tags=["curiosity", item.domain, item.source],
                                confidence=0.7,
                            )
                        except Exception as exc:
                            logger.warning("Failed to record curiosity experience for %s: %s", item.id, exc)

                    # Store in regular memory
                    if self._memory:
                        try:
                            from backend.models.memory import MemoryEntry, MemoryType
                            self._memory.store(MemoryEntry(
                                content=f"[Curiosity/{item.domain}] Q: {item.question[:100]} A: {response[:400]}",
                                memory_type=MemoryType.LEARNING,
                                tags=["curiosity", item.domain],
                                source="curiosity_engine",
                                confidence=0.65,
                            ))
                        except Exception as exc:
                            logger.warning("Failed to store curiosity memory for %s: %s", item.id, exc)

                    self._resolved = [*self._resolved[-99:], resolved_item]
                    self._total_questions_resolved += 1
                    fed += 1

                    # Remove from queue
                    self._queue = [q for q in self._queue if q.id != item.id]

            except Exception as exc:
                logger.debug("Failed to resolve curiosity item %s: %s", item.id, exc)

        return fed

    # ── Deduplication ─────────────────────────────────────────────

    def _is_duplicate(self, item: CuriosityItem) -> bool:
        """Check if this question is already in queue or recently resolved."""
        q_lower = item.question.lower()[:80]

        for existing in self._queue:
            if existing.question.lower()[:80] == q_lower:
                return True

        for resolved in self._resolved[-50:]:
            if resolved.question.lower()[:80] == q_lower:
                return True

        return False

    # ── External API ──────────────────────────────────────────────

    def add_curiosity(self, question: str, domain: str = "general", priority: float = 0.7) -> CuriosityItem:
        """Externally inject a curiosity item (e.g., from a failed chat response)."""
        import uuid
        item = CuriosityItem(
            id=f"curiosity_ext_{uuid.uuid4().hex[:8]}",
            question=question,
            domain=domain,
            source="external",
            priority=min(max(priority, 0.0), 1.0),
        )
        if not self._is_duplicate(item) and len(self._queue) < self.MAX_QUEUE_SIZE:
            self._queue.append(item)
            self._total_questions_generated += 1
            logger.info("Added external curiosity: %s", question[:80])
        return item

    def get_queue(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get the current curiosity queue."""
        return [
            {
                "id": item.id,
                "question": item.question,
                "domain": item.domain,
                "source": item.source,
                "priority": item.priority,
                "created_at": item.created_at,
            }
            for item in self._queue[:limit]
        ]

    def get_resolved(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recently resolved curiosity items."""
        return [
            {
                "id": item.id,
                "question": item.question,
                "domain": item.domain,
                "source": item.source,
                "resolution": item.resolution[:300],
                "created_at": item.created_at,
            }
            for item in reversed(self._resolved[-limit:])
        ]

    def stats(self) -> dict[str, Any]:
        """Curiosity engine statistics."""
        source_counts: dict[str, int] = {}
        for item in self._queue:
            source_counts[item.source] = source_counts.get(item.source, 0) + 1

        return {
            "running": self._running,
            "cycles": self._cycle_count,
            "queue_size": len(self._queue),
            "total_questions_generated": self._total_questions_generated,
            "total_questions_resolved": self._total_questions_resolved,
            "resolution_rate": round(
                self._total_questions_resolved / max(self._total_questions_generated, 1), 4
            ),
            "source_distribution": source_counts,
            "explored_topics": len(self._explored_topics),
        }
