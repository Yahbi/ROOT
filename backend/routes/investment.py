"""
Investment Analysis API — thesis generation, debates, quant models, portfolio optimization.

Routes:
- POST /api/investment/thesis          — generate full thesis for a symbol
- POST /api/investment/thesis/quick    — fast thesis (quant + 4 analysts, no debate)
- POST /api/investment/thesis/multi    — theses for multiple symbols
- POST /api/investment/debate          — run bull/bear debate on a symbol
- GET  /api/investment/theses          — list recent theses
- GET  /api/investment/theses/{id}     — get specific thesis
- GET  /api/investment/debates         — list recent debates
- GET  /api/investment/debates/{id}    — get specific debate
- POST /api/investment/quant           — get quant score only (no LLM)
- POST /api/investment/kelly           — Kelly criterion calculation
- POST /api/investment/monte-carlo     — Monte Carlo simulation
- POST /api/investment/optimize        — portfolio optimization from theses
- GET  /api/investment/agents          — list available investment agents
- GET  /api/investment/stats           — engine statistics
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/investment", tags=["investment"])


# ── Request Models ───────────────────────────────────────────

class ThesisRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern=r'^[A-Za-z0-9.\-]+$')
    agent_ids: Optional[list[str]] = None
    include_debate: bool = True
    portfolio_value: float = Field(default=100_000.0, gt=0)


class QuickThesisRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern=r'^[A-Za-z0-9.\-]+$')
    portfolio_value: float = Field(default=100_000.0, gt=0)


class MultiThesisRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=20)
    portfolio_value: float = Field(default=100_000.0, gt=0)


class DebateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern=r'^[A-Za-z0-9.\-]+$')
    max_rounds: int = Field(default=2, ge=1, le=5)
    risk_rounds: int = Field(default=1, ge=1, le=3)


class QuantRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern=r'^[A-Za-z0-9.\-]+$')
    portfolio_value: float = Field(default=100_000.0, gt=0)


class KellyRequest(BaseModel):
    win_probability: float = Field(ge=0, le=1)
    win_loss_ratio: float = Field(default=1.0, gt=0)
    fraction: float = Field(default=0.25, gt=0, le=1)
    portfolio_value: float = Field(default=100_000.0, gt=0)
    max_position_pct: float = Field(default=5.0, gt=0, le=100)


class MonteCarloRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern=r'^[A-Za-z0-9.\-]+$')
    n_simulations: int = Field(default=10_000, ge=100, le=100_000)
    n_days: int = Field(default=30, ge=1, le=365)
    initial_value: float = Field(default=100_000.0, gt=0)


class OptimizeRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=20)
    portfolio_value: float = Field(default=100_000.0, gt=0)


# ── Helpers ──────────────────────────────────────────────────

def _get_thesis_engine(request: Request):
    engine = getattr(request.app.state, "thesis_engine", None)
    if engine is None:
        raise HTTPException(503, "Thesis engine not available")
    return engine


def _get_debate_engine(request: Request):
    engine = getattr(request.app.state, "debate_engine", None)
    if engine is None:
        raise HTTPException(503, "Debate engine not available")
    return engine


def _get_market_data(request: Request):
    mds = getattr(request.app.state, "market_data", None)
    if mds is None:
        from backend.core.market_data import MarketDataService
        mds = MarketDataService()
    return mds


def _get_portfolio_optimizer(request: Request):
    opt = getattr(request.app.state, "portfolio_optimizer", None)
    if opt is None:
        raise HTTPException(503, "Portfolio optimizer not available")
    return opt


def _thesis_to_dict(thesis) -> dict:
    """Convert InvestmentThesis to JSON-safe dict."""
    return asdict(thesis)


def _verdict_to_dict(verdict) -> dict:
    """Convert DebateVerdict to JSON-safe dict."""
    return asdict(verdict)


# ── Thesis Routes ────────────────────────────────────────────

@router.post("/thesis")
async def generate_thesis(request: Request, body: ThesisRequest):
    """Generate full investment thesis for a symbol."""
    engine = _get_thesis_engine(request)
    thesis = await engine.generate_thesis(
        symbol=body.symbol,
        agent_ids=body.agent_ids,
        include_debate=body.include_debate,
        portfolio_value=body.portfolio_value,
    )
    return _thesis_to_dict(thesis)


@router.post("/thesis/quick")
async def quick_thesis(request: Request, body: QuickThesisRequest):
    """Fast thesis: quant models + 4 analysis agents, no debate."""
    engine = _get_thesis_engine(request)
    thesis = await engine.quick_thesis(
        symbol=body.symbol,
        portfolio_value=body.portfolio_value,
    )
    return _thesis_to_dict(thesis)


@router.post("/thesis/multi")
async def multi_thesis(request: Request, body: MultiThesisRequest):
    """Generate theses for multiple symbols."""
    engine = _get_thesis_engine(request)
    theses = await engine.multi_thesis(
        symbols=body.symbols,
        portfolio_value=body.portfolio_value,
    )
    return {"theses": [_thesis_to_dict(t) for t in theses], "count": len(theses)}


@router.get("/theses")
async def list_theses(
    request: Request,
    symbol: Optional[str] = None,
    limit: int = 10,
):
    """List recent theses."""
    engine = _get_thesis_engine(request)
    theses = engine.get_theses(symbol=symbol, limit=limit)
    return {"theses": [_thesis_to_dict(t) for t in theses], "count": len(theses)}


@router.get("/theses/{thesis_id}")
async def get_thesis(request: Request, thesis_id: str):
    """Get a specific thesis by ID."""
    engine = _get_thesis_engine(request)
    thesis = engine.get_thesis(thesis_id)
    if thesis is None:
        raise HTTPException(404, f"Thesis {thesis_id} not found")
    return _thesis_to_dict(thesis)


# ── Debate Routes ────────────────────────────────────────────

@router.post("/debate")
async def run_debate(request: Request, body: DebateRequest):
    """Run a full bull/bear investment debate."""
    engine = _get_debate_engine(request)
    verdict = await engine.run_debate(
        symbol=body.symbol,
        max_rounds=body.max_rounds,
        risk_rounds=body.risk_rounds,
    )
    return _verdict_to_dict(verdict)


@router.get("/debates")
async def list_debates(
    request: Request,
    symbol: Optional[str] = None,
    limit: int = 10,
):
    """List recent debates."""
    engine = _get_debate_engine(request)
    debates = engine.get_debates(symbol=symbol, limit=limit)
    return {"debates": [_verdict_to_dict(d) for d in debates], "count": len(debates)}


@router.get("/debates/{debate_id}")
async def get_debate(request: Request, debate_id: str):
    """Get a specific debate by ID."""
    engine = _get_debate_engine(request)
    debate = engine.get_debate(debate_id)
    if debate is None:
        raise HTTPException(404, f"Debate {debate_id} not found")
    return _verdict_to_dict(debate)


# ── Quant Model Routes ───────────────────────────────────────

@router.post("/quant")
async def quant_score(request: Request, body: QuantRequest):
    """Get quantitative score for a symbol (pure math, no LLM needed)."""
    engine = _get_thesis_engine(request)
    score = engine.get_quant_score(body.symbol, body.portfolio_value)
    return asdict(score)


@router.post("/kelly")
async def kelly_calc(body: KellyRequest):
    """Calculate Kelly Criterion position sizing."""
    from backend.core.quant_models import kelly_criterion as kc
    result = kc(
        win_probability=body.win_probability,
        win_loss_ratio=body.win_loss_ratio,
        fraction=body.fraction,
        portfolio_value=body.portfolio_value,
        max_position_pct=body.max_position_pct,
    )
    return asdict(result)


@router.post("/monte-carlo")
async def monte_carlo(request: Request, body: MonteCarloRequest):
    """Run Monte Carlo simulation on a symbol."""
    from backend.core.quant_models import monte_carlo_simulation
    mds = _get_market_data(request)
    returns = mds.get_returns(body.symbol, period="1y")
    if len(returns) < 5:
        raise HTTPException(400, f"Insufficient data for {body.symbol}")
    result = monte_carlo_simulation(
        historical_returns=returns,
        n_simulations=body.n_simulations,
        n_days=body.n_days,
        initial_value=body.initial_value,
    )
    return result


# ── Portfolio Optimization ───────────────────────────────────

@router.post("/optimize")
async def optimize_portfolio(request: Request, body: OptimizeRequest):
    """Generate theses for symbols and optimize portfolio allocation."""
    thesis_engine = _get_thesis_engine(request)
    optimizer = _get_portfolio_optimizer(request)

    # Generate quick theses for all symbols
    theses = await thesis_engine.multi_thesis(
        symbols=body.symbols,
        portfolio_value=body.portfolio_value,
    )

    # Optimize allocation
    allocation = optimizer.optimize(
        theses=theses,
        portfolio_value=body.portfolio_value,
    )

    return asdict(allocation)


# ── Info Routes ──────────────────────────────────────────────

@router.get("/agents")
async def list_agents():
    """List all available investment agents."""
    from backend.core.investment_agents import InvestmentAgentRunner
    return {
        "agents": InvestmentAgentRunner.list_agents(),
        "philosophy_count": len(InvestmentAgentRunner.philosophy_agent_ids()),
        "analysis_count": len(InvestmentAgentRunner.analysis_agent_ids()),
        "total": len(InvestmentAgentRunner.all_agent_ids()),
    }


@router.get("/stats")
async def investment_stats(request: Request):
    """Get investment engine statistics."""
    thesis_engine = getattr(request.app.state, "thesis_engine", None)
    debate_engine = getattr(request.app.state, "debate_engine", None)
    meta_agent = getattr(request.app.state, "meta_agent", None)
    arb_agent = getattr(request.app.state, "arb_agent", None)
    economic = getattr(request.app.state, "economic_sustainability", None)
    episodic = getattr(request.app.state, "episodic_trades", None)
    perfection = getattr(request.app.state, "self_perfection", None)

    stats = {}
    if thesis_engine:
        stats["thesis"] = thesis_engine.stats()
    if debate_engine:
        stats["debate"] = debate_engine.stats()
    if meta_agent:
        stats["meta_agent"] = meta_agent.stats()
    if arb_agent:
        stats["arb_agent"] = arb_agent.stats()
    if economic:
        stats["economics"] = economic.stats()
    if episodic:
        stats["episodic_trades"] = episodic.stats()
    if perfection:
        stats["self_perfection"] = perfection.stats()
    return stats


@router.get("/hierarchy")
async def get_hierarchy(request: Request):
    """Get the organism hierarchy tree."""
    organism = getattr(request.app.state, "organism", None)
    if organism is None:
        from backend.core.organism_hierarchy import ORGANISM_TREE
        from dataclasses import asdict
        return {"tree": {k: asdict(v) for k, v in ORGANISM_TREE.items()}}
    return {"tree": organism.get_hierarchy(), "stats": organism.stats()}


@router.post("/pipeline")
async def run_pipeline(request: Request, body: MultiThesisRequest):
    """Run the full organism analysis pipeline."""
    organism = getattr(request.app.state, "organism", None)
    if organism is None:
        raise HTTPException(503, "Organism orchestrator not available")
    return await organism.full_analysis_pipeline(
        symbols=body.symbols,
        portfolio_value=body.portfolio_value,
    )
