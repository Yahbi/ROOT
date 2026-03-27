"""Hedge Fund routes — AI-powered autonomous trading system API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/hedge-fund", tags=["hedge-fund"])


class ManualSignalRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    direction: str = Field(..., pattern=r"^(long|short)$")
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    reasoning: str = Field("", max_length=2000)
    timeframe: str = Field("swing", pattern=r"^(intraday|swing|position)$")


class CloseTradeRequest(BaseModel):
    trade_id: str
    exit_price: float


# ── Market Scanning ─────────────────────────────────────────

@router.post("/scan")
async def scan_markets(request: Request):
    """Trigger a market scan — agents generate trading signals."""
    hf = request.app.state.hedge_fund
    signals = await hf.scan_markets()
    return {
        "status": "scan_complete",
        "signal_count": len(signals),
        "signals": [
            {
                "id": s.id,
                "symbol": s.symbol,
                "direction": s.direction,
                "confidence": s.confidence,
                "source": s.source,
                "reasoning": s.reasoning[:200],
                "timeframe": s.timeframe,
            }
            for s in signals
        ],
    }


@router.post("/cycle")
async def run_cycle(request: Request):
    """Run one full hedge fund cycle: scan → analyze → decide → execute."""
    hf = request.app.state.hedge_fund
    results = await hf.run_cycle()
    return {"status": "cycle_complete", **results}


# ── Signals ─────────────────────────────────────────────────

@router.get("/signals")
async def get_signals(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    """Get recent trading signals."""
    hf = request.app.state.hedge_fund
    return hf.get_signals(limit=limit)


@router.post("/signals")
async def add_manual_signal(req: ManualSignalRequest, request: Request):
    """Add a manual trading signal (from Yohan)."""
    import uuid
    from backend.core.hedge_fund import Signal, _now_iso

    signal = Signal(
        id=f"sig_{uuid.uuid4().hex[:8]}",
        symbol=req.symbol.upper(),
        direction=req.direction,
        confidence=req.confidence,
        source="yohan_manual",
        reasoning=req.reasoning or f"Manual signal from Yohan: {req.direction} {req.symbol}",
        timeframe=req.timeframe,
        created_at=_now_iso(),
    )
    hf = request.app.state.hedge_fund
    hf._store_signal(signal)
    return {"status": "stored", "signal_id": signal.id}


# ── Trades ──────────────────────────────────────────────────

@router.get("/trades")
async def get_trades(request: Request, status: str = "all", limit: int = Query(default=50, ge=1, le=500)):
    """Get trades, optionally filtered by status."""
    hf = request.app.state.hedge_fund
    return hf.get_trades(status=status, limit=limit)


@router.post("/trades/close")
async def close_trade(req: CloseTradeRequest, request: Request):
    """Close a trade and record the outcome."""
    hf = request.app.state.hedge_fund
    result = hf.record_trade_outcome(req.trade_id, req.exit_price)
    if not result:
        raise HTTPException(status_code=404, detail="Trade not found")
    return result


@router.post("/execute")
async def execute_signal(request: Request, signal_id: str):
    """Execute a specific signal (manual trigger)."""
    hf = request.app.state.hedge_fund
    row = hf.conn.execute(
        "SELECT * FROM signals WHERE id = ?", (signal_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    from backend.core.hedge_fund import Signal
    signal = Signal(
        id=row["id"],
        symbol=row["symbol"],
        direction=row["direction"],
        confidence=row["confidence"],
        source=row["source"],
        reasoning=row["reasoning"] or "",
        timeframe=row["timeframe"] or "swing",
        entry_price=row["entry_price"],
        stop_loss=row["stop_loss"],
        take_profit=row["take_profit"],
        created_at=row["created_at"],
    )

    portfolio = await hf.get_portfolio()
    portfolio_value = portfolio.get("total_value", 100000)
    result = await hf.execute_signal(signal, portfolio_value)
    return result or {"status": "no_result"}


# ── Portfolio ───────────────────────────────────────────────

@router.get("/portfolio")
async def get_portfolio(request: Request):
    """Get current portfolio state."""
    hf = request.app.state.hedge_fund
    return await hf.get_portfolio()


@router.get("/performance")
async def get_performance(request: Request):
    """Get overall hedge fund performance stats."""
    hf = request.app.state.hedge_fund
    return hf.get_performance()


@router.get("/strategies")
async def get_strategies(request: Request):
    """Get learned strategy weights."""
    hf = request.app.state.hedge_fund
    return hf.get_strategy_weights()


# ── Risk Controls ───────────────────────────────────────────

@router.get("/risk-limits")
async def get_risk_limits():
    """Get current risk control settings."""
    from backend.core.hedge_fund import RISK_LIMITS
    return RISK_LIMITS
