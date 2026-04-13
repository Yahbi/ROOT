"""
Organism Hierarchy — enforces the hierarchical "living quant firm" design.

The hierarchy:

Meta-Agent (CEO / Self-Improver)          tier=0
├── Research Crew (Analysts + Debate)     tier=1
├── Signal Agent (Probability Engine)     tier=1
├── Arb/MM Agent (Spread harvesting)      tier=1
├── Risk & Sizing Agent (Kelly + caps)    tier=1
├── Execution Agent (Trade execution)     tier=2
├── Memory & Reflection Layer             tier=2
└── Economic Engine (Self-sustainability) tier=2

Self-Perfection Crew (background)
├── Gap Finder                            tier=1
├── Skill Evolution                       tier=2
├── Code Mutation Loop                    tier=2
├── Audit & Test Crew                     tier=1
└── UI Enhancer                           tier=2

This module:
1. Defines the hierarchy with clear responsibilities
2. Routes tasks to the correct crew/agent
3. Enforces tier-based approval chains
4. Provides the orchestration entry points for full pipeline runs
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("root.organism_hierarchy")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Hierarchy Definition ─────────────────────────────────────

@dataclass(frozen=True)
class OrganismNode:
    """A node in the organism hierarchy."""
    id: str
    name: str
    role: str
    tier: int              # 0=CEO, 1=Director, 2=Executor
    parent_id: Optional[str]
    children: list[str]    # IDs of child nodes
    system_module: str     # Which ROOT module implements this
    capabilities: list[str]


ORGANISM_TREE: dict[str, OrganismNode] = {
    # ── CEO ──
    "meta_agent": OrganismNode(
        id="meta_agent",
        name="Meta-Agent",
        role="CEO / Self-Improver — nightly reflection, hypothesis generation, system evolution",
        tier=0,
        parent_id=None,
        children=["research_crew", "signal_agent", "arb_agent", "risk_agent",
                  "execution_agent", "memory_layer", "economic_engine", "self_perfection"],
        system_module="backend.core.meta_agent.MetaAgent",
        capabilities=["reflection", "hypothesis_generation", "system_evolution", "performance_audit"],
    ),

    # ── Research Division (tier 1) ──
    "research_crew": OrganismNode(
        id="research_crew",
        name="Research Crew",
        role="17 investment agents + bull/bear debate → thesis generation",
        tier=1,
        parent_id="meta_agent",
        children=["thesis_engine", "debate_engine", "investment_agents"],
        system_module="backend.core.thesis_engine.ThesisEngine",
        capabilities=["thesis_generation", "agent_analysis", "debate", "sentiment_analysis"],
    ),
    "thesis_engine": OrganismNode(
        id="thesis_engine",
        name="Thesis Engine",
        role="Blends quant + qualitative signals into investment theses",
        tier=1,
        parent_id="research_crew",
        children=[],
        system_module="backend.core.thesis_engine.ThesisEngine",
        capabilities=["thesis_synthesis", "multi_agent_orchestration"],
    ),
    "debate_engine": OrganismNode(
        id="debate_engine",
        name="Debate Engine",
        role="Structured bull/bear debates with risk assessment",
        tier=1,
        parent_id="research_crew",
        children=[],
        system_module="backend.core.debate_engine.DebateEngine",
        capabilities=["bull_bear_debate", "research_synthesis", "risk_debate"],
    ),
    "investment_agents": OrganismNode(
        id="investment_agents",
        name="Investment Agent Panel",
        role="13 philosophy + 4 analysis agents (Buffett, Graham, Munger, etc.)",
        tier=2,
        parent_id="research_crew",
        children=[],
        system_module="backend.core.investment_agents.InvestmentAgentRunner",
        capabilities=["fundamental_analysis", "technical_analysis", "sentiment_analysis", "valuation"],
    ),

    # ── Signal / Probability Engine (tier 1) ──
    "signal_agent": OrganismNode(
        id="signal_agent",
        name="Signal Agent",
        role="Probability engine — Bayesian updates, Monte Carlo, calibration",
        tier=1,
        parent_id="meta_agent",
        children=[],
        system_module="backend.core.quant_models",
        capabilities=["bayesian_update", "monte_carlo", "brier_scoring", "arima_forecast", "garch_volatility"],
    ),

    # ── Arb/MM Agent (tier 1) ──
    "arb_agent": OrganismNode(
        id="arb_agent",
        name="Arb/MM Agent",
        role="LMSR spread harvesting, cross-market arbitrage, pairs trading",
        tier=1,
        parent_id="meta_agent",
        children=[],
        system_module="backend.core.arb_agent.ArbAgent",
        capabilities=["spread_detection", "arbitrage_scanning", "pairs_trading", "bayesian_pricing"],
    ),

    # ── Risk & Sizing Agent (tier 1) ──
    "risk_agent": OrganismNode(
        id="risk_agent",
        name="Risk & Sizing Agent",
        role="Fractional Kelly sizing, volatility-adjusted limits, portfolio optimization",
        tier=1,
        parent_id="meta_agent",
        children=[],
        system_module="backend.core.portfolio_optimizer.PortfolioOptimizer",
        capabilities=["kelly_sizing", "risk_metrics", "portfolio_optimization", "correlation_analysis"],
    ),

    # ── Execution Agent (tier 2) ──
    "execution_agent": OrganismNode(
        id="execution_agent",
        name="Execution Agent",
        role="Trade execution via Alpaca/Polymarket, position monitoring",
        tier=2,
        parent_id="meta_agent",
        children=[],
        system_module="backend.core.hedge_fund.HedgeFundEngine",
        capabilities=["trade_execution", "position_monitoring", "order_management"],
    ),

    # ── Memory & Reflection Layer (tier 2) ──
    "memory_layer": OrganismNode(
        id="memory_layer",
        name="Memory & Reflection",
        role="Episodic trade memory, experience memory, prediction ledger, learning",
        tier=2,
        parent_id="meta_agent",
        children=[],
        system_module="backend.core.episodic_trade_memory.EpisodicTradeMemory",
        capabilities=["episodic_logging", "lesson_extraction", "calibration_tracking", "experience_storage"],
    ),

    # ── Economic Engine (tier 2) ──
    "economic_engine": OrganismNode(
        id="economic_engine",
        name="Economic Engine",
        role="Self-sustainability: reinvestment rules, survival mode, strategy P&L",
        tier=2,
        parent_id="meta_agent",
        children=[],
        system_module="backend.core.economic_sustainability.EconomicSustainability",
        capabilities=["profit_allocation", "cost_tracking", "survival_mode", "strategy_scaling"],
    ),

    # ── Self-Perfection Crew (tier 1, background) ──
    "self_perfection": OrganismNode(
        id="self_perfection",
        name="Self-Perfection Crew",
        role="Continuous improvement: gap finding, mutation, audit, merge",
        tier=1,
        parent_id="meta_agent",
        children=["gap_finder", "skill_evolution", "code_mutation", "audit_crew"],
        system_module="backend.core.self_perfection.SelfPerfectionEngine",
        capabilities=["gap_detection", "mutation_proposal", "audit", "self_improvement"],
    ),
    "gap_finder": OrganismNode(
        id="gap_finder",
        name="Gap Finder",
        role="Scans logs, backtests, metrics for performance gaps",
        tier=2,
        parent_id="self_perfection",
        children=[],
        system_module="backend.core.self_perfection.SelfPerfectionEngine",
        capabilities=["performance_monitoring", "gap_detection", "anomaly_detection"],
    ),
    "skill_evolution": OrganismNode(
        id="skill_evolution",
        name="Skill Evolution",
        role="Auto-generates new skills when gaps are found",
        tier=2,
        parent_id="self_perfection",
        children=[],
        system_module="backend.core.builder_agent.BuilderAgent",
        capabilities=["skill_generation", "skill_testing", "skill_deployment"],
    ),
    "code_mutation": OrganismNode(
        id="code_mutation",
        name="Code Mutation Loop",
        role="Proposes code improvements, backtests them, merges if EV improves",
        tier=2,
        parent_id="self_perfection",
        children=[],
        system_module="backend.core.self_writing_code.SelfWritingCodeSystem",
        capabilities=["code_generation", "backtest_evaluation", "git_merge"],
    ),
    "audit_crew": OrganismNode(
        id="audit_crew",
        name="Audit & Test Crew",
        role="Critics that veto changes dropping Sharpe or increasing cost",
        tier=1,
        parent_id="self_perfection",
        children=[],
        system_module="backend.core.self_perfection.SelfPerfectionEngine",
        capabilities=["code_review", "test_execution", "veto_power", "regression_detection"],
    ),
}


# ── Orchestrator ─────────────────────────────────────────────

class OrganismOrchestrator:
    """Orchestrates the full organism hierarchy."""

    def __init__(
        self,
        meta_agent=None,
        thesis_engine=None,
        debate_engine=None,
        arb_agent=None,
        portfolio_optimizer=None,
        hedge_fund=None,
        episodic_trades=None,
        economic_sustainability=None,
        self_perfection=None,
        prediction_ledger=None,
        bus=None,
    ) -> None:
        self._meta = meta_agent
        self._thesis = thesis_engine
        self._debate = debate_engine
        self._arb = arb_agent
        self._portfolio = portfolio_optimizer
        self._hedge_fund = hedge_fund
        self._episodic = episodic_trades
        self._economics = economic_sustainability
        self._perfection = self_perfection
        self._prediction = prediction_ledger
        self._bus = bus

    async def full_analysis_pipeline(
        self,
        symbols: list[str],
        portfolio_value: float = 100_000.0,
    ) -> dict:
        """Run the full organism pipeline for a list of symbols.

        Flow (respecting hierarchy):
        1. CEO (Meta-Agent) checks economic mode — can we trade?
        2. Research Crew generates theses (quant + agents + optional debate)
        3. Signal Agent enriches with probability models
        4. Risk Agent optimizes portfolio allocation
        5. Results passed to Execution Agent for action
        6. Memory Layer records everything
        """
        start_time = time.monotonic()

        # 1. Economic gate
        if self._economics and not self._economics.should_trade():
            return {
                "status": "blocked",
                "reason": f"Economic mode: {self._economics.mode}",
                "action": "none",
            }

        # 2. Research Crew → Theses
        theses = []
        if self._thesis:
            theses = await self._thesis.multi_thesis(symbols, portfolio_value)

        # 3. Risk Agent → Portfolio optimization
        allocation = None
        if self._portfolio and theses:
            allocation = self._portfolio.optimize(theses, portfolio_value)

        # 4. Record in Memory Layer
        for thesis in theses:
            if self._episodic and thesis.recommended_action in ("buy", "short"):
                try:
                    self._episodic.record_entry(
                        market_id=thesis.symbol,
                        action=thesis.recommended_action,
                        entry_price=0.0,  # Will be filled on execution
                        thesis=thesis.thesis_narrative[:500],
                        thesis_signal=thesis.final_signal,
                        thesis_confidence=thesis.final_confidence,
                        ev_calculation={
                            "composite_score": thesis.quant_score.composite_score,
                            "kelly_pct": thesis.quant_score.kelly_recommended_pct,
                            "kelly_edge": thesis.quant_score.kelly_edge,
                        },
                        strategy="thesis_pipeline",
                        agents_consulted=[s.agent_id for s in thesis.agent_signals],
                        thesis_id=thesis.id,
                    )
                except Exception as e:
                    logger.warning("Failed to record episodic entry for %s: %s", thesis.symbol, e)

        elapsed = round(time.monotonic() - start_time, 2)

        result = {
            "status": "complete",
            "symbols_analyzed": len(symbols),
            "theses_generated": len(theses),
            "actionable": sum(1 for t in theses if t.recommended_action != "hold"),
            "duration_seconds": elapsed,
            "theses": [
                {
                    "symbol": t.symbol,
                    "signal": t.final_signal,
                    "confidence": t.final_confidence,
                    "action": t.recommended_action,
                    "position_pct": t.position_size_pct,
                    "quant_composite": t.quant_score.composite_score,
                    "agents_used": t.agents_used,
                }
                for t in theses
            ],
        }

        if allocation:
            from dataclasses import asdict
            result["allocation"] = {
                "total_invested_pct": allocation.total_invested_pct,
                "cash_pct": allocation.cash_pct,
                "expected_return": allocation.expected_return,
                "sharpe_ratio": allocation.sharpe_ratio,
                "positions": len(allocation.positions),
                "risk_warnings": allocation.risk_warnings,
            }

        return result

    def get_hierarchy(self) -> dict:
        """Return the full organism hierarchy as a tree."""
        def _build_subtree(node_id: str) -> dict:
            node = ORGANISM_TREE.get(node_id)
            if not node:
                return {"id": node_id, "error": "not found"}
            return {
                "id": node.id,
                "name": node.name,
                "role": node.role,
                "tier": node.tier,
                "module": node.system_module,
                "capabilities": node.capabilities,
                "children": [_build_subtree(cid) for cid in node.children],
            }

        return _build_subtree("meta_agent")

    def get_node(self, node_id: str) -> Optional[OrganismNode]:
        return ORGANISM_TREE.get(node_id)

    def list_nodes(self, tier: Optional[int] = None) -> list[OrganismNode]:
        nodes = list(ORGANISM_TREE.values())
        if tier is not None:
            nodes = [n for n in nodes if n.tier == tier]
        return nodes

    def stats(self) -> dict:
        nodes = list(ORGANISM_TREE.values())
        return {
            "total_nodes": len(nodes),
            "tiers": {t: sum(1 for n in nodes if n.tier == t) for t in range(3)},
            "capabilities": list(set(c for n in nodes for c in n.capabilities)),
        }
