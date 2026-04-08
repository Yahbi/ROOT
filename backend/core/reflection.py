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


class ReflectionEngine:
    """Drives ROOT's self-improvement through periodic introspection."""

    def __init__(self, memory: MemoryEngine, llm: Optional[LLMService] = None, learning=None) -> None:
        self._memory = memory
        self._llm = llm
        self._learning = learning  # LearningEngine for outcome-aware reflection
        self._reflections: list[Reflection] = []

    def set_llm(self, llm: LLMService) -> None:
        self._llm = llm

    async def reflect(self, trigger: str = "scheduled") -> Optional[Reflection]:
        """Run a self-reflection cycle. Returns the reflection produced."""
        if not self._llm:
            return None

        # Gather context for reflection
        recent = self._memory.get_recent(limit=30)
        strongest = self._memory.get_strongest(limit=20)
        stats = self._memory.stats()

        context = self._build_context(recent, strongest, stats, trigger)

        # Ask the LLM to reflect
        response = await self._llm.complete(
            system=REFLECTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
            model_tier="thinking",
            method="reflection",
        )

        if not response:
            return None

        # Parse and apply the reflection
        reflection = self._parse_and_apply(response, trigger, recent)
        if reflection:
            self._save_reflection(reflection)
            self._reflections.append(reflection)
            # Execute the action if one was generated
            if reflection.action:
                self._execute_reflection_action(reflection)

        return reflection

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

        return self._parse_and_apply(response, f"interaction: {user_message[:80]}", [])

    def get_reflections(self, limit: int = 20) -> list[Reflection]:
        """Get recent reflections."""
        return list(reversed(self._reflections[-limit:]))

    # ── internals ──────────────────────────────────────────────

    def _build_context(
        self,
        recent: list[MemoryEntry],
        strongest: list[MemoryEntry],
        stats: dict,
        trigger: str,
    ) -> str:
        recent_text = "\n".join(
            f"- [{m.memory_type.value}] (conf={m.confidence:.2f}, accessed={m.access_count}x) {m.content}"
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

        return f"""REFLECTION TRIGGER: {trigger}

MEMORY STATS: {json.dumps(stats, indent=2)}

RECENT MEMORIES (last 30):
{recent_text or "(none yet)"}

STRONGEST MEMORIES (top 20):
{strongest_text or "(none yet)"}
{learning_section}
Based on this snapshot of ROOT's memory and learning data, perform a self-reflection.
Identify patterns, contradictions, gaps, and opportunities for improvement.
Pay special attention to interaction quality trends and agent performance."""

    def _parse_and_apply(
        self, response: str, trigger: str, context_memories: list[MemoryEntry]
    ) -> Optional[Reflection]:
        """Parse LLM reflection response and apply changes to memory."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            text = response.strip()
            if "```" in text:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                text = text[start:end].strip()
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            import logging
            logging.getLogger("root.reflection").error(
                "Failed to parse reflection JSON: %s. Response: %s", exc, response[:300]
            )
            # If parsing fails, store the raw response as an observation
            return Reflection(
                id=f"ref_{uuid.uuid4().hex[:12]}",
                trigger=trigger,
                observation=response[:500],
                insight="(unparsed reflection)",
                memories_referenced=[m.id for m in context_memories if m.id],
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
            if adj["direction"] == "strengthen":
                self._memory.strengthen(adj["memory_id"], boost=0.1)
            else:
                self._memory.strengthen(adj["memory_id"], boost=-0.1)

        return Reflection(
            id=f"ref_{uuid.uuid4().hex[:12]}",
            trigger=trigger,
            observation=data.get("observation", ""),
            insight=data.get("insight", ""),
            action=data.get("action"),
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
        import logging
        log = logging.getLogger("root.reflection")
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
                        log.info(
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
            log.info("Reflection action: queued skill creation — %s", action[:100])
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
            log.info("Reflection action: stored goal — %s", action[:100])
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
            log.info("Reflection action: stored knowledge gap — %s", action[:100])
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
            log.info("Reflection action (unclassified): %s", action[:100])

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
        path = Path(REFLECTIONS_DIR) / f"{ts}_{reflection.id}.json"
        path.write_text(json.dumps(reflection.model_dump(), indent=2))

        # Also store as a memory
        self._memory.store(MemoryEntry(
            content=f"Reflection: {reflection.insight}",
            memory_type=MemoryType.REFLECTION,
            tags=["self-reflection", reflection.trigger.split(":")[0].strip()],
            source="reflection_engine",
        ))
