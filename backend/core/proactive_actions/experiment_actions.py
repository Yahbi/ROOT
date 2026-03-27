"""Experiment proposing, revenue seeding, experiment running, code scanning, and revenue tracking."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("root.proactive.experiment")


async def experiment_proposer(
    *,
    experiment_lab: Any = None,
    collab: Any = None,
    llm: Any = None,
    memory: Any = None,
) -> str:
    """Auto-propose experiments from market scans, business discoveries, and agent insights."""
    if not experiment_lab:
        return "requires experiment_lab"

    # Check if we already have too many running experiments
    stats = experiment_lab.stats()
    running = stats.get("by_status", {}).get("running", 0)
    proposed = stats.get("by_status", {}).get("proposed", 0)
    if running >= 5 or proposed >= 10:
        return f"Experiment backlog full: {running} running, {proposed} proposed"

    if not llm:
        return "requires LLM for experiment generation"

    # Gather context from recent memory observations
    context_parts: list[str] = []
    if memory:
        from backend.models.memory import MemoryQuery, MemoryType
        recent = memory.search(
            MemoryQuery(query="opportunity market discovery business", limit=10)
        )
        for m in recent[:5]:
            context_parts.append(m.content[:200])

    context = "\n".join(context_parts) if context_parts else "No recent insights available."

    prompt = (
        "Based on the following recent intelligence, propose 2-3 concrete experiments "
        "that ROOT should run. Each experiment should test a specific hypothesis about "
        "revenue generation, trading strategy, or system optimization.\n\n"
        f"Recent intelligence:\n{context}\n\n"
        "For each experiment, provide:\n"
        "1. title (short)\n"
        "2. hypothesis (what we're testing)\n"
        "3. category (one of: saas, marketing, pricing, trading, automation, content, agent_config, infrastructure)\n"
        "4. design (how to test it)\n"
        "5. success_criteria (what constitutes success)\n\n"
        "Respond as JSON array. Focus on experiments that can be validated within 1-7 days."
    )

    try:
        response = await llm.complete(
            system="You are ROOT's experiment designer. Propose practical, testable experiments.",
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            max_tokens=1000,
            method="proactive",
        )

        import json as _json
        raw = response.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        experiments = _json.loads(raw)
        if not isinstance(experiments, list):
            return "LLM returned non-list response"

        created = 0
        for exp in experiments[:3]:
            title = str(exp.get("title", ""))
            hypothesis = str(exp.get("hypothesis", ""))
            category = str(exp.get("category", "agent_config"))
            if not title or not hypothesis:
                continue

            valid_categories = {
                "saas", "marketing", "pricing", "trading",
                "automation", "content", "agent_config", "infrastructure",
            }
            if category not in valid_categories:
                category = "agent_config"

            experiment_lab.propose(
                title=title,
                hypothesis=hypothesis,
                category=category,
                design=str(exp.get("design", ""))[:500],
                success_criteria=str(exp.get("success_criteria", ""))[:300],
                confidence=0.6,
                created_by="experiment_proposer",
            )
            created += 1

        return f"Experiment proposer: created {created} new experiments"

    except Exception as exc:
        logger.error("Experiment proposer failed: %s", exc)
        return f"Experiment proposer failed: {exc}"


async def seed_revenue_products(
    *,
    revenue_engine: Any = None,
    ecosystem: Any = None,
) -> str:
    """Ensure revenue engine is seeded with real products from project ecosystem."""
    if not revenue_engine:
        return "requires revenue_engine"

    # Check if already seeded
    try:
        products = revenue_engine.get_products()
        if len(products) > 0:
            return f"Revenue already seeded: {len(products)} products"
    except Exception as e:
        logger.warning("Revenue product check failed: %s — will attempt seed", e)

    # Seed with Yohan's real projects
    products = [
        ("Onsite Lead Platform", "data_products",
         "Production lead gen — PropertyReach + ATTOM enrichment, "
         "real estate leads with contact data. Active platform.", 50.0),
        ("US Permit Data API", "data_products",
         "1.2GB aggregated US construction permit data by ZIP code. "
         "Ready to monetize as API or dataset product.", 10.0),
        ("OI-Astra Trading Bot", "automation_agency",
         "13-agent autonomous trading command center — "
         "Robinhood, Polymarket, TradingView. Revenue via trading profits.", 30.0),
        ("AI Automation Services", "ai_consulting",
         "ROOT-powered automation consulting — build custom AI workflows "
         "for businesses using ROOT's agent orchestration.", 0.0),
        ("OpenClaw Data Discovery", "data_products",
         "9-stage public data source discovery service. "
         "Can be offered as SaaS tool for data teams.", 5.0),
    ]

    created = 0
    for name, stream, desc, cost in products:
        try:
            revenue_engine.add_product(
                name=name, stream=stream, description=desc, monthly_cost=cost,
            )
            created += 1
        except Exception as exc:
            logger.warning("Failed to seed product '%s': %s", name, exc)

    return f"Revenue seeded: {created} products from project ecosystem"


async def run_experiments(
    *,
    experiment_lab: Any = None,
    llm: Any = None,
    memory: Any = None,
    collab: Any = None,
) -> str:
    """Autonomous experiment lifecycle: start proposed -> evaluate running -> learn from results."""
    if not experiment_lab:
        return "requires experiment_lab"

    actions_taken: list[str] = []

    # Phase 1: Start top proposed experiments (max 2 per cycle)
    proposed = experiment_lab.get_proposed(limit=5)
    started = 0
    for exp in proposed:
        if started >= 2:
            break
        # Only start experiments with reasonable confidence
        if exp.confidence >= 0.4 and exp.design:
            experiment_lab.start_experiment(exp.id)
            started += 1
            actions_taken.append(f"started '{exp.title}'")

    # Phase 2: Evaluate running experiments using LLM
    running = experiment_lab.get_running(limit=5)
    evaluated = 0

    if running and llm:
        for exp in running[:3]:
            # Check if experiment has been running long enough (>2 hours)
            from datetime import datetime as _dt, timezone as _tz
            try:
                created = _dt.fromisoformat(exp.created_at.replace("Z", "+00:00"))
                age_hours = (
                    _dt.now(_tz.utc) - created
                ).total_seconds() / 3600
                if age_hours < 2:
                    continue
            except Exception:
                pass

            # Use LLM to evaluate the experiment
            eval_prompt = (
                f"Evaluate this experiment and determine if it should be marked "
                f"as completed (success or failure).\n\n"
                f"Title: {exp.title}\n"
                f"Hypothesis: {exp.hypothesis}\n"
                f"Category: {exp.category.value}\n"
                f"Design: {exp.design}\n"
                f"Success criteria: {exp.success_criteria}\n"
                f"Running for: {age_hours:.1f} hours\n\n"
                f"Based on the design and time elapsed, provide:\n"
                f"1. verdict: 'success', 'failure', or 'continue' (if more time needed)\n"
                f"2. result: summary of findings\n"
                f"3. lesson: key insight learned\n\n"
                f"Respond as JSON: {{\"verdict\": ..., \"result\": ..., \"lesson\": ...}}"
            )

            try:
                response = await llm.complete(
                    system="You are ROOT's experiment evaluator. Be honest and data-driven.",
                    messages=[{"role": "user", "content": eval_prompt}],
                    model_tier="fast",
                    max_tokens=500,
                    method="proactive",
                )

                import json as _json
                raw = response.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

                evaluation = _json.loads(raw)
                verdict = str(evaluation.get("verdict", "continue")).lower()

                if verdict in ("success", "failure"):
                    experiment_lab.complete_experiment(
                        experiment_id=exp.id,
                        result=str(evaluation.get("result", ""))[:500],
                        lesson_learned=str(evaluation.get("lesson", ""))[:300],
                        success=(verdict == "success"),
                    )
                    evaluated += 1
                    actions_taken.append(
                        f"evaluated '{exp.title}' -> {verdict}"
                    )
            except Exception as exc:
                logger.debug("Experiment evaluation failed for %s: %s", exp.id, exc)

    # Phase 3: Auto-scale successful experiments
    completed = experiment_lab.get_completed(limit=10)
    scaled = 0
    for exp in completed:
        if exp.status.value == "completed" and exp.confidence >= 0.7:
            experiment_lab.scale_experiment(exp.id)
            scaled += 1
            actions_taken.append(f"scaled '{exp.title}'")
            if scaled >= 2:
                break

    # Store summary to memory
    if memory and actions_taken:
        from backend.models.memory import MemoryEntry, MemoryType
        memory.store(MemoryEntry(
            content=f"Experiment runner: {'; '.join(actions_taken)}",
            memory_type=MemoryType.OBSERVATION,
            tags=["experiments", "autonomous", "lifecycle"],
            source="experiment_runner",
            confidence=0.8,
        ))

    summary = (
        f"Experiment runner: {started} started, {evaluated} evaluated, "
        f"{scaled} scaled"
    )
    if actions_taken:
        summary += f" -- {'; '.join(actions_taken)}"
    return summary


async def scan_code_improvements(
    *,
    self_writing_code: Any = None,
    llm: Any = None,
    memory: Any = None,
) -> str:
    """Scan codebase for inefficiencies and propose self-improvement code changes."""
    if not self_writing_code:
        return "requires self_writing_code engine"

    # Check existing proposal backlog
    try:
        stats = self_writing_code.stats()
        pending = stats.get("by_status", {}).get("proposed", 0)
        if pending >= 5:
            return f"Code improvement backlog full: {pending} pending proposals"
    except Exception:
        pass

    if not llm:
        return "requires LLM for code analysis"

    # Gather context about recent issues, errors, and patterns
    context_parts: list[str] = []
    if memory:
        from backend.models.memory import MemoryQuery, MemoryType
        recent_errors = memory.search(
            MemoryQuery(query="error bug issue performance slow", limit=5)
        )
        for m in recent_errors:
            context_parts.append(m.content[:200])

    context = "\n".join(context_parts) if context_parts else "No recent issues found."

    prompt = (
        "Analyze ROOT's recent issues and patterns. Propose 1-2 specific code "
        "improvements that would increase system reliability or performance.\n\n"
        f"Recent system observations:\n{context}\n\n"
        "For each proposal, provide:\n"
        "1. title: short description\n"
        "2. area: which module/file to improve\n"
        "3. description: what to change and why\n"
        "4. impact: expected improvement\n"
        "5. risk: low/medium/high\n\n"
        "Respond as JSON array. Focus on practical, testable improvements."
    )

    try:
        response = await llm.complete(
            system="You are ROOT's self-improvement engineer. Propose precise code changes.",
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            max_tokens=800,
            method="proactive",
        )

        import json as _json
        raw = response.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        proposals = _json.loads(raw)
        if not isinstance(proposals, list):
            return "LLM returned non-list response"

        created = 0
        for prop in proposals[:2]:
            title = str(prop.get("title", ""))
            description = str(prop.get("description", ""))
            if not title or not description:
                continue

            try:
                self_writing_code.propose_improvement(
                    title=title,
                    description=description,
                    file_path=str(prop.get("area", "backend/core/")),
                    inefficiency=str(prop.get("impact", ""))[:200],
                    proposed_change=description[:300],
                    scope="minor" if str(prop.get("risk", "low")) == "low" else "major",
                    agent_id="code_scanner",
                )
                created += 1
            except Exception as exc:
                logger.debug("Failed to create code proposal: %s", exc)

        return f"Code scanner: {created} improvement proposals created"

    except Exception as exc:
        logger.error("Code scanner failed: %s", exc)
        return f"Code scanner failed: {exc}"


async def track_revenue_health(
    *,
    revenue_engine: Any = None,
    ecosystem: Any = None,
    memory: Any = None,
) -> str:
    """Monitor project revenue health, flag risks, and identify growth opportunities."""
    if not revenue_engine:
        return "requires revenue_engine"

    findings: list[str] = []

    # Check revenue snapshot
    try:
        snapshot = revenue_engine.get_snapshot()
        total_products = snapshot.get("total_products", 0)
        monthly_revenue = snapshot.get("monthly_revenue", 0)
        monthly_costs = snapshot.get("monthly_costs", 0)
        emergency = snapshot.get("emergency_mode", False)

        findings.append(
            f"Revenue: ${monthly_revenue:,.0f}/mo, "
            f"Costs: ${monthly_costs:,.0f}/mo, "
            f"Products: {total_products}"
        )

        if emergency:
            findings.append("ALERT: Emergency mode active — below $400/mo survival threshold")
        elif monthly_revenue < 1000:
            findings.append("WARNING: Revenue below $1K/mo — needs acceleration")

    except Exception as exc:
        findings.append(f"Revenue snapshot unavailable: {exc}")

    # Cross-reference with ecosystem for growth opportunities
    if ecosystem:
        try:
            summary = ecosystem.get_ecosystem_summary()
            by_stream = summary.get("by_revenue_stream", {})
            underserved = [
                stream for stream, projects in by_stream.items()
                if len(projects) <= 1
            ]
            if underserved:
                findings.append(
                    f"Growth opportunity: underserved revenue streams: "
                    f"{', '.join(underserved)}"
                )
        except Exception:
            pass

    # Store revenue health to memory
    if memory and findings:
        from backend.models.memory import MemoryEntry, MemoryType
        memory.store(MemoryEntry(
            content=f"Revenue health: {'; '.join(findings)}",
            memory_type=MemoryType.OBSERVATION,
            tags=["revenue", "health", "tracking", "economics"],
            source="revenue_tracker",
            confidence=0.85,
        ))

    return f"Revenue tracker: {'; '.join(findings)}"
