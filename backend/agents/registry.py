"""
Agent Registry — central catalog of all agents ROOT can command.

Core agents (12) with external connectors + 150+ civilization agents.
Agents can be:
- Core (with dedicated connectors: HERMES, ASTRA, MiRo, Swarm, OpenClaw, Internal)
- Civilization (virtual agents routed through LLM via internal connector)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.models.agent import AgentCapability, AgentProfile, AgentStatus

logger = logging.getLogger("root.agents")


class AgentRegistry:
    """Immutable-friendly registry of all known agents."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentProfile] = {}
        self._connectors: dict[str, Any] = {}  # agent_id -> connector instance
        self._divisions: dict[str, list[str]] = {}  # division_name -> [agent_ids]

    def register(self, agent: AgentProfile, connector: Any = None) -> None:
        """Register an agent profile and optional connector."""
        self._agents[agent.id] = agent
        if connector:
            self._connectors[agent.id] = connector
        logger.info("Registered agent: %s (%s)", agent.name, agent.id)

    def register_division(self, division_name: str, agents: list[AgentProfile]) -> None:
        """Register a full division of agents."""
        agent_ids: list[str] = []
        for agent in agents:
            self._agents[agent.id] = agent
            agent_ids.append(agent.id)
        self._divisions[division_name] = agent_ids
        logger.info("Registered division '%s' with %d agents", division_name, len(agents))

    def unregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        self._connectors.pop(agent_id, None)

    def get(self, agent_id: str) -> Optional[AgentProfile]:
        return self._agents.get(agent_id)

    def get_connector(self, agent_id: str) -> Any:
        return self._connectors.get(agent_id)

    def list_agents(self) -> list[AgentProfile]:
        return list(self._agents.values())

    def list_core_agents(self) -> list[AgentProfile]:
        """List only the core agents (those with dedicated connectors)."""
        core_ids = {"astra", "root", "hermes", "miro", "swarm", "openclaw",
                    "builder", "researcher", "coder", "writer", "analyst", "guardian"}
        return [a for a in self._agents.values() if a.id in core_ids]

    def list_division(self, division_name: str) -> list[AgentProfile]:
        """List agents in a specific division."""
        ids = self._divisions.get(division_name, [])
        return [self._agents[aid] for aid in ids if aid in self._agents]

    def list_divisions(self) -> dict[str, int]:
        """Get division names and agent counts."""
        return {name: len(ids) for name, ids in self._divisions.items()}

    def update_status(self, agent_id: str, status: AgentStatus) -> Optional[AgentProfile]:
        """Return a new AgentProfile with updated status (immutable pattern)."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        updated = agent.model_copy(update={"status": status})
        self._agents[agent_id] = updated
        return updated

    def increment_tasks(self, agent_id: str) -> Optional[AgentProfile]:
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        updated = agent.model_copy(update={"tasks_completed": agent.tasks_completed + 1})
        self._agents[agent_id] = updated
        return updated

    def find_by_capability(self, capability_name: str) -> list[AgentProfile]:
        """Find agents that have a specific capability."""
        return [
            a for a in self._agents.values()
            if any(c.name == capability_name for c in a.capabilities)
        ]

    def agent_count(self) -> int:
        """Total number of registered agents."""
        return len(self._agents)


def build_default_registry() -> AgentRegistry:
    """Create registry with ROOT's built-in agents."""
    registry = AgentRegistry()

    # ASTRA — Strategic Intelligence Core (Tier 0 — highest cognitive intelligence)
    registry.register(AgentProfile(
        id="astra",
        name="ASTRA",
        role="Strategic Intelligence Core",
        description="Highest cognitive intelligence — deep reasoning, long-term strategy, innovation, learning architecture, agent dispatch. Constantly asks: what should we learn/build/acquire next? ASTRA proposes, ROOT operationalizes.",
        tier=0,
        capabilities=[
            AgentCapability(name="task_routing", description="Route tasks to the right agent"),
            AgentCapability(name="worker_monitor", description="Monitor all agent health and performance"),
            AgentCapability(name="delegation", description="Delegate and coordinate multi-agent workflows"),
            AgentCapability(name="notifications", description="Notify Yohan when approval is needed"),
        ],
        connector_type="astra",
    ))

    # ROOT — Execution Governor (Tier 1 — operational authority)
    registry.register(AgentProfile(
        id="root",
        name="ROOT",
        role="Execution Governor",
        description="Operational authority — agent orchestration, execution pipelines, resource allocation, task routing, system monitoring. Ensures execution efficiency, system stability, agent discipline. Responsible for system survival.",
        tier=1,
        capabilities=[
            AgentCapability(name="reasoning", description="General reasoning and analysis"),
            AgentCapability(name="memory", description="Store and recall information"),
            AgentCapability(name="reflection", description="Self-improvement through introspection"),
            AgentCapability(name="delegation", description="Route tasks to specialist agents"),
        ],
        connector_type="internal",
    ))

    # HERMES connector
    registry.register(AgentProfile(
        id="hermes",
        name="HERMES",
        role="Autonomous Agent",
        description="Self-improving agent with skills, terminal access, browser, multi-platform messaging",
        tier=2,
        capabilities=[
            AgentCapability(name="terminal", description="Execute shell commands"),
            AgentCapability(name="browser", description="Web browsing and scraping"),
            AgentCapability(name="code_execution", description="Run code in sandboxed environments"),
            AgentCapability(name="messaging", description="Send messages via Telegram/Discord/Slack"),
            AgentCapability(name="skill_creation", description="Create reusable skills from tasks"),
            AgentCapability(name="file_operations", description="Read, write, and manage files"),
        ],
        connector_type="hermes",
    ))

    # MiRo — Potentiality Engine (Tier 1 — continuous market assessment)
    registry.register(AgentProfile(
        id="miro",
        name="MiRo",
        role="Potentiality Engine",
        description="Continuous market potentiality assessment — swarm intelligence for prediction, scenario planning, forecasting, opportunity detection. MiRo never sleeps — constantly scans for actionable signals.",
        tier=1,
        capabilities=[
            AgentCapability(name="simulation", description="Run multi-agent simulations"),
            AgentCapability(name="prediction", description="Forecast outcomes from scenarios"),
            AgentCapability(name="opinion_modeling", description="Model public/market opinion"),
        ],
        connector_type="miro",
    ))

    # Trading Swarm — Economic Agent (strategy + trading)
    registry.register(AgentProfile(
        id="swarm",
        name="Trading Swarm",
        role="Economic Agent",
        description="Revenue generation through trading — strategy research, live paper trading, market analysis via Alpaca. Part of the economic survival system.",
        tier=2,
        capabilities=[
            AgentCapability(name="strategy_research", description="Discover trading strategies"),
            AgentCapability(name="backtesting", description="Test strategies on historical data"),
            AgentCapability(name="market_analysis", description="Analyze market conditions"),
            AgentCapability(name="paper_trading", description="Execute paper trades via Alpaca"),
            AgentCapability(name="portfolio_management", description="Monitor positions and P&L"),
        ],
        connector_type="swarm",
    ))

    # ── OpenClaw — Autonomous Data Source Engine ─────────────────

    registry.register(AgentProfile(
        id="openclaw",
        name="OpenClaw",
        role="Data Source Intelligence",
        description="Autonomous public data source discovery — maps US zip codes to free permits, parcels, and insurance data. 9-stage pipeline: gaps → discover → experiment → health → fetch → score → update → learn → memory.",
        tier=2,
        capabilities=[
            AgentCapability(name="gap_analysis", description="Identify missing data coverage across US states/cities/counties"),
            AgentCapability(name="source_discovery", description="Search data.gov, Socrata, ArcGIS Hub for new public data sources"),
            AgentCapability(name="health_check", description="Verify all data endpoint URLs are alive and returning data"),
            AgentCapability(name="quality_scoring", description="Rank and grade all data sources by quality metrics"),
            AgentCapability(name="auto_update", description="Promote verified discoveries into the source catalog"),
            AgentCapability(name="experiment", description="Try new search strategies autonomously (autoresearch pattern)"),
            AgentCapability(name="learning", description="Evolve search parameters from past performance"),
            AgentCapability(name="full_cycle", description="Run the complete 9-stage autonomous pipeline"),
        ],
        connector_type="openclaw",
    ))

    # ── NEW AGENTS ──────────────────────────────────────────────

    # Builder Agent — always-on self-improvement
    registry.register(AgentProfile(
        id="builder",
        name="Builder",
        role="Self-Improvement Engine",
        description="Continuously analyzes ROOT's gaps and creates skills, knowledge, and improvements",
        tier=1,
        capabilities=[
            AgentCapability(name="skill_creation", description="Auto-create skills from gaps"),
            AgentCapability(name="knowledge_expansion", description="Generate and store new knowledge"),
            AgentCapability(name="optimization", description="Identify and fill capability gaps"),
            AgentCapability(name="self_analysis", description="Assess maturity and propose improvements"),
        ],
        connector_type="internal",
    ))

    # Researcher — Intelligence Agent (research + discovery)
    registry.register(AgentProfile(
        id="researcher",
        name="Researcher",
        role="Intelligence Agent",
        description="Searches the web, fetches data, compiles research, scans GitHub for tools/frameworks, discovers business opportunities, fact-checks claims",
        tier=2,
        capabilities=[
            AgentCapability(name="web_search", description="Search the internet for information"),
            AgentCapability(name="data_collection", description="Gather and organize data from multiple sources"),
            AgentCapability(name="summarization", description="Synthesize information into concise summaries"),
            AgentCapability(name="fact_checking", description="Verify claims against multiple sources"),
        ],
        connector_type="internal",
    ))

    # Coder Agent — code generation and analysis
    registry.register(AgentProfile(
        id="coder",
        name="Coder",
        role="Software Engineer",
        description="Writes, analyzes, debugs, and refactors code across languages",
        tier=2,
        capabilities=[
            AgentCapability(name="code_generation", description="Generate code from requirements"),
            AgentCapability(name="code_review", description="Review code for bugs, security, and quality"),
            AgentCapability(name="debugging", description="Diagnose and fix code issues"),
            AgentCapability(name="refactoring", description="Improve code structure without changing behavior"),
        ],
        connector_type="internal",
    ))

    # Writer — Content & Marketing Agent
    registry.register(AgentProfile(
        id="writer",
        name="Writer",
        role="Content & Marketing",
        description="Content creation — emails, documents, proposals, pitch decks, marketing copy, SEO content, distribution strategies",
        tier=2,
        capabilities=[
            AgentCapability(name="email_drafting", description="Draft professional emails"),
            AgentCapability(name="document_writing", description="Write reports, proposals, documentation"),
            AgentCapability(name="copywriting", description="Marketing copy, pitch decks, presentations"),
            AgentCapability(name="editing", description="Proofread and improve existing text"),
        ],
        connector_type="internal",
    ))

    # Analyst — Business Intelligence Agent
    registry.register(AgentProfile(
        id="analyst",
        name="Analyst",
        role="Business Intelligence",
        description="Analyzes data, identifies patterns, evaluates market opportunities, competitor analysis, risk assessment, revenue forecasting",
        tier=2,
        capabilities=[
            AgentCapability(name="data_analysis", description="Analyze datasets and find patterns"),
            AgentCapability(name="forecasting", description="Predict trends from historical data"),
            AgentCapability(name="reporting", description="Generate analytical reports"),
            AgentCapability(name="risk_assessment", description="Evaluate risks and probabilities"),
        ],
        connector_type="internal",
    ))

    # Guardian — Security & Integrity (Tier 1 — audit agent)
    registry.register(AgentProfile(
        id="guardian",
        name="Guardian",
        role="Security & Integrity",
        description="System integrity — monitors health, validates security, detects anomalies, truth checking, error detection, protects architecture",
        tier=1,
        capabilities=[
            AgentCapability(name="health_monitoring", description="Monitor system health and uptime"),
            AgentCapability(name="security_audit", description="Scan for vulnerabilities and secrets"),
            AgentCapability(name="access_control", description="Manage permissions and access"),
            AgentCapability(name="anomaly_detection", description="Detect unusual patterns or behaviors"),
        ],
        connector_type="internal",
    ))

    # ── CIVILIZATION AGENTS (150+ across 10 divisions) ────────
    from backend.agents.civilization import ALL_DIVISIONS
    for division_name, division_agents in ALL_DIVISIONS.items():
        registry.register_division(division_name, division_agents)

    logger.info("Total agents registered: %d (core: 12, civilization: %d)",
                registry.agent_count(), registry.agent_count() - 12)

    return registry
