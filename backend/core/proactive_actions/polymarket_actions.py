"""
Proactive actions for Polymarket trading bot.

- scan_polymarkets: Scan markets and collect price data
- polymarket_trade_cycle: Full autonomous trading cycle
- monitor_polymarket_positions: Check open positions for exits
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("root.proactive.polymarket")


async def scan_polymarkets(*, polymarket_bot: Any = None) -> str:
    """Scan Polymarket for market data and store snapshots."""
    if not polymarket_bot:
        return "requires polymarket_bot"

    try:
        snapshots = await polymarket_bot.scan_markets(limit=30)
        return f"Scanned {len(snapshots)} Polymarket markets"
    except Exception as e:
        logger.error("Polymarket scan failed: %s", e)
        return f"Scan failed: {str(e)[:200]}"


async def polymarket_trade_cycle(
    *,
    polymarket_bot: Any = None,
    escalation: Any = None,
) -> str:
    """Run full Polymarket trading cycle: scan → analyze → trade → monitor."""
    if not polymarket_bot:
        return "requires polymarket_bot"

    # Check escalation before trading
    if escalation:
        decision = escalation.should_auto_execute(
            "polymarket_trade_cycle", risk_level="critical",
        )
        if not decision.should_auto_execute:
            logger.info("Polymarket trade blocked by escalation: %s", decision.reason)
            return f"Escalation blocked: {decision.reason}"

    try:
        results = await polymarket_bot.run_cycle()
        return (
            f"Polymarket cycle: {results['markets_scanned']} markets, "
            f"{results['scalp_signals']} scalp + {results['edge_signals']} edge signals, "
            f"{results['trades_executed']} executed, {results['trades_failed']} failed"
        )
    except Exception as e:
        logger.error("Polymarket trade cycle failed: %s", e)
        return f"Trade cycle failed: {str(e)[:200]}"


async def monitor_polymarket_positions(
    *,
    polymarket_bot: Any = None,
) -> str:
    """Monitor open Polymarket positions for profit/loss exits."""
    if not polymarket_bot:
        return "requires polymarket_bot"

    try:
        summary = await polymarket_bot.monitor_positions()
        return (
            f"Polymarket monitor: {summary['checked']} checked, "
            f"{summary['closed_profit']} profit, {summary['closed_loss']} loss, "
            f"{summary['still_open']} open"
        )
    except Exception as e:
        logger.error("Polymarket position monitor failed: %s", e)
        return f"Monitor failed: {str(e)[:200]}"
