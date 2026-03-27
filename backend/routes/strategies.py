"""Strategy validation API — autonomous backtest → rank → promote pipeline."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("/validate")
async def run_validation(request: Request) -> dict:
    """Trigger a full autonomous strategy validation scan.

    Tests all built-in strategies against default symbols,
    backtests each, runs Monte Carlo, and promotes winners.
    """
    validator = getattr(request.app.state, "strategy_validator", None)
    if not validator:
        raise HTTPException(status_code=503, detail="Strategy validator not available")

    results = await validator.validate_all_strategies()
    promoted = [r for r in results if r.get("promoted")]

    return {
        "total_tested": len(results),
        "promoted_count": len(promoted),
        "promoted": promoted,
        "top_10": results[:10],
    }


@router.get("/promoted")
async def get_promoted(request: Request, limit: int = 20) -> dict:
    """Get strategies that passed validation and are ready for live trading."""
    validator = getattr(request.app.state, "strategy_validator", None)
    if not validator:
        raise HTTPException(status_code=503, detail="Strategy validator not available")

    promoted = validator.get_promoted(limit=limit)
    return {"count": len(promoted), "strategies": promoted}


@router.get("/recent")
async def get_recent(request: Request, limit: int = 50) -> dict:
    """Get recent validation attempts (both passed and failed)."""
    validator = getattr(request.app.state, "strategy_validator", None)
    if not validator:
        raise HTTPException(status_code=503, detail="Strategy validator not available")

    recent = validator.get_recent(limit=limit)
    return {"count": len(recent), "validations": recent}


@router.get("/stats")
async def get_stats(request: Request) -> dict:
    """Summary statistics for strategy validation."""
    validator = getattr(request.app.state, "strategy_validator", None)
    if not validator:
        raise HTTPException(status_code=503, detail="Strategy validator not available")

    return validator.stats()
