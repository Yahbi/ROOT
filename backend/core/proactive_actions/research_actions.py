"""Research, scanning, discovery, and intelligence-gathering actions."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("root.proactive.research")


async def scan_opportunities(
    *,
    collab: Any = None,
    llm: Any = None,
) -> str:
    """Scan for opportunities aligned with Yohan's interests."""
    if not collab or not llm:
        return "requires LLM + collaboration"

    result = await collab.delegate(
        from_agent="proactive_engine",
        to_agent="researcher",
        task=(
            "Briefly scan for new opportunities relevant to Yohan's interests: "
            "AI development, trading strategies, real estate data, automation. "
            "Keep it concise — just list top 3 most interesting recent developments."
        ),
    )
    return result.final_result or "scan complete"


async def discover_skills(
    *,
    self_dev: Any = None,
    memory: Any = None,
) -> str:
    """Create skills from successful interaction patterns."""
    if not self_dev or not memory:
        return "no self-dev or memory engine"

    from backend.models.memory import MemoryQuery, MemoryType
    learnings = memory.search(
        MemoryQuery(query="skill pattern procedure", memory_type=MemoryType.LEARNING, limit=10)
    )

    if not learnings:
        assessment = self_dev.assess()
        skills_count = assessment.get("skills", {}).get("total", 0)
        return f"Skills: {skills_count} active — no new patterns found"

    # Propose skill creation for strong learnings
    proposed = 0
    for m in learnings:
        if m.confidence >= 0.7 and m.access_count >= 2:
            self_dev.propose_improvement(
                area="skills",
                description=f"Create skill from learning: {m.content[:200]}",
                rationale="High-confidence, frequently-accessed learning pattern",
            )
            proposed += 1
            if proposed >= 2:
                break

    return f"Skill discovery: {proposed} proposals from {len(learnings)} learnings"


async def scan_github(
    *,
    collab: Any = None,
    llm: Any = None,
    memory: Any = None,
) -> str:
    """Scan GitHub for trending repos, AI breakthroughs, useful tools."""
    if not collab or not llm:
        return "requires LLM + collaboration"

    result = await collab.delegate(
        from_agent="proactive_engine",
        to_agent="researcher",
        task=(
            "Search GitHub and the web for the latest trending AI repositories, "
            "breakthroughs, and tools that could benefit Yohan's projects. Focus on: "
            "1) New agent frameworks or tools, 2) Trading/finance AI projects, "
            "3) Local LLM inference improvements, 4) Automation tools. "
            "List top 3 most relevant finds with GitHub URLs if possible. Be concise."
        ),
    )

    # Store findings
    if result.final_result and memory:
        from backend.models.memory import MemoryEntry, MemoryType
        entry = MemoryEntry(
            content=f"GitHub scan: {result.final_result[:300]}",
            memory_type=MemoryType.OBSERVATION,
            tags=["github", "research", "proactive"],
            source="github_scanner",
            confidence=0.7,
        )
        memory.store(entry)

    return result.final_result or "GitHub scan complete"


async def scan_markets(
    *,
    collab: Any = None,
    llm: Any = None,
    memory: Any = None,
    hedge_fund: Any = None,
    market_data: Any = None,
) -> str:
    """Scan markets via Trading Swarm agent + AGI trading intelligence pipeline."""
    if not collab or not llm:
        return "requires LLM + collaboration"

    parts: list[str] = []

    # ── Phase 1: Swarm agent web-based market scan ─────────────
    result = await collab.delegate(
        from_agent="proactive_engine",
        to_agent="swarm",
        task=(
            "Quick market pulse check. Search for current conditions on major indices "
            "(SPY, QQQ, BTC). Report: 1) Current price levels and daily change, "
            "2) Any major news or catalysts today, 3) Any trading opportunities. "
            "Keep it brief — 5 sentences max."
        ),
    )
    swarm_intel = result.final_result or ""
    if swarm_intel:
        parts.append(swarm_intel)

    # ── Phase 2: Real technical analysis via MarketDataService ──
    if market_data:
        import json as _json
        for symbol in ("SPY", "QQQ", "BTC-USD"):
            try:
                analysis = await market_data.get_full_analysis(symbol)
                if analysis and "error" not in analysis:
                    quote = analysis.get("quote", {})
                    indicators = analysis.get("indicators", {})
                    price = quote.get("current_price", "N/A")
                    change_pct = quote.get("change_percent", "N/A")
                    rsi = indicators.get("rsi_14", "N/A")
                    macd = indicators.get("macd", {})
                    macd_signal = macd.get("signal", "") if isinstance(macd, dict) else ""
                    parts.append(
                        f"[{symbol}] ${price} ({change_pct}%) RSI={rsi}"
                        + (f" MACD-signal={macd_signal}" if macd_signal else "")
                    )
            except Exception as ta_exc:
                logger.debug("Technical analysis failed for %s: %s", symbol, ta_exc)

    # ── Phase 3: Hedge fund trading intelligence cycle ──────────
    if hedge_fund:
        try:
            cycle_result = await hedge_fund.run_cycle()
            if cycle_result:
                import json as _json2
                trades = cycle_result.get("trades_executed", 0)
                signals = cycle_result.get("signals_generated", 0)
                parts.append(
                    f"Trading cycle: {signals} signals, {trades} trades"
                )
                if cycle_result.get("portfolio"):
                    portfolio = cycle_result["portfolio"]
                    equity = portfolio.get("equity", "N/A")
                    parts.append(f"Portfolio equity: ${equity}")
        except Exception as hf_exc:
            logger.debug("Hedge fund cycle in market scan failed: %s", hf_exc)

    combined = " | ".join(parts) if parts else "market scan complete"

    # Store market intelligence in memory
    if combined and memory:
        from backend.models.memory import MemoryEntry, MemoryType
        entry = MemoryEntry(
            content=f"Market scan: {combined[:500]}",
            memory_type=MemoryType.OBSERVATION,
            tags=["market", "trading", "proactive", "technical_analysis"],
            source="market_scanner",
            confidence=0.8,
        )
        memory.store(entry)

    return combined[:500]


async def miro_predict(
    *,
    collab: Any = None,
    llm: Any = None,
    memory: Any = None,
    notification_engine: Any = None,
) -> str:
    """MiRo market prediction: extract data, project potentiality, recommend next moves."""
    if not collab or not llm:
        return "requires LLM + collaboration"

    result = await collab.pipeline(
        initiator="proactive_engine",
        goal="Market prediction and potentiality projection",
        steps=[
            {
                "agent_id": "miro",
                "task": (
                    "Run market prediction scan. Search for current prices on SPY, QQQ, "
                    "BTC-USD, ETH-USD. Find today's key news, earnings, and macro events. "
                    "Run your Bull/Bear/Quant/Contrarian/Macro panel. "
                    "Deliver: 1) Key data extracted with numbers+dates, "
                    "2) Potentiality map with 3 scenarios and probability %, "
                    "3) Concrete next move recommendation for Yohan."
                ),
            },
            {
                "agent_id": "analyst",
                "task": (
                    "Validate MiRo's market predictions. Check the numbers and logic. "
                    "Rate each scenario: probability (1-100%), confidence (1-10). "
                    "Add any risks MiRo missed. Final recommendation for Yohan. "
                    "Context from MiRo: {prev_result}"
                ),
            },
        ],
    )

    prediction = result.final_result or ""

    # Store predictions
    if prediction and memory:
        from backend.models.memory import MemoryEntry, MemoryType
        entry = MemoryEntry(
            content=f"MiRo prediction: {prediction[:400]}",
            memory_type=MemoryType.OBSERVATION,
            tags=["prediction", "miro", "proactive", "future"],
            source="miro_prediction",
            confidence=0.65,
        )
        memory.store(entry)

    # Push notification to Yohan
    if prediction and len(prediction) > 30 and notification_engine:
        try:
            await notification_engine.send(
                title="MiRo Market Prediction",
                body=prediction[:800],
                level="high",
                source="miro_prediction",
            )
        except Exception as ntf_exc:
            logger.warning("MiRo prediction notification failed: %s", ntf_exc)

    return prediction or "MiRo prediction complete"


async def miro_continuous_assess(
    *,
    collab: Any = None,
    memory: Any = None,
    notification_engine: Any = None,
) -> str:
    """MiRo continuously assesses market potentiality and shares to agent network."""
    if not collab:
        return "requires collab engine"

    try:
        result = await collab.delegate(
            from_agent="proactive_engine",
            to_agent="miro",
            task=(
                "Run a potentiality assessment NOW. Scan current market conditions, "
                "identify emerging trends, evaluate asset opportunities, and predict "
                "near-term movements. Focus on actionable signals that could generate "
                "revenue. Return: top 3 opportunities with confidence scores."
            ),
        )
        prediction = result.final_result or ""

        # Share MiRo's insights to agent network
        if prediction and len(prediction) > 30:
            # Store as observation
            if memory:
                from backend.models.memory import MemoryEntry, MemoryType
                memory.store(MemoryEntry(
                    content=f"MiRo continuous potentiality: {prediction[:500]}",
                    memory_type=MemoryType.OBSERVATION,
                    tags=["miro", "potentiality", "market", "continuous"],
                    source="miro_continuous",
                    confidence=0.7,
                ))

            # Push notification for actionable signals
            if notification_engine:
                try:
                    await notification_engine.send(
                        title="MiRo Potentiality Signal",
                        body=prediction[:600],
                        level="medium",
                        source="miro_continuous",
                    )
                except Exception as ntf_exc:
                    logger.warning("MiRo continuous notification failed: %s", ntf_exc)

        return f"MiRo assessment: {prediction[:200]}" if prediction else "MiRo: no prediction"

    except Exception as exc:
        logger.error("MiRo continuous assessment failed: %s", exc)
        return f"MiRo assessment failed: {exc}"


async def data_intelligence(*, collab: Any = None) -> str:
    """Run OpenClaw to discover new public data sources."""
    if not collab:
        return "requires collaboration"

    result = await collab.delegate(
        from_agent="proactive_engine",
        to_agent="openclaw",
        task="Run gap analysis and discovery to find new public data sources",
    )
    return result.final_result or "data intelligence scan complete"


async def business_discovery(
    *,
    collab: Any = None,
    memory: Any = None,
) -> str:
    """Scan for micro-SaaS, automation, and product opportunities."""
    if not collab:
        return "requires collab engine"

    try:
        result = await collab.pipeline(
            initiator="proactive_engine",
            goal="Discover new business and revenue opportunities",
            steps=[
                {
                    "agent_id": "researcher",
                    "task": (
                        "Search for trending micro-SaaS ideas, AI automation opportunities, "
                        "and underserved markets in 2024-2025. Focus on: "
                        "1. Problems that can be solved with AI/automation, "
                        "2. Markets where Yohan's skills (Python, FastAPI, AI, data pipelines) "
                        "give competitive advantage, "
                        "3. Low-capital, high-margin digital products. "
                        "Return top 5 opportunities with estimated revenue potential."
                    ),
                },
                {
                    "agent_id": "analyst",
                    "task": (
                        "Analyze these business opportunities: {prev_result}\n\n"
                        "For each, evaluate: market size, competition, time to MVP, "
                        "revenue potential, alignment with Yohan's goals ($10K+/mo MRR). "
                        "Rank by risk-adjusted ROI. Flag any that Yohan should act on NOW."
                    ),
                },
            ],
        )
        discovery = result.final_result or ""

        # Store discovery to memory
        if discovery and len(discovery) > 50 and memory:
            from backend.models.memory import MemoryEntry, MemoryType
            memory.store(MemoryEntry(
                content=f"Business discovery: {discovery[:500]}",
                memory_type=MemoryType.OBSERVATION,
                tags=["business", "discovery", "revenue", "opportunity"],
                source="business_discovery",
                confidence=0.65,
            ))

        return f"Business discovery: {discovery[:200]}" if discovery else "No opportunities found"

    except Exception as exc:
        logger.error("Business discovery failed: %s", exc)
        return f"Business discovery failed: {exc}"


async def scan_project_ecosystem(
    *,
    ecosystem: Any = None,
    memory: Any = None,
) -> str:
    """Scan project ecosystem and store awareness into memory."""
    if not ecosystem:
        return "requires ecosystem engine"

    context = ecosystem.get_context_for_brain()
    summary = ecosystem.get_ecosystem_summary()

    if memory:
        from backend.models.memory import MemoryEntry, MemoryType
        # Store/update ecosystem awareness
        memory.store(MemoryEntry(
            content=f"Project ecosystem: {summary['total_projects']} projects tracked. "
                    f"Revenue streams: {', '.join(f'{k}: {v}' for k, v in summary['by_revenue_stream'].items())}. "
                    f"Tech: {', '.join(summary['tech_stack_coverage'][:10])}. "
                    f"Connections: {summary['connections']} cross-project links.",
            memory_type=MemoryType.OBSERVATION,
            tags=["ecosystem", "projects", "portfolio", "overview"],
            source="ecosystem_scanner",
            confidence=0.9,
        ))

    return (
        f"Ecosystem scan: {summary['total_projects']} projects, "
        f"{summary['connections']} connections, "
        f"{len(summary['by_revenue_stream'])} revenue streams"
    )


async def correlate_projects(
    *,
    ecosystem: Any = None,
    llm: Any = None,
    memory: Any = None,
    experience_memory: Any = None,
) -> str:
    """Correlate across projects to find synergies, shared resources, and opportunities."""
    if not ecosystem or not llm:
        return "requires ecosystem + LLM"

    context = ecosystem.get_context_for_brain()
    connections = ecosystem.get_connections()
    summary = ecosystem.get_ecosystem_summary()

    # Gather recent memories about each project
    project_intel: list[str] = []
    if memory:
        from backend.models.memory import MemoryQuery
        for proj_name in [p.name for p in ecosystem.get_all_projects()]:
            hits = memory.search(MemoryQuery(query=proj_name, limit=2))
            for h in hits:
                project_intel.append(f"[{proj_name}] {h.content[:150]}")

    prompt = (
        "Analyze Yohan's project ecosystem for cross-project synergies and "
        "opportunities that aren't being exploited yet.\n\n"
        f"Projects:\n{context}\n\n"
        f"Known connections ({len(connections)}):\n"
        + "\n".join(f"- {c['source']} \u2194 {c['target']}: {c['description']}" for c in connections)
        + "\n\nRecent project intelligence:\n"
        + "\n".join(project_intel[:10])
        + "\n\nIdentify:\n"
        "1. Untapped synergies between projects\n"
        "2. Shared data/APIs that could be consolidated\n"
        "3. Revenue opportunities from combining projects\n"
        "4. Technical integrations that would multiply value\n\n"
        "Be specific and actionable. Focus on what's NOT yet connected."
    )

    try:
        response = await llm.complete(
            system="You are ROOT's cross-project intelligence analyst. Find synergies.",
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            max_tokens=800,
            method="proactive",
        )

        correlation = response.strip()
        if not correlation or len(correlation) < 30:
            return "No new correlations found"

        # Store correlation insights
        if memory:
            from backend.models.memory import MemoryEntry, MemoryType
            memory.store(MemoryEntry(
                content=f"Cross-project correlation: {correlation[:500]}",
                memory_type=MemoryType.OBSERVATION,
                tags=["ecosystem", "correlation", "synergy", "opportunity"],
                source="project_correlator",
                confidence=0.75,
            ))

        # Record as strategy experience
        if experience_memory:
            try:
                experience_memory.record_experience(
                    experience_type="strategy",
                    domain="ecosystem",
                    title="Cross-project correlation analysis",
                    description=correlation[:300],
                    context={"projects": summary.get("total_projects", 0)},
                )
            except Exception:
                pass

        return f"Project correlator: {correlation[:200]}"

    except Exception as exc:
        logger.error("Project correlation failed: %s", exc)
        return f"Correlation failed: {exc}"
