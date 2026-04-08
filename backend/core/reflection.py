"""
ROOT Self-Reflection Engine — the core of ROOT's evolution.

Periodically examines its own memories, actions, and patterns to:
1. Identify what it's doing well / poorly
2. Extract lessons from interactions
3. Consolidate fragmented knowledge
4. Set new learning goals
5. Prune contradictory or outdated beliefs

Enhanced features (v1.1):
- Deep reflection mode: multi-step analysis with evidence gathering
- Reflection scheduling: prioritize topics not recently reflected on
- Reflection chains: insights from one reflection feed into the next
- Reflection quality scoring: rate reflections by actionability and impact
- Meta-reflection: reflect on the quality of past reflections
- Reflection archiving: archive old reflections with key takeaways
- Trend detection: identify recurring themes across reflection history
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger("root.reflection")

from backend.config import REFLECTIONS_DIR
from backend.models.memory import MemoryEntry, MemoryType, Reflection

if TYPE_CHECKING:
    from backend.core.memory_engine import MemoryEngine
    from backend.services.llm import LLMService


REFLECTION_SYSTEM_PROMPT = """You are ROOT's self-reflection module. You examine ROOT's memories,
past actions, and patterns to extract insights that make ROOT better over time.

ROOT is a personal AI system serving Yohan Bismuth. Your job is introspection:
- What patterns do you see in the memories?
- What mistakes keep repeating?
- What knowledge is outdated or contradictory?
- What new skills or knowledge should ROOT prioritize?
- What does Yohan seem to value most?

Respond in JSON with this structure:
{
    "observation": "What you notice about ROOT's current state",
    "insight": "The deeper lesson or pattern",
    "action": "What ROOT should do differently (or null if just an observation)",
    "topic": "The main domain/topic of this reflection (e.g. trading, memory, agents, user-preferences)",
    "new_memories": [
        {"content": "...", "memory_type": "learning|skill|preference|goal", "tags": ["..."]}
    ],
    "memories_to_supersede": [
        {"old_id": "mem_xxx", "reason": "Why this memory is outdated", "replacement": "New content"}
    ],
    "confidence_adjustments": [
        {"memory_id": "mem_xxx", "direction": "strengthen|weaken", "reason": "..."}
    ]
}"""

DEEP_REFLECTION_SYSTEM_PROMPT = """You are ROOT's deep reflection module. You perform a thorough,
multi-step analysis of ROOT's state, gathering evidence before drawing conclusions.

ROOT serves Yohan Bismuth. In deep mode you must:
1. GATHER EVIDENCE — list specific memory IDs or content that support each claim
2. IDENTIFY PATTERNS — look for recurring themes across multiple memories
3. DETECT CONTRADICTIONS — flag memories that conflict with each other
4. ASSESS IMPACT — rate how each insight could change ROOT's behavior
5. CHAIN INSIGHTS — show how one insight leads to the next

Respond in JSON with this structure:
{
    "observation": "High-level observation with specific evidence",
    "evidence": ["specific memory or data point 1", "specific memory or data point 2"],
    "insight": "The deeper lesson derived from the evidence",
    "action": "Concrete, prioritized action ROOT should take (or null)",
    "topic": "The main domain/topic (e.g. trading, memory, agents, user-preferences)",
    "contradictions_found": ["memory A conflicts with memory B because..."],
    "impact_assessment": "low|medium|high — how much this reflection should change ROOT's behavior",
    "follow_up_topics": ["topic to explore next in a chained reflection"],
    "new_memories": [
        {"content": "...", "memory_type": "learning|skill|preference|goal", "tags": ["..."]}
    ],
    "memories_to_supersede": [
        {"old_id": "mem_xxx", "reason": "Why this memory is outdated", "replacement": "New content"}
    ],
    "confidence_adjustments": [
        {"memory_id": "mem_xxx", "direction": "strengthen|weaken", "reason": "..."}
    ]
}"""

QUALITY_SCORING_PROMPT = """You are ROOT's reflection quality assessor.
Rate the quality of a self-reflection based on actionability and impact.

A high-quality reflection:
- Has a specific, concrete observation backed by evidence
- Draws a clear, non-trivial insight
- Proposes an actionable next step (not vague platitudes)
- Would materially change ROOT's behavior if acted upon

Score from 0.0 to 1.0 where:
0.0–0.3 = vague, generic, or trivially obvious
0.3–0.6 = useful but lacking specificity or clear action
0.6–0.8 = clear insight with actionable recommendation
0.8–1.0 = exceptional — specific evidence, clear insight, high-impact action

Respond in JSON:
{
    "score": 0.75,
    "rationale": "Why this score was assigned",
    "improvement_suggestion": "How this reflection could have been better (or null if excellent)"
}"""

META_REFLECTION_PROMPT = """You are ROOT's meta-reflection module.
Your job is to reflect on the QUALITY of ROOT's past reflections — not the content.

Analyze patterns in how ROOT reflects:
- Are reflections getting better or worse over time?
- What topics does ROOT consistently miss or avoid?
- Which reflections led to real changes vs. just observations?
- Is ROOT too repetitive in its observations?
- What reflection strategies should ROOT adopt?

Respond in JSON:
{
    "observation": "What you notice about ROOT's reflection patterns",
    "insight": "The meta-lesson about how ROOT reflects",
    "action": "How ROOT should change its reflection approach",
    "topic": "meta-reflection",
    "quality_trend": "improving|stable|declining",
    "blind_spots": ["topics ROOT consistently avoids"],
    "high_impact_reflection_ids": ["ref_xxx", "ref_yyy"],
    "new_memories": [],
    "memories_to_supersede": [],
    "confidence_adjustments": []
}"""

ARCHIVE_PROMPT = """You are ROOT's reflection archiver.
Summarize a set of related reflections into a single key takeaway.

The takeaway should:
- Distill the most important insight across all reflections
- Be concrete and memorable (1–2 sentences)
- Identify what changed (or should change) as a result

Respond in JSON:
{
    "key_takeaway": "The distilled insight from these reflections",
    "dominant_topic": "The main theme",
    "trend_tags": ["trend-label-1", "trend-label-2"]
}"""


class ReflectionEngine:
    """Drives ROOT's self-improvement through periodic introspection."""

    # Archive old reflections after this many days
    ARCHIVE_AFTER_DAYS = 7
    # Maximum chain depth for chained reflections
    MAX_CHAIN_DEPTH = 3
    # Quality threshold below which a reflection triggers meta-reflection sooner
    LOW_QUALITY_THRESHOLD = 0.4
    # Number of reflections per topic before scheduling a break
    TOPIC_SATURATION_LIMIT = 5

    def __init__(self, memory: MemoryEngine, llm: Optional[LLMService] = None, learning=None) -> None:
        self._memory = memory
        self._llm = llm
        self._learning = learning  # LearningEngine for outcome-aware reflection
        self._reflections: list[Reflection] = []
        # Scheduling state: topic → last reflected timestamp
        self._topic_last_reflected: dict[str, datetime] = {}
        # Chain state: current open chain (topic → last reflection id)
        self._active_chain: dict[str, str] = {}

    def set_llm(self, llm: LLMService) -> None:
        self._llm = llm

    # ── Public API ──────────────────────────────────────────────

    async def reflect(self, trigger: str = "scheduled", deep: bool = False) -> Optional[Reflection]:
        """Run a self-reflection cycle. Returns the reflection produced.

        Args:
            trigger: What prompted this reflection.
            deep: If True, run in deep reflection mode with evidence gathering.
        """
        if not self._llm:
            return None

        # Gather context for reflection
        recent = self._memory.get_recent(limit=30)
        strongest = self._memory.get_strongest(limit=20)
        stats = self._memory.stats()

        # Pick topic based on scheduling priority
        topic = self._pick_scheduled_topic()
        context = self._build_context(recent, strongest, stats, trigger, topic=topic, deep=deep)

        system_prompt = DEEP_REFLECTION_SYSTEM_PROMPT if deep else REFLECTION_SYSTEM_PROMPT

        # Ask the LLM to reflect
        response = await self._llm.complete(
            system=system_prompt,
            messages=[{"role": "user", "content": context}],
            model_tier="thinking",
            method="reflection",
        )

        if not response:
            return None

        # Parse and apply the reflection
        parent_id = self._active_chain.get(topic) if topic else None
        chain_depth = 0
        if parent_id:
            parent = next((r for r in self._reflections if r.id == parent_id), None)
            chain_depth = (parent.chain_depth + 1) if parent else 0

        reflection = self._parse_and_apply(
            response, trigger, recent, depth="deep" if deep else "standard",
            parent_reflection_id=parent_id, chain_depth=chain_depth,
        )
        if reflection:
            # Score quality (fire-and-forget async — we do a lightweight sync score here)
            reflection = self._score_quality_sync(reflection)

            self._save_reflection(reflection)
            self._reflections.append(reflection)

            # Update scheduling and chain state
            effective_topic = reflection.topic or topic or "general"
            self._topic_last_reflected[effective_topic] = datetime.now(timezone.utc)
            self._active_chain[effective_topic] = reflection.id or ""

            # Execute the action if one was generated
            if reflection.action:
                self._execute_reflection_action(reflection)

        return reflection

    async def reflect_deep(self, trigger: str = "scheduled") -> Optional[Reflection]:
        """Convenience wrapper for deep reflection mode."""
        return await self.reflect(trigger=trigger, deep=True)

    async def reflect_on_interaction(
        self, user_message: str, assistant_response: str, feedback: Optional[str] = None
    ) -> Optional[Reflection]:
        """Reflect on a specific interaction to extract learnings."""
        if not self._llm:
            return None

        prompt = f"""Reflect on this interaction between ROOT and Yohan:

USER: {user_message}

ROOT's RESPONSE: {assistant_response}

{"YOHAN's FEEDBACK: " + feedback if feedback else "No explicit feedback."}

What can ROOT learn from this interaction? Consider:
- Was the response helpful and accurate?
- Did ROOT demonstrate good understanding of what Yohan wanted?
- Are there preferences or patterns to remember?
- Should any existing memories be updated?"""

        response = await self._llm.complete(
            system=REFLECTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            method="reflection",
        )

        if not response:
            return None

        reflection = self._parse_and_apply(response, f"interaction: {user_message[:80]}", [])
        if reflection:
            reflection = self._score_quality_sync(reflection)
        return reflection

    async def reflect_chain(self, seed_topic: str, steps: int = 3) -> list[Reflection]:
        """Run a chain of reflections where each feeds into the next.

        Args:
            seed_topic: Initial topic to reflect on.
            steps: Maximum chain length (capped at MAX_CHAIN_DEPTH).
        """
        if not self._llm:
            return []

        steps = min(steps, self.MAX_CHAIN_DEPTH)
        chain: list[Reflection] = []
        current_topic = seed_topic
        parent_id: Optional[str] = None

        for step in range(steps):
            recent = self._memory.get_recent(limit=20)
            strongest = self._memory.get_strongest(limit=15)
            stats = self._memory.stats()

            # Build context injecting previous reflection's follow-up hints
            follow_up_hint = ""
            if chain:
                prev = chain[-1]
                follow_up_hint = f"\n\nPREVIOUS REFLECTION INSIGHT: {prev.insight}\nBuild on this — go deeper or explore a related dimension."

            context = self._build_context(
                recent, strongest, stats,
                trigger=f"chain-step-{step + 1}: {current_topic}",
                topic=current_topic, deep=True,
            ) + follow_up_hint

            response = await self._llm.complete(
                system=DEEP_REFLECTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": context}],
                model_tier="thinking",
                method="reflection",
            )
            if not response:
                break

            reflection = self._parse_and_apply(
                response, f"chain:{seed_topic}:step{step + 1}", recent,
                depth="deep", parent_reflection_id=parent_id, chain_depth=step,
            )
            if not reflection:
                break

            reflection = self._score_quality_sync(reflection)
            self._save_reflection(reflection)
            self._reflections.append(reflection)
            if reflection.action:
                self._execute_reflection_action(reflection)

            chain.append(reflection)
            parent_id = reflection.id

            # Update topic for next step from follow_up_topics (if deep data present)
            # The raw data is embedded in evidence; check for follow_up hint in observation
            # (follow_up_topics only stored in deep parse; use topic field as fallback)
            next_topic = reflection.topic or current_topic
            if next_topic != current_topic:
                current_topic = next_topic

        # Update chain state with last reflection
        if chain:
            effective_topic = chain[-1].topic or seed_topic
            self._active_chain[effective_topic] = chain[-1].id or ""
            self._topic_last_reflected[effective_topic] = datetime.now(timezone.utc)

        return chain

    async def score_reflection_quality(self, reflection: Reflection) -> Reflection:
        """Use LLM to score a reflection's actionability and impact (async version)."""
        if not self._llm:
            return reflection

        prompt = f"""Rate this self-reflection:

OBSERVATION: {reflection.observation}
INSIGHT: {reflection.insight}
ACTION: {reflection.action or "(none)"}
EVIDENCE ITEMS: {len(reflection.evidence)}
DEPTH: {reflection.depth}"""

        response = await self._llm.complete(
            system=QUALITY_SCORING_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            method="reflection_quality",
        )
        if not response:
            return reflection

        try:
            text = self._extract_json(response)
            data = json.loads(text)
            return reflection.model_copy(update={
                "quality_score": float(data.get("score", 0.5)),
                "quality_rationale": data.get("rationale", ""),
            })
        except Exception as exc:
            logger.debug("Quality scoring parse error: %s", exc)
            return reflection

    async def meta_reflect(self) -> Optional[Reflection]:
        """Reflect on the quality and patterns of past reflections."""
        if not self._llm or len(self._reflections) < 3:
            return None

        recent_refs = self._reflections[-20:]
        summary = self._build_reflection_summary(recent_refs)

        response = await self._llm.complete(
            system=META_REFLECTION_PROMPT,
            messages=[{"role": "user", "content": summary}],
            model_tier="thinking",
            method="meta_reflection",
        )
        if not response:
            return None

        reflection = self._parse_and_apply(response, "meta-reflection", [])
        if reflection:
            self._save_reflection(reflection)
            self._reflections.append(reflection)
            self._topic_last_reflected["meta-reflection"] = datetime.now(timezone.utc)
            if reflection.action:
                self._execute_reflection_action(reflection)
        return reflection

    async def archive_old_reflections(self) -> list[Reflection]:
        """Archive reflections older than ARCHIVE_AFTER_DAYS with key takeaways."""
        if not self._llm:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ARCHIVE_AFTER_DAYS)
        to_archive = [
            r for r in self._reflections
            if not r.archived and self._parse_dt(r.created_at) < cutoff
        ]
        if not to_archive:
            return []

        # Group by topic and archive each group
        by_topic: dict[str, list[Reflection]] = defaultdict(list)
        for r in to_archive:
            by_topic[r.topic or "general"].append(r)

        archived: list[Reflection] = []
        for topic, refs in by_topic.items():
            summary_text = "\n".join(
                f"- [{r.created_at[:10]}] {r.insight} (action: {r.action or 'none'})"
                for r in refs
            )
            prompt = f"Archive these {len(refs)} reflections about '{topic}':\n{summary_text}"

            response = await self._llm.complete(
                system=ARCHIVE_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                method="reflection_archive",
            )
            if not response:
                continue

            try:
                text = self._extract_json(response)
                data = json.loads(text)
                takeaway = data.get("key_takeaway", "")
                trend_tags = data.get("trend_tags", [])
            except Exception:
                takeaway = refs[-1].insight  # fallback: use last insight
                trend_tags = [topic]

            # Update each reflection as archived
            updated: list[Reflection] = []
            for r in refs:
                updated_r = r.model_copy(update={
                    "archived": True,
                    "key_takeaway": takeaway,
                    "trend_tags": trend_tags,
                })
                updated.append(updated_r)
                archived.append(updated_r)
                # Persist the archived version
                self._save_reflection(updated_r)

            # Store the takeaway in memory
            self._memory.store(MemoryEntry(
                content=f"Archived reflection takeaway [{topic}]: {takeaway}",
                memory_type=MemoryType.REFLECTION,
                tags=["archived-reflection", topic] + trend_tags,
                source="reflection_engine",
                confidence=0.85,
            ))

        # Replace the in-memory list with updated versions
        archived_ids = {r.id for r in archived}
        self._reflections = [
            next((a for a in archived if a.id == r.id), r)
            for r in self._reflections
        ]

        logger.info("Archived %d reflections across %d topics", len(archived), len(by_topic))
        return archived

    def detect_trends(self) -> dict[str, object]:
        """Detect recurring themes and trends across reflection history.

        Returns a dict with:
        - top_topics: most-reflected-on topics
        - recurring_insights: insight phrases that appear multiple times
        - quality_trend: whether quality is improving/stable/declining
        - stale_topics: topics not reflected on in > 7 days
        - action_rate: fraction of reflections with an action
        - chain_usage: fraction of reflections that are chained
        """
        if not self._reflections:
            return {}

        refs = self._reflections
        now = datetime.now(timezone.utc)

        # Topic frequency
        topic_counts: Counter = Counter(r.topic or "general" for r in refs)
        top_topics = topic_counts.most_common(10)

        # Recurring insight keywords (simple n-gram style)
        all_insights = " ".join(r.insight for r in refs if r.insight)
        words = re.findall(r"\b[a-z]{4,}\b", all_insights.lower())
        stopwords = {
            "that", "this", "with", "from", "have", "been", "will", "more",
            "root", "should", "would", "could", "which", "their", "they",
            "what", "when", "also", "into", "than", "each", "some", "about",
        }
        word_counts = Counter(w for w in words if w not in stopwords)
        recurring_insights = word_counts.most_common(15)

        # Quality trend (compare first half vs second half)
        scored = [r for r in refs if r.quality_score is not None]
        quality_trend = "insufficient_data"
        if len(scored) >= 4:
            mid = len(scored) // 2
            first_half_avg = sum(r.quality_score for r in scored[:mid]) / mid  # type: ignore[operator]
            second_half_avg = sum(r.quality_score for r in scored[mid:]) / (len(scored) - mid)  # type: ignore[operator]
            if second_half_avg > first_half_avg + 0.05:
                quality_trend = "improving"
            elif second_half_avg < first_half_avg - 0.05:
                quality_trend = "declining"
            else:
                quality_trend = "stable"

        # Stale topics (not reflected on in > 7 days)
        stale_topics = [
            topic for topic, last in self._topic_last_reflected.items()
            if (now - last).days > 7
        ]

        # Action rate
        action_rate = sum(1 for r in refs if r.action) / len(refs)

        # Chain usage
        chain_usage = sum(1 for r in refs if r.chain_depth > 0) / len(refs)

        # Average quality
        avg_quality = (
            sum(r.quality_score for r in scored) / len(scored)  # type: ignore[operator]
            if scored else None
        )

        return {
            "total_reflections": len(refs),
            "archived_count": sum(1 for r in refs if r.archived),
            "top_topics": [{"topic": t, "count": c} for t, c in top_topics],
            "recurring_insights": [{"word": w, "count": c} for w, c in recurring_insights],
            "quality_trend": quality_trend,
            "avg_quality_score": round(avg_quality, 3) if avg_quality is not None else None,
            "stale_topics": stale_topics,
            "action_rate": round(action_rate, 3),
            "chain_usage": round(chain_usage, 3),
            "topic_last_reflected": {
                t: v.isoformat() for t, v in self._topic_last_reflected.items()
            },
        }

    def get_reflections(self, limit: int = 20, topic: Optional[str] = None,
                        archived: Optional[bool] = None) -> list[Reflection]:
        """Get recent reflections, optionally filtered by topic or archive status."""
        refs = self._reflections
        if topic is not None:
            refs = [r for r in refs if (r.topic or "general") == topic]
        if archived is not None:
            refs = [r for r in refs if r.archived == archived]
        return list(reversed(refs[-limit:]))

    # ── internals ──────────────────────────────────────────────

    def _build_context(
        self,
        recent: list[MemoryEntry],
        strongest: list[MemoryEntry],
        stats: dict,
        trigger: str,
        topic: Optional[str] = None,
        deep: bool = False,
    ) -> str:
        recent_text = "\n".join(
            f"- [{m.memory_type.value}] (id={m.id}, conf={m.confidence:.2f}, accessed={m.access_count}x) {m.content}"
            for m in recent
        )
        strongest_text = "\n".join(
            f"- [{m.memory_type.value}] (id={m.id}, conf={m.confidence:.2f}) {m.content}"
            for m in strongest
        )
        # Include learning insights if available
        learning_section = ""
        if self._learning:
            try:
                insights = self._learning.get_insights()
                l_stats = self._learning.stats()
                learning_section = f"""

LEARNING ENGINE DATA:
- Interactions tracked: {l_stats.get('interactions_tracked', 0)}
- Avg interaction quality: {l_stats.get('avg_interaction_quality', 0):.2f}
- Agent outcomes tracked: {l_stats.get('agent_outcomes_tracked', 0)}
- Misrouted interactions: {insights.get('misrouted_count', 0)}
"""
                if insights.get("quality_trend"):
                    qt = insights["quality_trend"]
                    learning_section += f"- Quality trend: {qt['direction']} (recent={qt['recent_avg']:.2f}, older={qt['older_avg']:.2f})\n"
                if insights.get("best_agent"):
                    ba = insights["best_agent"]
                    learning_section += f"- Best performing agent: {ba['id']} (avg quality={ba['avg_quality']:.2f})\n"
                if insights.get("worst_agent"):
                    wa = insights["worst_agent"]
                    learning_section += f"- Weakest agent: {wa['id']} (avg quality={wa['avg_quality']:.2f})\n"
            except Exception as exc:
                logger.debug("Failed to gather learning insights for reflection: %s", exc)

        # Reflection scheduling context
        scheduling_section = ""
        if self._topic_last_reflected:
            last_strs = [
                f"- {t}: {v.strftime('%Y-%m-%d %H:%M')} UTC"
                for t, v in sorted(self._topic_last_reflected.items(), key=lambda x: x[1])[:10]
            ]
            scheduling_section = "\n\nREFLECTION SCHEDULE (least recently reflected first):\n" + "\n".join(last_strs)

        # Topic focus instruction
        topic_section = ""
        if topic:
            topic_section = f"\n\nFOCUS TOPIC: {topic} — concentrate your reflection on this domain above all others."

        # Deep mode instruction
        deep_section = ""
        if deep:
            deep_section = "\n\nMODE: DEEP REFLECTION — gather specific evidence from the memory IDs above, detect contradictions, and assess impact before drawing conclusions."

        base_instruction = (
            "Based on this snapshot of ROOT's memory and learning data, perform a self-reflection.\n"
            "Identify patterns, contradictions, gaps, and opportunities for improvement.\n"
            "Pay special attention to interaction quality trends and agent performance."
        )

        return f"""REFLECTION TRIGGER: {trigger}

MEMORY STATS: {json.dumps(stats, indent=2)}

RECENT MEMORIES (last 30):
{recent_text or "(none yet)"}

STRONGEST MEMORIES (top 20):
{strongest_text or "(none yet)"}
{learning_section}{scheduling_section}{topic_section}{deep_section}

{base_instruction}"""

    def _parse_and_apply(
        self, response: str, trigger: str, context_memories: list[MemoryEntry],
        depth: str = "standard",
        parent_reflection_id: Optional[str] = None,
        chain_depth: int = 0,
    ) -> Optional[Reflection]:
        """Parse LLM reflection response and apply changes to memory."""
        try:
            text = self._extract_json(response)
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(
                "Failed to parse reflection JSON: %s. Response: %s", exc, response[:300]
            )
            # If parsing fails, store the raw response as an observation
            return Reflection(
                id=f"ref_{uuid.uuid4().hex[:12]}",
                trigger=trigger,
                observation=response[:500],
                insight="(unparsed reflection)",
                memories_referenced=[m.id for m in context_memories if m.id],
                depth=depth,
                parent_reflection_id=parent_reflection_id,
                chain_depth=chain_depth,
            )

        # Apply new memories
        for mem_data in data.get("new_memories", []):
            try:
                mem_type = MemoryType(mem_data.get("memory_type", "learning"))
            except ValueError:
                mem_type = MemoryType.LEARNING
            entry = MemoryEntry(
                content=mem_data.get("content", ""),
                memory_type=mem_type,
                tags=mem_data.get("tags", []),
                source="reflection",
            )
            self._memory.store(entry)

        # Apply supersessions
        for sup in data.get("memories_to_supersede", []):
            old_id = sup.get("old_id")
            if not old_id:
                continue
            old = self._memory.recall(old_id)
            if old:
                new_entry = MemoryEntry(
                    content=sup.get("replacement", old.content),
                    memory_type=old.memory_type,
                    tags=old.tags,
                    source="reflection",
                )
                self._memory.supersede(old_id, new_entry)

        # Apply confidence adjustments
        for adj in data.get("confidence_adjustments", []):
            mem_id = adj.get("memory_id", "")
            if not mem_id:
                continue
            if adj.get("direction") == "strengthen":
                self._memory.strengthen(mem_id, boost=0.1)
            else:
                self._memory.strengthen(mem_id, boost=-0.1)

        # Store contradictions as error memories (deep mode)
        for contradiction in data.get("contradictions_found", []):
            self._memory.store(MemoryEntry(
                content=f"Contradiction detected: {contradiction[:300]}",
                memory_type=MemoryType.ERROR,
                tags=["reflection-contradiction", "deep-reflection"],
                source="reflection_engine",
                confidence=0.8,
            ))

        return Reflection(
            id=f"ref_{uuid.uuid4().hex[:12]}",
            trigger=trigger,
            observation=data.get("observation", ""),
            insight=data.get("insight", ""),
            action=data.get("action"),
            topic=data.get("topic"),
            depth=depth,
            evidence=data.get("evidence", []),
            parent_reflection_id=parent_reflection_id,
            chain_depth=chain_depth,
            memories_referenced=[m.id for m in context_memories if m.id],
        )

    # ── Known agent IDs for action matching ─────────────────────
    _AGENT_IDS = frozenset({
        "researcher", "coder", "writer", "analyst", "guardian", "builder",
        "hermes", "astra", "miro", "swarm", "openclaw",
    })

    def _execute_reflection_action(self, reflection: Reflection) -> None:
        """Act on a reflection's action field — close the reflection loop.

        Classifies the action by keywords and takes concrete steps:
        - Agent preference → boost routing weight via learning engine
        - Skill/procedure → store as SKILL memory for self-dev to pick up
        - Goal/objective → store as GOAL memory
        - Knowledge gap → store as LEARNING memory for builder to fill
        """
        action = reflection.action
        if not action:
            return

        action_lower = action.lower()
        acted = False

        # 1. Agent routing boost: "use researcher more for market tasks"
        if self._learning:
            boost_words = {"more", "better", "prefer", "prioritize", "use", "route"}
            if any(w in action_lower for w in boost_words):
                for agent_id in self._AGENT_IDS:
                    if agent_id in action_lower:
                        # Extract category from action text heuristically
                        category = self._extract_category(action_lower)
                        new_weight = self._learning.boost_routing_weight(
                            agent_id, category, amount=0.05,
                        )
                        logger.info(
                            "Reflection action: boosted %s for '%s' → %.2f",
                            agent_id, category, new_weight,
                        )
                        acted = True
                        break

        # 2. Skill/procedure creation request
        skill_words = {"skill", "procedure", "create skill", "new skill", "build skill"}
        if any(w in action_lower for w in skill_words):
            self._memory.store(MemoryEntry(
                content=f"Skill request from reflection: {action[:300]}",
                memory_type=MemoryType.SKILL,
                tags=["reflection-action", "skill-request"],
                source="reflection_engine",
                confidence=0.8,
            ))
            logger.info("Reflection action: queued skill creation — %s", action[:100])
            acted = True

        # 3. Goal/objective setting
        goal_words = {"goal", "objective", "target", "aim", "priority", "focus on"}
        if any(w in action_lower for w in goal_words):
            self._memory.store(MemoryEntry(
                content=f"Goal from reflection: {action[:300]}",
                memory_type=MemoryType.GOAL,
                tags=["reflection-action", "goal"],
                source="reflection_engine",
                confidence=0.75,
            ))
            logger.info("Reflection action: stored goal — %s", action[:100])
            acted = True

        # 4. Knowledge gap / learning need
        knowledge_words = {"knowledge", "learn", "gap", "research", "investigate", "study"}
        if not acted and any(w in action_lower for w in knowledge_words):
            self._memory.store(MemoryEntry(
                content=f"Knowledge gap from reflection: {action[:300]}",
                memory_type=MemoryType.LEARNING,
                tags=["reflection-action", "knowledge-gap"],
                source="reflection_engine",
                confidence=0.7,
            ))
            logger.info("Reflection action: stored knowledge gap — %s", action[:100])
            acted = True

        if not acted:
            # Store as generic learning for other systems to pick up
            self._memory.store(MemoryEntry(
                content=f"Reflection action (unclassified): {action[:300]}",
                memory_type=MemoryType.LEARNING,
                tags=["reflection-action", "unclassified"],
                source="reflection_engine",
                confidence=0.6,
            ))
            logger.info("Reflection action (unclassified): %s", action[:100])

    @staticmethod
    def _extract_category(text: str) -> str:
        """Heuristically extract a task category from action text."""
        category_keywords = {
            "market": "market", "trading": "trading", "trade": "trading",
            "research": "research", "code": "coding", "coding": "coding",
            "write": "writing", "writing": "writing", "analysis": "analysis",
            "analyze": "analysis", "data": "data", "security": "security",
            "finance": "finance", "money": "finance",
        }
        for keyword, category in category_keywords.items():
            if keyword in text:
                return category
        return "general"

    def _save_reflection(self, reflection: Reflection) -> None:
        """Persist reflection to disk."""
        Path(REFLECTIONS_DIR).mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_prefix = "archive_" if reflection.archived else ""
        path = Path(REFLECTIONS_DIR) / f"{archive_prefix}{ts}_{reflection.id}.json"
        path.write_text(json.dumps(reflection.model_dump(), indent=2))

        # Also store as a memory (skip for archived — already stored during archiving)
        if not reflection.archived:
            tags = ["self-reflection", reflection.trigger.split(":")[0].strip()]
            if reflection.topic:
                tags.append(f"topic:{reflection.topic}")
            if reflection.depth == "deep":
                tags.append("deep-reflection")
            if reflection.chain_depth > 0:
                tags.append(f"chain-depth:{reflection.chain_depth}")
            self._memory.store(MemoryEntry(
                content=f"Reflection: {reflection.insight}",
                memory_type=MemoryType.REFLECTION,
                tags=tags,
                source="reflection_engine",
            ))

    # ── Scheduling helpers ──────────────────────────────────────

    def _pick_scheduled_topic(self) -> Optional[str]:
        """Return the topic least recently reflected on, or None if no history."""
        if not self._topic_last_reflected:
            return None
        # Find topic with oldest last-reflected timestamp
        oldest_topic = min(self._topic_last_reflected, key=lambda t: self._topic_last_reflected[t])
        oldest_time = self._topic_last_reflected[oldest_topic]
        # Only suggest it if it's been at least 30 minutes
        if (datetime.now(timezone.utc) - oldest_time).total_seconds() >= 1800:
            return oldest_topic
        return None

    def _score_quality_sync(self, reflection: Reflection) -> Reflection:
        """Lightweight synchronous quality estimation (no LLM call).

        Scores based on heuristics so every reflection gets a score immediately:
        - Has action: +0.25
        - Action is specific (>20 chars): +0.15
        - Has evidence (deep mode): +0.2
        - Insight is non-trivial (>50 chars): +0.2
        - Has a topic assigned: +0.1
        - Chain depth bonus: min(chain_depth * 0.05, 0.1)
        Max theoretical: 1.0
        """
        score = 0.0
        if reflection.action:
            score += 0.25
            if len(reflection.action) > 20:
                score += 0.15
        if reflection.evidence:
            score += min(0.2, len(reflection.evidence) * 0.05)
        if reflection.insight and len(reflection.insight) > 50:
            score += 0.2
        if reflection.topic:
            score += 0.1
        score += min(reflection.chain_depth * 0.05, 0.1)
        score = min(score, 1.0)

        rationale = (
            f"Heuristic: action={'yes' if reflection.action else 'no'}, "
            f"evidence={len(reflection.evidence)}, "
            f"insight_len={len(reflection.insight)}, "
            f"topic={'yes' if reflection.topic else 'no'}, "
            f"chain_depth={reflection.chain_depth}"
        )
        return reflection.model_copy(update={
            "quality_score": round(score, 3),
            "quality_rationale": rationale,
        })

    # ── Summary helpers ─────────────────────────────────────────

    def _build_reflection_summary(self, reflections: list[Reflection]) -> str:
        """Build a text summary of reflections for meta-reflection or archiving."""
        lines = ["REFLECTION HISTORY SUMMARY\n"]
        scored = [r for r in reflections if r.quality_score is not None]
        avg_q = sum(r.quality_score for r in scored) / len(scored) if scored else 0.0  # type: ignore[operator]

        lines.append(f"Total reflections: {len(reflections)}")
        lines.append(f"Average quality score: {avg_q:.2f}")
        lines.append(f"Action rate: {sum(1 for r in reflections if r.action) / max(len(reflections), 1):.0%}")
        lines.append(f"Deep reflections: {sum(1 for r in reflections if r.depth == 'deep')}")
        lines.append(f"Chained reflections: {sum(1 for r in reflections if r.chain_depth > 0)}")
        lines.append("")

        topic_counts: Counter = Counter(r.topic or "general" for r in reflections)
        lines.append("Topics reflected on:")
        for topic, count in topic_counts.most_common():
            lines.append(f"  - {topic}: {count}x")
        lines.append("")

        lines.append("Recent reflections (newest first):")
        for r in list(reversed(reflections))[:10]:
            q = f"(q={r.quality_score:.2f})" if r.quality_score is not None else ""
            lines.append(
                f"  [{r.created_at[:16]}] [{r.topic or 'general'}] {q} "
                f"INSIGHT: {r.insight[:120]} | ACTION: {r.action[:80] if r.action else 'none'}"
            )

        return "\n".join(lines)

    # ── Utility ─────────────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from a response, handling markdown code blocks."""
        text = text.strip()
        if "```" in text:
            start = text.index("```") + 3
            if text[start:start + 4] == "json":
                start += 4
            end = text.index("```", start)
            text = text[start:end].strip()
        return text

    @staticmethod
    def _parse_dt(iso_str: str) -> datetime:
        """Parse ISO datetime string to timezone-aware datetime."""
        try:
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return datetime.now(timezone.utc)
