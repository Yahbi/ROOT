"""MiRo world intelligence — autonomous multi-domain analysis and daily briefing."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("root.proactive.intelligence")

# Domain rotation — each run covers 2 domains (round-robin by run_count)
_INTELLIGENCE_DOMAINS: list[dict[str, str]] = [
    {
        "key": "markets",
        "prompt": (
            "Analyze current market conditions across major indices and assets "
            "(SPY, QQQ, BTC, ETH, gold, oil). Report key movers, volume anomalies, "
            "and short-term outlook with confidence levels."
        ),
    },
    {
        "key": "geopolitics",
        "prompt": (
            "Assess current geopolitical developments — conflicts, trade tensions, "
            "sanctions, elections, diplomacy shifts. Evaluate their market and "
            "economic implications. Flag any emerging risks."
        ),
    },
    {
        "key": "ai_technology",
        "prompt": (
            "Report on the latest AI and technology developments — model releases, "
            "breakthroughs, regulatory changes, major acquisitions, open-source "
            "milestones. Identify opportunities for Yohan's projects."
        ),
    },
    {
        "key": "crypto_defi",
        "prompt": (
            "Analyze crypto market dynamics — BTC/ETH price action, DeFi protocol "
            "developments, regulatory news, Layer 2 activity, emerging trends. "
            "Highlight actionable opportunities and risks."
        ),
    },
    {
        "key": "weather_climate",
        "prompt": (
            "Assess significant weather events and climate patterns — extreme weather, "
            "natural disasters, seasonal shifts. Evaluate their economic and "
            "supply chain impacts, commodity price effects."
        ),
    },
    {
        "key": "macro_economics",
        "prompt": (
            "Analyze central bank signals, inflation data, employment trends, GDP "
            "updates, and fiscal policy developments across major economies. "
            "Summarize the macro outlook and investment implications."
        ),
    },
]


async def miro_world_intelligence(
    *,
    collab: Any = None,
    memory: Any = None,
    notification_engine: Any = None,
    run_count: int = 0,
) -> str:
    """MiRo scans 2 world domains per cycle (round-robin) and pushes insights."""
    if not collab:
        return "requires collab engine"

    n_domains = len(_INTELLIGENCE_DOMAINS)
    idx_start = (run_count * 2) % n_domains
    domains_this_run = [
        _INTELLIGENCE_DOMAINS[idx_start % n_domains],
        _INTELLIGENCE_DOMAINS[(idx_start + 1) % n_domains],
    ]

    results: list[str] = []
    for domain in domains_this_run:
        try:
            result = await collab.delegate(
                from_agent="proactive_engine",
                to_agent="miro",
                task=domain["prompt"],
            )
            analysis = result.final_result or ""
            if not analysis or len(analysis) < 20:
                continue

            # Store to memory
            if memory:
                from backend.models.memory import MemoryEntry, MemoryType
                memory.store(MemoryEntry(
                    content=f"MiRo [{domain['key']}]: {analysis[:500]}",
                    memory_type=MemoryType.OBSERVATION,
                    tags=["miro", "intelligence", domain["key"], "proactive"],
                    source=f"miro_world_{domain['key']}",
                    confidence=0.7,
                ))

            # Push notification
            if notification_engine:
                try:
                    await notification_engine.send(
                        title=f"MiRo Intelligence: {domain['key'].replace('_', ' ').title()}",
                        body=analysis[:800],
                        level="medium",
                        source=f"miro_world_{domain['key']}",
                    )
                except Exception as ntf_exc:
                    logger.warning("Intelligence notification failed for %s: %s", domain["key"], ntf_exc)

            results.append(f"[{domain['key']}] {analysis[:150]}")

        except Exception as exc:
            logger.error("MiRo world intelligence failed for %s: %s", domain["key"], exc)
            results.append(f"[{domain['key']}] failed: {exc}")

    summary = " | ".join(results) if results else "no domains analyzed"
    return f"World intelligence ({len(results)}/2 domains): {summary[:300]}"


async def miro_daily_briefing(
    *,
    collab: Any = None,
    llm: Any = None,
    memory: Any = None,
    notification_engine: Any = None,
) -> str:
    """MiRo synthesizes a comprehensive daily briefing across all domains."""
    if not llm:
        return "requires LLM"

    # Gather recent MiRo observations from memory
    recent_intel: list[str] = []
    if memory:
        from backend.models.memory import MemoryQuery, MemoryType
        hits = memory.search(MemoryQuery(
            query="MiRo intelligence prediction potentiality market",
            memory_type=MemoryType.OBSERVATION,
            limit=20,
        ))
        for h in hits:
            recent_intel.append(h.content[:300])

    intel_context = "\n".join(recent_intel[:15]) if recent_intel else "No recent intelligence available."

    prompt = (
        "You are MiRo, Yohan's autonomous world intelligence oracle. "
        "Synthesize a comprehensive daily briefing from recent observations.\n\n"
        f"Recent intelligence:\n{intel_context}\n\n"
        "Create a structured briefing covering:\n"
        "1. MARKETS — key moves, outlook, opportunities\n"
        "2. GEOPOLITICS — developments and implications\n"
        "3. AI & TECH — breakthroughs, regulatory changes\n"
        "4. CRYPTO — market dynamics, DeFi news\n"
        "5. MACRO — central bank signals, economic indicators\n"
        "6. WEATHER — significant events and economic impacts\n"
        "7. RECOMMENDATIONS — top 3 actionable items for Yohan\n\n"
        "Be concise but insightful. Lead with the most important developments."
    )

    try:
        briefing = await llm.complete(
            system="You are MiRo — Yohan's autonomous prediction and world intelligence engine.",
            messages=[{"role": "user", "content": prompt}],
            model_tier="default",
            max_tokens=1200,
            method="proactive",
        )
        briefing = briefing.strip()

        if not briefing or len(briefing) < 50:
            return "MiRo daily briefing: insufficient data to synthesize"

        # Store the briefing
        if memory:
            from backend.models.memory import MemoryEntry, MemoryType
            memory.store(MemoryEntry(
                content=f"MiRo daily briefing: {briefing[:600]}",
                memory_type=MemoryType.OBSERVATION,
                tags=["miro", "briefing", "daily", "intelligence"],
                source="miro_daily_briefing",
                confidence=0.75,
            ))

        # Push comprehensive notification
        if notification_engine:
            try:
                await notification_engine.send(
                    title="MiRo Daily Briefing",
                    body=briefing[:1500],
                    level="high",
                    source="miro_daily_briefing",
                )
            except Exception as ntf_exc:
                logger.warning("Daily briefing notification failed: %s", ntf_exc)

        return f"MiRo daily briefing: {briefing[:200]}"

    except Exception as exc:
        logger.error("MiRo daily briefing failed: %s", exc)
        return f"MiRo daily briefing failed: {exc}"
