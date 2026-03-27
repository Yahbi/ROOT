"""Backtesting routes — run and query hedge fund backtests."""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/backtesting", tags=["backtesting"])


# ── Request Models ───────────────────────────────────────────


class SignalItem(BaseModel):
    """A single trading signal for backtesting."""
    date: str = Field(..., min_length=1, max_length=30, description="ISO date string")
    symbol: str = Field(..., min_length=1, max_length=10, description="Ticker symbol")
    action: str = Field(..., pattern=r"^(buy|sell)$", description="buy or sell")
    price: float = Field(..., gt=0, description="Execution price")
    quantity: int = Field(..., gt=0, description="Number of shares")


class BacktestRequest(BaseModel):
    """Request body for running a backtest."""
    strategy_name: str = Field(..., min_length=1, max_length=200, description="Strategy name")
    signals: list[SignalItem] = Field(..., min_length=1, max_length=10000, description="Trading signals")
    initial_capital: float = Field(100_000.0, gt=0, le=1_000_000_000, description="Starting capital")


class MonteCarloRequest(BaseModel):
    """Request body for Monte Carlo simulation."""
    simulations: int = Field(1000, gt=0, le=100_000, description="Number of simulations")


# ── Endpoints ────────────────────────────────────────────────


@router.post("/run")
async def run_backtest(body: BacktestRequest, request: Request):
    """Run a backtest with the given strategy signals."""
    backtester = _get_backtester(request)

    signals_dicts = [s.model_dump() for s in body.signals]

    try:
        result = backtester.backtest(
            strategy_name=body.strategy_name,
            signals=signals_dicts,
            initial_capital=body.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}") from exc

    return {"status": "completed", "result": asdict(result)}


@router.get("/results")
async def list_results(
    request: Request,
    limit: int = Query(20, gt=0, le=1000, description="Max results to return"),
):
    """List stored backtest results, most recent first."""
    backtester = _get_backtester(request)

    try:
        results = backtester.get_results(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch results: {exc}") from exc

    return {
        "count": len(results),
        "results": [asdict(r) for r in results],
    }


@router.get("/results/{result_id}")
async def get_result(result_id: str, request: Request):
    """Get a single backtest result by ID."""
    backtester = _get_backtester(request)

    try:
        result = backtester.get_result(result_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch result: {exc}") from exc

    if result is None:
        raise HTTPException(status_code=404, detail=f"Backtest result '{result_id}' not found")

    return {"result": asdict(result)}


@router.post("/monte-carlo/{result_id}")
async def run_monte_carlo(
    result_id: str,
    request: Request,
    body: Optional[MonteCarloRequest] = None,
):
    """Run Monte Carlo simulation on a stored backtest result."""
    backtester = _get_backtester(request)
    simulations = body.simulations if body else 1000

    try:
        source_result = backtester.get_result(result_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch result: {exc}") from exc

    if source_result is None:
        raise HTTPException(status_code=404, detail=f"Backtest result '{result_id}' not found")

    try:
        mc_result = backtester.monte_carlo(
            backtest_result=source_result,
            simulations=simulations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Monte Carlo failed: {exc}") from exc

    return {
        "status": "completed",
        "source": asdict(source_result),
        "monte_carlo": mc_result,
    }


# ── Helpers ──────────────────────────────────────────────────


def _get_backtester(request: Request):
    """Extract backtester from app state, raising 503 if unavailable."""
    backtester = getattr(request.app.state, "backtester", None)
    if backtester is None:
        raise HTTPException(status_code=503, detail="Backtester not initialized")
    return backtester
