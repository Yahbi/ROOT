"""
Proactive action handlers — standalone async functions for ProactiveEngine.

Each handler receives the engine's dependencies as explicit parameters
rather than accessing them via `self`, keeping them decoupled and testable.

This package re-exports all public functions from sub-modules so that
existing imports like `from backend.core.proactive_actions import check_health`
continue to work unchanged.
"""

from backend.core.proactive_actions.health_actions import (
    check_health,
    consolidate_knowledge,
    survival_economics,
    check_approval_timeouts,
    auto_recover_goals,
    auto_remediate_revenue,
)

from backend.core.proactive_actions.research_actions import (
    scan_opportunities,
    discover_skills,
    scan_github,
    scan_markets,
    miro_predict,
    miro_continuous_assess,
    data_intelligence,
    business_discovery,
    scan_project_ecosystem,
    correlate_projects,
)

from backend.core.proactive_actions.execution_actions import (
    evolve_agents,
    self_rewrite,
    drain_task_queue,
    auto_trade_cycle,
    assess_goals,
    track_goals,
    validate_strategies,
)

from backend.core.proactive_actions.experiment_actions import (
    experiment_proposer,
    seed_revenue_products,
    run_experiments,
    scan_code_improvements,
    track_revenue_health,
)

from backend.core.proactive_actions.intelligence_actions import (
    miro_world_intelligence,
    miro_daily_briefing,
)

from backend.core.proactive_actions.polymarket_actions import (
    scan_polymarkets,
    polymarket_trade_cycle,
    monitor_polymarket_positions,
)

__all__ = [
    # health_actions
    "check_health",
    "consolidate_knowledge",
    "survival_economics",
    "check_approval_timeouts",
    "auto_recover_goals",
    "auto_remediate_revenue",
    # research_actions
    "scan_opportunities",
    "discover_skills",
    "scan_github",
    "scan_markets",
    "miro_predict",
    "miro_continuous_assess",
    "data_intelligence",
    "business_discovery",
    "scan_project_ecosystem",
    "correlate_projects",
    # execution_actions
    "evolve_agents",
    "self_rewrite",
    "drain_task_queue",
    "auto_trade_cycle",
    "assess_goals",
    "track_goals",
    "validate_strategies",
    # experiment_actions
    "experiment_proposer",
    "seed_revenue_products",
    "run_experiments",
    "scan_code_improvements",
    "track_revenue_health",
    # intelligence_actions
    "miro_world_intelligence",
    "miro_daily_briefing",
    # polymarket_actions
    "scan_polymarkets",
    "polymarket_trade_cycle",
    "monitor_polymarket_positions",
]
