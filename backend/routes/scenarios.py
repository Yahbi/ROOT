"""Routes for Scenario Simulator — What-If Lab for market simulations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class SimulateRequest(BaseModel):
    hypothesis: str = Field(min_length=5, max_length=1000)
    symbols: str = Field(default="", max_length=200)
    time_horizon: str = Field(default="1 week", max_length=50)
    agent_count: int = Field(default=5, ge=2, le=7)
    synthesis_rounds: int = Field(default=1, ge=1, le=3)


@router.post("/simulate")
async def run_scenario(req: SimulateRequest, request: Request):
    """Run a what-if scenario simulation with parallel agents."""
    simulator = getattr(request.app.state, "scenario_simulator", None)
    if not simulator:
        raise HTTPException(503, "Scenario simulator not available")

    from backend.core.scenario_simulator import ScenarioConfig

    config = ScenarioConfig(
        hypothesis=req.hypothesis,
        symbols=req.symbols,
        time_horizon=req.time_horizon,
        agent_count=req.agent_count,
        synthesis_rounds=req.synthesis_rounds,
    )

    try:
        result = await simulator.simulate(config)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Simulation failed: {str(exc)[:200]}")

    return {
        "id": result.id,
        "hypothesis": result.config.hypothesis,
        "symbols": result.config.symbols,
        "time_horizon": result.config.time_horizon,
        "agent_perspectives": result.agent_perspectives,
        "potentiality_map": {
            "bull": {
                "scenario": result.bull_scenario,
                "probability": result.bull_probability,
            },
            "base": {
                "scenario": result.base_scenario,
                "probability": result.base_probability,
            },
            "bear": {
                "scenario": result.bear_scenario,
                "probability": result.bear_probability,
            },
        },
        "synthesis": result.synthesis,
        "created_at": result.created_at,
    }


@router.get("")
async def list_scenarios(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
):
    """List recent scenario simulations."""
    simulator = getattr(request.app.state, "scenario_simulator", None)
    if not simulator:
        raise HTTPException(503, "Scenario simulator not available")

    scenarios = simulator.list_scenarios(limit=limit)
    return {"scenarios": scenarios, "total": len(scenarios)}


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str, request: Request):
    """Get a specific scenario simulation by ID."""
    simulator = getattr(request.app.state, "scenario_simulator", None)
    if not simulator:
        raise HTTPException(503, "Scenario simulator not available")

    data = simulator.get_scenario(scenario_id)
    if not data:
        raise HTTPException(404, "Scenario not found")

    return data
