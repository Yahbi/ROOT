"""Money Engine — Multi-agent Strategy Council for wealth generation."""

from __future__ import annotations

import json, logging, uuid
from dataclasses import dataclass, field, replace as dc_replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from backend.core.memory_engine import MemoryEngine
from backend.core.skill_engine import SkillEngine
from backend.core.self_dev import SelfDevEngine
from backend.models.memory import MemoryEntry, MemoryQuery, MemoryType

logger = logging.getLogger("root.money")


class OpportunityType(str, Enum):
    TRADING = "trading"
    AUTOMATION = "automation"
    SaaS = "saas"
    FREELANCE = "freelance"
    ARBITRAGE = "arbitrage"
    REAL_ESTATE = "real_estate"
    AI_PRODUCT = "ai_product"
    DATA_PRODUCT = "data_product"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class Opportunity:
    """Immutable money-making opportunity identified by the council."""
    id: str
    title: str
    description: str
    opportunity_type: OpportunityType
    risk_level: RiskLevel
    confidence_score: float  # 0.0 - 1.0
    estimated_monthly_revenue: Optional[float] = None
    time_to_first_revenue_days: Optional[int] = None
    capital_required: float = 0.0
    agent_sources: list[str] = field(default_factory=list)
    action_steps: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CouncilSession:
    """Immutable record of a Strategy Council session."""
    id: str
    opportunities: list[Opportunity]
    agents_consulted: list[str]
    total_opportunities: int
    top_recommendation: Optional[Opportunity]
    session_duration_seconds: float
    mode: str  # "offline" or "online"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Agent domain config ──────────────────────────────────────

AGENT_DOMAINS: dict[str, dict[str, list[str]]] = {
    "swarm":  {"tags": ["trading", "strategy", "backtest", "market", "crypto", "stocks", "roi"],
               "skills": ["trading", "strategy", "backtest", "market"]},
    "miro":   {"tags": ["simulation", "prediction", "forecast", "scenario", "swarm", "opinion"],
               "skills": ["simulation", "prediction", "scenario", "forecast"]},
    "hermes": {"tags": ["research", "web", "scraping", "data", "automation", "code", "tool"],
               "skills": ["research", "automation", "browser", "scraping"]},
    "astra":  {"tags": ["orchestration", "workflow", "agent", "worker", "coordination"],
               "skills": ["orchestration", "routing", "delegation"]},
    "root":   {"tags": ["money", "revenue", "income", "business", "profit", "saas", "product"],
               "skills": ["learning", "improvement", "pattern"]},
}

_AGENT_PROMPT = (
    "Analyze current market conditions and identify the single best money-making "
    "opportunity for Yohan. Consider: trading, SaaS, data products, consulting, "
    "automation. Return a JSON object with keys: title, description, "
    "type (trading|automation|saas|freelance|arbitrage|real_estate|ai_product|data_product), "
    "risk (low|medium|high|very_high), confidence (0-1), estimated_monthly_revenue, "
    "time_to_first_revenue_days, capital_required, action_steps (list)."
)
_SYNTHESIS_SYSTEM = (
    "You are the ROOT Strategy Council synthesizer. Produce 3-5 scored opportunities "
    "as a JSON array. Keys: title, description, type, risk, confidence, "
    "estimated_monthly_revenue, time_to_first_revenue_days, capital_required, "
    "action_steps, agent_sources, tags. Only output valid JSON."
)
_VALID_TYPES = {t.value for t in OpportunityType}
_VALID_RISKS = {r.value for r in RiskLevel}

# Per-cluster metadata: keywords for grouping, opp_type, title, desc prefix, action steps
_CLUSTER_META: dict[str, dict[str, Any]] = {
    "trading":    {"kw": ["trading", "strategy", "backtest", "market", "crypto", "stocks"],
                   "type": OpportunityType.TRADING,
                   "title": "Autonomous Trading Strategy Execution",
                   "prefix": "Based on trading intelligence",
                   "steps": ["Validate with paper trading", "Set risk limits", "Deploy with monitoring"]},
    "automation": {"kw": ["automation", "workflow", "scraping", "browser", "code"],
                   "type": OpportunityType.AUTOMATION,
                   "title": "Workflow Automation Service",
                   "prefix": "Based on automation capabilities",
                   "steps": ["Identify highest-value workflow", "Build pipeline", "Package for clients"]},
    "data":       {"kw": ["data", "api", "permit", "leads", "scraping", "enrichment"],
                   "type": OpportunityType.DATA_PRODUCT,
                   "title": "Data Intelligence API Product",
                   "prefix": "Based on data pipeline assets",
                   "steps": ["Deploy API with auth", "Automate data refresh", "Launch tiered pricing"]},
    "ai_product": {"kw": ["agent", "ai", "saas", "product", "orchestration"],
                   "type": OpportunityType.AI_PRODUCT,
                   "title": "AI Agent Platform",
                   "prefix": "Based on AI agent architecture",
                   "steps": ["Package as API/SaaS", "Add billing", "Launch free tier"]},
    "consulting": {"kw": ["consulting", "freelance", "expert", "revenue", "income"],
                   "type": OpportunityType.FREELANCE,
                   "title": "AI Systems Consulting",
                   "prefix": "Based on demonstrated expertise",
                   "steps": ["Build portfolio", "List on platforms", "Offer discovery calls"]},
    "research":   {"kw": ["research", "prediction", "simulation", "forecast", "analysis"],
                   "type": OpportunityType.SaaS,
                   "title": "Predictive Analytics Service",
                   "prefix": "Based on analytical capabilities",
                   "steps": ["Validate models", "Build prediction API", "Monetize via subscription"]},
}
_RISK_MAP: dict[OpportunityType, RiskLevel] = {
    OpportunityType.TRADING: RiskLevel.HIGH, OpportunityType.ARBITRAGE: RiskLevel.HIGH,
    OpportunityType.FREELANCE: RiskLevel.LOW, OpportunityType.DATA_PRODUCT: RiskLevel.LOW,
    OpportunityType.AUTOMATION: RiskLevel.MEDIUM, OpportunityType.SaaS: RiskLevel.MEDIUM,
    OpportunityType.AI_PRODUCT: RiskLevel.MEDIUM, OpportunityType.REAL_ESTATE: RiskLevel.HIGH,
}
# revenue_base, time_to_revenue_days, capital_required  — keyed by OpportunityType
_OPP_ECONOMICS: dict[OpportunityType, tuple[int, int, int]] = {
    OpportunityType.TRADING: (5000, 7, 5000), OpportunityType.SaaS: (8000, 30, 500),
    OpportunityType.DATA_PRODUCT: (6000, 14, 200), OpportunityType.AI_PRODUCT: (10000, 30, 1000),
    OpportunityType.FREELANCE: (12000, 7, 0), OpportunityType.AUTOMATION: (7000, 14, 200),
    OpportunityType.ARBITRAGE: (3000, 14, 2000), OpportunityType.REAL_ESTATE: (4000, 90, 50000),
}


class MoneyEngine:
    """Strategy Council — multi-agent collaboration for wealth generation."""

    def __init__(
        self,
        memory: MemoryEngine,
        skills: SkillEngine,
        self_dev: SelfDevEngine,
        registry: Any = None,
        orchestrator: Any = None,
        llm: Any = None,
        collab: Any = None,
        bus: Any = None,
    ) -> None:
        self._memory = memory
        self._skills = skills
        self._self_dev = self_dev
        self._registry = registry
        self._orchestrator = orchestrator
        self._llm = llm
        self._collab = collab
        self._bus = bus
        self._sandbox_gate = None  # Set via main.py
        self._notification_engine = None  # Set via main.py
        self._sessions: list[CouncilSession] = []

    # ── Public API ──────────────────────────────────────────────

    async def convene_council(self, focus: Optional[str] = None) -> CouncilSession:
        """Run an offline Strategy Council session (memory + skills only)."""
        return await self._run_session(focus, mode="offline")

    async def convene_council_online(self, focus: Optional[str] = None) -> CouncilSession:
        """Run an online Strategy Council — LLM + multi-agent fanout.

        Falls back to offline council if LLM or collab is unavailable.
        """
        if self._sandbox_gate is not None:
            decision = self._sandbox_gate.check(
                system_id="revenue", action="council_online",
                description=f"Online Strategy Council (focus: {focus or 'general'})",
                agent_id="money_engine", risk_level="medium",
            )
            if not decision.was_executed:
                logger.info("Sandbox blocked online council, falling back to offline")
                return await self.convene_council(focus=focus)
        if not self._collab or not self._llm:
            logger.warning("Online council unavailable, falling back to offline")
            return await self.convene_council(focus=focus)
        return await self._run_session(focus, mode="online")

    def get_sessions(self, limit: int = 20) -> list[CouncilSession]:
        return list(reversed(self._sessions[-limit:]))

    def get_latest_opportunities(self, limit: int = 10) -> list[Opportunity]:
        if not self._sessions:
            return []
        return self._sessions[-1].opportunities[:limit]

    def get_opportunity(self, opp_id: str) -> Optional[Opportunity]:
        for session in reversed(self._sessions):
            for opp in session.opportunities:
                if opp.id == opp_id:
                    return opp
        return None

    def stats(self) -> dict:
        all_opps = [o for s in self._sessions for o in s.opportunities]
        return {
            "total_sessions": len(self._sessions),
            "total_opportunities": len(all_opps),
            "avg_confidence": (
                sum(o.confidence_score for o in all_opps) / len(all_opps)
                if all_opps else 0.0
            ),
            "opportunity_types": list(set(o.opportunity_type.value for o in all_opps)),
            "total_estimated_monthly": sum(o.estimated_monthly_revenue or 0 for o in all_opps),
        }

    # ── Core Session Runner ─────────────────────────────────────

    async def _run_session(self, focus: Optional[str], mode: str) -> CouncilSession:
        session_id = f"council_{uuid.uuid4().hex[:12]}"
        start = datetime.now(timezone.utc)
        logger.info("Strategy Council (%s): %s (focus: %s)", mode, session_id, focus or "general")

        agent_insights, agent_skills = self._gather_intelligence(focus)
        agents_consulted = list(AGENT_DOMAINS.keys())

        if mode == "online":
            opportunities, agents_consulted = await self._online_deliberation(
                agent_insights, agent_skills, focus,
            )
        else:
            opportunities = self._generate_from_intelligence(agent_insights, agent_skills, focus)

        ranked = sorted(opportunities, key=lambda o: o.confidence_score, reverse=True)
        self._store_top_opportunities(ranked)
        self._log_evolution(agent_insights, ranked)

        end = datetime.now(timezone.utc)
        session = CouncilSession(
            id=session_id, opportunities=ranked, agents_consulted=agents_consulted,
            total_opportunities=len(ranked),
            top_recommendation=ranked[0] if ranked else None,
            session_duration_seconds=round((end - start).total_seconds(), 2),
            mode=mode, created_at=start.isoformat(),
        )
        self._sessions = [*self._sessions, session]
        logger.info("Council %s done: %d opps in %.1fs", session_id, len(ranked),
                    session.session_duration_seconds)
        return session

    async def _online_deliberation(
        self,
        agent_insights: dict[str, list[MemoryEntry]],
        agent_skills: dict[str, list],
        focus: Optional[str],
    ) -> tuple[list[Opportunity], list[str]]:
        """Fan out to agents + synthesize via LLM. Falls back on failure."""
        agents_consulted = ["swarm", "miro", "researcher", "root"]
        try:
            task_prompt = f"Focus area: {focus}\n\n{_AGENT_PROMPT}" if focus else _AGENT_PROMPT
            workflow = await self._collab.fanout(
                initiator="root",
                goal="Strategy Council: identify best money-making opportunities",
                agents=["swarm", "miro", "researcher"],
                task=task_prompt,
            )
            agent_responses = [step.result for step in workflow.steps if step.result]
        except Exception as exc:
            logger.error("Fanout failed: %s", exc)
            return self._generate_from_intelligence(agent_insights, agent_skills, focus), list(AGENT_DOMAINS.keys())
        try:
            opps = await self._synthesize_opportunities_llm(agent_responses, agent_insights, focus)
            return opps, agents_consulted
        except Exception as exc:
            logger.error("LLM synthesis failed: %s", exc)
            return self._generate_from_intelligence(agent_insights, agent_skills, focus), agents_consulted

    def _gather_intelligence(self, focus: Optional[str] = None,
    ) -> tuple[dict[str, list[MemoryEntry]], dict[str, list]]:
        """Search memory and skills for each agent domain."""
        agent_insights: dict[str, list[MemoryEntry]] = {}
        agent_skills: dict[str, list] = {}
        for agent_id, domain in AGENT_DOMAINS.items():
            raw: list[MemoryEntry] = []
            for tag in domain["tags"]:
                raw.extend(self._memory.search(MemoryQuery(
                    query=f"{tag} {focus}" if focus else tag, limit=5)))
            seen: set[str] = set()
            unique = [seen.add(m.content[:100]) or m  # type: ignore[func-returns-value]
                      for m in raw if m.content[:100] not in seen]
            agent_insights[agent_id] = unique[:10]
            ds: list = []
            for kw in domain["skills"]:
                ds.extend(self._skills.search(kw, limit=2))
            agent_skills[agent_id] = ds[:5]
        return agent_insights, agent_skills

    # ── LLM-Powered Synthesis ───────────────────────────────────

    async def _synthesize_opportunities_llm(
        self, agent_responses: list[str],
        insights: dict[str, list[MemoryEntry]], focus: Optional[str],
    ) -> list[Opportunity]:
        memory_summary = self._summarize_insights(insights)
        user_msg = (
            f"Agent analyses:\n\n"
            + "\n\n---\n\n".join(agent_responses[:5])
            + f"\n\nMemory insights:\n{memory_summary}"
        )
        if focus:
            user_msg = f"Focus: {focus}\n\n{user_msg}"

        raw = await self._llm.complete(
            messages=[{"role": "user", "content": user_msg}],
            system=_SYNTHESIS_SYSTEM, model_tier="default",
            max_tokens=3000, temperature=0.5,
        )
        return self._parse_opportunities_json(raw)

    # ── Intelligence-Based Generation ───────────────────────────

    def _generate_from_intelligence(
        self, insights: dict[str, list[MemoryEntry]],
        skills: dict[str, list], focus: Optional[str],
    ) -> list[Opportunity]:
        """Generate opportunities from actual memory content."""
        opps: list[Opportunity] = []
        clusters = self._cluster_insights(insights)

        for cluster_name, cluster_entries in clusters.items():
            if not cluster_entries:
                continue

            avg_conf = sum(e.confidence for e in cluster_entries) / len(cluster_entries)
            evidence_strength = min(1.0, len(cluster_entries) / 10.0)
            confidence = round(min(0.95, avg_conf * 0.6 + evidence_strength * 0.4), 2)

            meta = _CLUSTER_META.get(cluster_name, {})
            opp_type = meta.get("type", OpportunityType.SaaS)
            risk = _RISK_MAP.get(opp_type, RiskLevel.MEDIUM)
            rev_base, time_days, capital = _OPP_ECONOMICS.get(opp_type, (5000, 30, 500))

            all_tags: set[str] = set()
            for entry in cluster_entries:
                all_tags.update(getattr(entry, "tags", []) or [])

            snippets = [e.content[:100] for e in cluster_entries[:3]]
            prefix = meta.get("prefix", "Based on stored knowledge")

            opp = Opportunity(
                id=f"opp_{uuid.uuid4().hex[:8]}",
                title=meta.get("title", f"{opp_type.value.replace('_', ' ').title()} Opportunity"),
                description=f"{prefix}: {'; '.join(snippets)}",
                opportunity_type=opp_type, risk_level=risk,
                confidence_score=confidence,
                estimated_monthly_revenue=round(rev_base * confidence, -2),
                time_to_first_revenue_days=time_days,
                capital_required=float(capital),
                agent_sources=list({
                    agent for agent, entries in insights.items()
                    if any(e in cluster_entries for e in entries)
                }),
                action_steps=meta.get("steps", ["Research market", "Build MVP", "Launch and iterate"]),
                supporting_evidence=[e.content[:150] for e in cluster_entries[:3]],
                tags=list(all_tags)[:8],
            )
            opps.append(opp)

        if focus:
            opps = self._apply_focus_boost(opps, focus)
        return opps[:5]

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _cluster_insights(
        insights: dict[str, list[MemoryEntry]],
    ) -> dict[str, list[MemoryEntry]]:
        """Group memory entries into topic clusters."""
        all_entries: list[MemoryEntry] = []
        for entries in insights.values():
            all_entries.extend(entries)

        seen: set[str] = set()
        unique: list[MemoryEntry] = []
        for e in all_entries:
            key = e.content[:80]
            if key not in seen:
                seen.add(key)
                unique.append(e)

        topic_map: dict[str, list[MemoryEntry]] = {}
        for entry in unique:
            content_lower = entry.content.lower()
            entry_tags = {t.lower() for t in (getattr(entry, "tags", []) or [])}
            best_bucket, best_score = "research", 0

            for bucket, meta in _CLUSTER_META.items():
                keywords = meta["kw"]
                score = sum(1 for kw in keywords if kw in content_lower or kw in entry_tags)
                if score > best_score:
                    best_score = score
                    best_bucket = bucket

            topic_map[best_bucket] = [*topic_map.get(best_bucket, []), entry]
        return topic_map

    @staticmethod
    def _apply_focus_boost(opps: list[Opportunity], focus: str) -> list[Opportunity]:
        fl = focus.lower()
        def _matches(o: Opportunity) -> bool:
            return any(fl in t or fl in o.title.lower() or fl in o.description.lower()
                       for t in o.tags)
        return [
            dc_replace(o, confidence_score=min(1.0, o.confidence_score + 0.05))
            if _matches(o) else o for o in opps
        ]

    @staticmethod
    def _parse_opportunities_json(raw: str) -> list[Opportunity]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM JSON: %s", raw[:200])
            return []

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []

        opps: list[Opportunity] = []
        for item in data[:5]:
            if not isinstance(item, dict):
                continue
            try:
                opp_type_raw = str(item.get("type", "saas")).lower()
                risk_raw = str(item.get("risk", "medium")).lower()
                opps.append(Opportunity(
                    id=f"opp_{uuid.uuid4().hex[:8]}",
                    title=str(item.get("title", "Untitled"))[:200],
                    description=str(item.get("description", ""))[:500],
                    opportunity_type=OpportunityType(
                        opp_type_raw if opp_type_raw in _VALID_TYPES else "saas"),
                    risk_level=RiskLevel(risk_raw if risk_raw in _VALID_RISKS else "medium"),
                    confidence_score=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                    estimated_monthly_revenue=float(item.get("estimated_monthly_revenue", 0)),
                    time_to_first_revenue_days=int(item.get("time_to_first_revenue_days", 30)),
                    capital_required=float(item.get("capital_required", 0)),
                    agent_sources=list(item.get("agent_sources", ["llm"])),
                    action_steps=list(item.get("action_steps", [])),
                    supporting_evidence=list(item.get("supporting_evidence", [])),
                    tags=list(item.get("tags", [])),
                ))
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning("Skipping malformed opportunity: %s", exc)
        return opps

    @staticmethod
    def _summarize_insights(insights: dict[str, list[MemoryEntry]]) -> str:
        parts: list[str] = []
        for agent_id, entries in insights.items():
            if entries:
                snippets = [e.content[:100] for e in entries[:3]]
                parts.append(f"[{agent_id}]: {'; '.join(snippets)}")
        return "\n".join(parts) if parts else "No stored intelligence available."

    def _store_top_opportunities(self, ranked: list[Opportunity]) -> None:
        for opp in ranked[:3]:
            self._memory.store(MemoryEntry(
                content=(
                    f"Opportunity identified: {opp.title} — {opp.description} "
                    f"(confidence: {opp.confidence_score:.0%}, "
                    f"risk: {opp.risk_level.value}, "
                    f"est. revenue: ${opp.estimated_monthly_revenue or 0:,.0f}/mo)"
                ),
                memory_type=MemoryType.GOAL,
                tags=["opportunity", opp.opportunity_type.value, opp.risk_level.value],
                source="strategy_council",
                confidence=opp.confidence_score,
            ))

    def _log_evolution(self, agent_insights: dict[str, list[MemoryEntry]],
                       ranked: list[Opportunity]) -> None:
        self._self_dev.propose_improvement(
            area="money_strategy",
            description=(
                f"Strategy Council identified {len(ranked)} opportunities "
                f"(top: {ranked[0].title if ranked else 'none'})"
            ),
            rationale=(
                f"Consulted {len(agent_insights)} agent domains, "
                f"analyzed {sum(len(v) for v in agent_insights.values())} entries"
            ),
        )
