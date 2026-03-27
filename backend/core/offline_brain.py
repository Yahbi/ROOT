"""
Offline Brain — ROOT's intelligence when no API key is available.

Uses local memory, skills, and pattern matching to respond.
No external API calls. Pure local intelligence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.core.memory_engine import MemoryEngine
from backend.core.skill_engine import SkillEngine
from backend.core.context_manager import ContextManager
from backend.core.self_dev import SelfDevEngine
from backend.models.agent import ChatMessage
from backend.models.memory import MemoryEntry, MemoryQuery, MemoryType

logger = logging.getLogger("root.offline")


class OfflineBrain:
    """Local-only brain that works without any API key.

    Uses memory retrieval, skill matching, and self-assessment
    to provide useful responses from ROOT's knowledge base.
    """

    def __init__(
        self,
        memory: MemoryEngine,
        skills: SkillEngine,
        self_dev: SelfDevEngine,
        context: ContextManager,
        money_engine: Optional[object] = None,
    ) -> None:
        self._memory = memory
        self._skills = skills
        self._self_dev = self_dev
        self._context = context
        self._money = money_engine
        self._conversation: list[dict[str, str]] = []
        self._interaction_count = 0

    async def chat(self, user_message: str) -> ChatMessage:
        """Process a message using local knowledge only."""
        self._interaction_count += 1
        self._conversation.append({"role": "user", "content": user_message})

        # 1. Search memory for relevant knowledge
        memories = self._memory.search(MemoryQuery(query=user_message, limit=10))

        # 2. Search skills for relevant procedures
        relevant_skills = self._skills.search(user_message, limit=3)

        # 3. Build response from local knowledge
        response = self._build_response(user_message, memories, relevant_skills)

        # Handle Strategy Council trigger
        if response == "council_trigger" and self._money:
            session = await self._money.convene_council(focus=user_message)
            response = self._format_council_session(session)

        self._conversation.append({"role": "assistant", "content": response})

        return ChatMessage(
            role="assistant",
            content=response,
            agent_id="root_offline",
            memories_used=[m.id for m in memories if m.id],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def chat_stream(self, user_message: str):
        """Simulate streaming for offline mode (yields complete response)."""
        result = await self.chat(user_message)
        yield result.content

    async def remember(self, content: str, memory_type: str = "fact", tags: Optional[list[str]] = None) -> MemoryEntry:
        """Store something in memory (works offline)."""
        try:
            mt = MemoryType(memory_type)
        except ValueError:
            mt = MemoryType.FACT
        entry = MemoryEntry(
            content=content,
            memory_type=mt,
            tags=tags or [],
            source="yohan_direct",
            confidence=1.0,
        )
        return self._memory.store(entry)

    async def delegate(self, agent_id: str, task: str) -> dict:
        """Delegation not available offline."""
        return {
            "error": "Delegation requires API connection. ROOT is running in offline mode.",
            "suggestion": "Set ANTHROPIC_API_KEY in .env to enable agent delegation.",
        }

    def get_conversation(self) -> list[dict[str, str]]:
        return list(self._conversation)

    def clear_conversation(self) -> None:
        self._conversation.clear()

    def _build_response(
        self,
        query: str,
        memories: list[MemoryEntry],
        skills: list,
    ) -> str:
        """Build a response from local knowledge."""
        parts = []

        # Check for special commands
        query_lower = query.lower().strip()

        if query_lower in ("status", "how are you", "what's your status"):
            return self._status_response()

        if query_lower.startswith("remember "):
            content = query[9:].strip()
            if content:
                self._memory.store(MemoryEntry(
                    content=content,
                    memory_type=MemoryType.FACT,
                    tags=["user-told"],
                    source="yohan_direct",
                ))
                return f"Stored in memory: {content}"

        if query_lower in ("assess", "self-assess", "how evolved are you"):
            assessment = self._self_dev.assess()
            return self._format_assessment(assessment)

        if query_lower in ("skills", "list skills", "what can you do"):
            return self._skills_response()

        if query_lower in ("memories", "what do you know", "knowledge"):
            return self._knowledge_response()

        if query_lower in ("gaps", "what are you missing"):
            gaps = self._self_dev.identify_gaps()
            return self._format_gaps(gaps)

        # Money / Strategy Council commands
        money_triggers = (
            "make money", "money", "council", "strategy council",
            "opportunities", "how to make money", "revenue",
            "make yohan money", "wealth",
        )
        if query_lower in money_triggers or "make money" in query_lower:
            return "council_trigger"  # Sentinel — handled in chat()

        # Default: search memory and skills for relevant info
        if memories:
            parts.append("**From my memory:**")
            for m in memories[:5]:
                conf = f" (confidence: {m.confidence:.0%})" if m.confidence < 1.0 else ""
                parts.append(f"- [{m.memory_type.value}] {m.content}{conf}")

        if skills:
            parts.append("\n**Relevant skills:**")
            for s in skills[:3]:
                parts.append(f"- **{s.category}/{s.name}**: {s.description}")

        if not memories and not skills:
            parts.append(
                "I'm running in offline mode (no API key). I can:\n"
                "- Search my **memory** for stored knowledge\n"
                "- Match your request to **skills** I've learned\n"
                "- Show my **status** and self-assessment\n"
                "- **Remember** things you tell me\n"
                "- Identify **gaps** in my knowledge\n\n"
                "To enable full reasoning, set `ANTHROPIC_API_KEY` in `.env`."
            )
        else:
            parts.append(
                "\n*Running in offline mode — responses are from stored knowledge. "
                "Set ANTHROPIC_API_KEY for full AI reasoning.*"
            )

        return "\n".join(parts)

    def _status_response(self) -> str:
        mem_stats = self._memory.stats()
        skill_stats = self._skills.stats()
        assessment = self._self_dev.assess()
        return (
            f"**ROOT Status — Offline Mode**\n\n"
            f"Maturity: **{assessment['maturity_level']}** ({assessment['maturity_score']:.0%})\n"
            f"Memories: **{mem_stats.get('total', 0)}** entries\n"
            f"Skills: **{skill_stats.get('total', 0)}** across {len(skill_stats.get('categories', {}))} categories\n"
            f"Evolutions: **{assessment.get('evolution_count', 0)}** logged\n"
            f"Gaps: **{len(assessment.get('capability_gaps', []))}** identified\n"
            f"Interactions this session: **{self._interaction_count}**\n\n"
            f"*Set ANTHROPIC_API_KEY to unlock full reasoning, reflection, and agent delegation.*"
        )

    def _skills_response(self) -> str:
        categories = self._skills.list_categories()
        if not categories:
            return "No skills loaded yet."
        parts = ["**ROOT Skill Library**\n"]
        for cat, skills in sorted(categories.items()):
            parts.append(f"\n**{cat}/**")
            for s in skills:
                tags = f" `{', '.join(s.tags)}`" if s.tags else ""
                parts.append(f"  - {s.name}: {s.description}{tags}")
        parts.append(f"\n**Total: {sum(len(s) for s in categories.values())} skills**")
        return "\n".join(parts)

    def _knowledge_response(self) -> str:
        stats = self._memory.stats()
        recent = self._memory.get_recent(limit=10)
        parts = [f"**ROOT Knowledge Base — {stats.get('total', 0)} memories**\n"]
        by_type = stats.get("by_type", {})
        for mt, info in sorted(by_type.items()):
            parts.append(f"- {mt}: {info['count']} (avg confidence: {info['avg_confidence']:.0%})")
        if recent:
            parts.append("\n**Recent memories:**")
            for m in recent[:5]:
                parts.append(f"- [{m.memory_type.value}] {m.content[:120]}...")
        return "\n".join(parts)

    def _format_assessment(self, assessment: dict) -> str:
        parts = [
            f"**ROOT Self-Assessment**\n",
            f"Maturity: **{assessment['maturity_level']}** ({assessment['maturity_score']:.0%})\n",
            f"Memories: {assessment['memories'].get('total', 0)}",
            f"Skills: {assessment['skills'].get('total', 0)}",
            f"Evolutions: {assessment['evolution_count']}",
        ]
        if assessment.get("capability_gaps"):
            parts.append(f"\n**{len(assessment['capability_gaps'])} capability gaps identified:**")
            for gap in assessment["capability_gaps"][:5]:
                parts.append(f"- {gap['description']} → {gap['suggestion']}")
        if assessment.get("recent_evolution"):
            parts.append("\n**Recent evolution:**")
            for ev in assessment["recent_evolution"]:
                parts.append(f"- [{ev['type']}] {ev['desc']}")
        return "\n".join(parts)

    def _format_council_session(self, session) -> str:
        """Format Strategy Council results for display."""
        parts = [
            f"**Strategy Council — {session.total_opportunities} Opportunities Identified**\n",
            f"Agents consulted: {', '.join(session.agents_consulted)}",
            f"Session: {session.id} ({session.session_duration_seconds:.1f}s)\n",
        ]

        if session.top_recommendation:
            top = session.top_recommendation
            parts.append(f"**Top Recommendation: {top.title}**")
            parts.append(f"Confidence: **{top.confidence_score:.0%}** | Risk: {top.risk_level.value}")
            if top.estimated_monthly_revenue:
                parts.append(f"Est. revenue: **${top.estimated_monthly_revenue:,.0f}/mo**")
            parts.append(f"\n{top.description}\n")

        parts.append("---\n**All Opportunities (ranked by confidence):**\n")
        for i, opp in enumerate(session.opportunities, 1):
            revenue = f"${opp.estimated_monthly_revenue:,.0f}/mo" if opp.estimated_monthly_revenue else "TBD"
            capital = f"${opp.capital_required:,.0f}" if opp.capital_required > 0 else "Free"
            parts.append(
                f"{i}. **{opp.title}** — {opp.confidence_score:.0%} confidence\n"
                f"   Type: {opp.opportunity_type.value} | Risk: {opp.risk_level.value} | "
                f"Revenue: {revenue} | Capital: {capital}\n"
                f"   Agents: {', '.join(opp.agent_sources)}"
            )
            if opp.action_steps:
                parts.append(f"   Next step: {opp.action_steps[0]}")
            parts.append("")

        parts.append(
            "*Strategy Council runs in offline mode using stored knowledge. "
            "Set ANTHROPIC_API_KEY for real-time agent collaboration and LLM-powered analysis.*"
        )
        return "\n".join(parts)

    def _format_gaps(self, gaps: list[dict]) -> str:
        if not gaps:
            return "No capability gaps identified. ROOT is well-rounded."
        parts = [f"**{len(gaps)} Capability Gaps Identified**\n"]
        for gap in gaps:
            parts.append(f"- **{gap['area']}**: {gap['description']}")
            parts.append(f"  → {gap['suggestion']}")
        return "\n".join(parts)
