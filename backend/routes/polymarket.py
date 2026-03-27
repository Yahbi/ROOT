"""
Polymarket trading bot API routes.

GET  /api/polymarket/stats        — Bot statistics + P&L
GET  /api/polymarket/positions    — Open positions
GET  /api/polymarket/history      — Market price history
POST /api/polymarket/cycle        — Trigger trading cycle
POST /api/polymarket/scan         — Scan markets only
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("root.routes.polymarket")

router = APIRouter(prefix="/api/polymarket", tags=["polymarket"])


def _get_bot(request: Request):
    bot = getattr(request.app.state, "polymarket_bot", None)
    if not bot:
        raise HTTPException(503, "Polymarket bot not configured")
    return bot


@router.get("/stats")
async def get_stats(request: Request):
    bot = _get_bot(request)
    return bot.stats()


@router.get("/positions")
async def get_positions(request: Request):
    bot = _get_bot(request)
    return {"positions": bot.get_open_positions()}


@router.get("/history/{condition_id}")
async def get_history(request: Request, condition_id: str, limit: int = 50):
    bot = _get_bot(request)
    return {"history": bot.get_market_history(condition_id, limit=min(limit, 200))}


@router.post("/cycle")
async def run_cycle(request: Request):
    bot = _get_bot(request)
    results = await bot.run_cycle()
    return results


@router.post("/scan")
async def scan_markets(request: Request):
    bot = _get_bot(request)
    snapshots = await bot.scan_markets(limit=30)
    return {
        "markets_scanned": len(snapshots),
        "markets": [
            {
                "question": s.question,
                "yes_price": s.yes_price,
                "no_price": s.no_price,
                "volume_24h": s.volume_24h,
                "liquidity": s.liquidity,
            }
            for s in snapshots[:20]
        ],
    }
