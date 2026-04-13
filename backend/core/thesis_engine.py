"""
Thesis Engine — investment thesis generation blending qualitative + quantitative signals.

Orchestrates the full AI hedge fund analysis pipeline:
1. Market data collection
2. Quantitative model scoring (Kelly, GARCH, technicals, risk metrics)
3. Investment agent analysis (13 philosophy + 4 specialist agents)
4. Bull/Bear debate
5. Thesis synthesis with position sizing

Integrates with ROOT's existing systems:
- HedgeFundEngine for execution
- PredictionLedger for tracking
- ExperienceMemory for learning
- MessageBus for inter-agent communication
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.core.quant_models import (
    kelly_criterion,
    garch_volatility,
    compute_indicators,
    risk_metrics,
    monte_carlo_simulation,
    simple_arima_forecast,
    brier_score,
    expected_value,
)
from backend.core.investment_agents import InvestmentSignal, InvestmentAgentRunner
from backend.core.market_data import MarketDataService

logger = logging.getLogger("root.thesis_engine")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class QuantScore:
    """Quantitative scoring from math models."""
    symbol: str
    technical_trend: str           # bullish | bearish | neutral
    rsi: float
    macd_signal: str               # bullish | bearish | neutral
    volatility_regime: str         # high | normal | low
    annual_volatility: float
    arima_direction: str           # bullish | bearish | neutral
    arima_pct_change: float
    monte_carlo_prob_profit: float
    sharpe_ratio: Optional[float]
    kelly_recommended_pct: float
    kelly_edge: float
    composite_score: float         # -100 to +100


@dataclass(frozen=True)
class InvestmentThesis:
    """Complete investment thesis combining all signals."""
    id: str
    symbol: str

    # Quantitative
    quant_score: QuantScore

    # Qualitative (from agents)
    agent_signals: list[InvestmentSignal]
    bull_consensus: float          # % of agents bullish
    bear_consensus: float          # % of agents bearish
    avg_confidence: float

    # Debate (optional)
    debate_verdict: Optional[str] = None
    debate_id: Optional[str] = None

    # Synthesis
    final_signal: str = "neutral"  # bullish | bearish | neutral
    final_confidence: float = 50.0
    recommended_action: str = "hold"  # buy | sell | hold | short
    position_size_pct: float = 0.0
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None

    # Narrative
    thesis_narrative: str = ""
    key_bull_points: list[str] = field(default_factory=list)
    key_bear_points: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)

    # Meta
    agents_used: int = 0
    duration_seconds: float = 0.0
    created_at: str = field(default_factory=_now_iso)


# ── Thesis Engine ────────────────────────────────────────────

class ThesisEngine:
    """Generates investment theses by blending quant models + agent analysis."""

    def __init__(
        self,
        llm=None,
        market_data: Optional[MarketDataService] = None,
        debate_engine=None,
        experience_memory=None,
        prediction_ledger=None,
        learning_engine=None,
        bus=None,
    ) -> None:
        self._llm = llm
        self._market_data = market_data or MarketDataService()
        self._debate_engine = debate_engine
        self._experience = experience_memory
        self._prediction_ledger = prediction_ledger
        self._learning = learning_engine
        self._bus = bus
        self._investment_runner: Optional[InvestmentAgentRunner] = None
        self._theses: list[InvestmentThesis] = []

        if llm:
            self._investment_runner = InvestmentAgentRunner(llm, self._market_data)

    def set_debate_engine(self, debate_engine) -> None:
        self._debate_engine = debate_engine

    # ── Core Pipeline ────────────────────────────────────────

    async def generate_thesis(
        self,
        symbol: str,
        agent_ids: Optional[list[str]] = None,
        include_debate: bool = True,
        portfolio_value: float = 100_000.0,
    ) -> InvestmentThesis:
        """Full thesis generation pipeline.

        1. Compute quant score (pure math, no LLM needed)
        2. Run investment agents (LLM-powered, parallel)
        3. Optionally run debate
        4. Synthesize into thesis
        """
        start_time = time.monotonic()
        thesis_id = f"thesis-{uuid.uuid4().hex[:8]}"
        symbol = symbol.upper()

        # ── 1. Quantitative Score ────────────────────────────
        quant = self._compute_quant_score(symbol, portfolio_value)

        # ── 2. Agent Analysis (parallel) ─────────────────────
        agent_signals = []
        if self._investment_runner:
            ids = agent_ids or InvestmentAgentRunner.all_agent_ids()
            # Run in batches to avoid overwhelming LLM
            batch_size = 4
            for i in range(0, len(ids), batch_size):
                batch = ids[i:i + batch_size]
                batch_signals = await self._investment_runner.analyze_multi(batch, symbol)
                agent_signals.extend(batch_signals)

        # ── 3. Debate (optional) ─────────────────────────────
        debate_verdict = None
        debate_id = None
        if include_debate and self._debate_engine:
            try:
                debate = await self._debate_engine.run_debate(
                    symbol=symbol,
                    max_rounds=2,
                )
                debate_verdict = debate.research_manager_verdict
                debate_id = debate.id
            except Exception as e:
                logger.warning("Debate skipped for %s: %s", symbol, e)

        # ── 4. Synthesize ────────────────────────────────────
        thesis = self._synthesize(
            thesis_id, symbol, quant, agent_signals,
            debate_verdict, debate_id, portfolio_value, start_time,
        )

        self._theses.append(thesis)

        # Record prediction
        if self._prediction_ledger and thesis.recommended_action in ("buy", "short"):
            try:
                self._prediction_ledger.record_prediction(
                    source="thesis_engine",
                    symbol=symbol,
                    direction="long" if thesis.recommended_action == "buy" else "short",
                    confidence=thesis.final_confidence / 100.0,
                    reasoning=thesis.thesis_narrative[:500],
                    deadline_hours=168,
                    target_price=thesis.target_price,
                )
            except Exception:
                pass

        # Publish to bus
        if self._bus:
            try:
                msg = self._bus.create_message(
                    topic="system.thesis",
                    sender="thesis_engine",
                    payload={
                        "thesis_id": thesis_id,
                        "symbol": symbol,
                        "signal": thesis.final_signal,
                        "confidence": thesis.final_confidence,
                        "action": thesis.recommended_action,
                        "position_pct": thesis.position_size_pct,
                    },
                )
                await self._bus.publish(msg)
            except Exception:
                pass

        logger.info(
            "Thesis %s for %s: %s (confidence=%.0f%%, size=%.1f%%) using %d agents in %.1fs",
            thesis_id, symbol, thesis.recommended_action, thesis.final_confidence,
            thesis.position_size_pct, thesis.agents_used,
            thesis.duration_seconds,
        )

        return thesis

    async def quick_thesis(
        self,
        symbol: str,
        portfolio_value: float = 100_000.0,
    ) -> InvestmentThesis:
        """Fast thesis using only quant models + 4 analysis agents (no debate)."""
        return await self.generate_thesis(
            symbol=symbol,
            agent_ids=InvestmentAgentRunner.analysis_agent_ids(),
            include_debate=False,
            portfolio_value=portfolio_value,
        )

    async def full_thesis(
        self,
        symbol: str,
        portfolio_value: float = 100_000.0,
    ) -> InvestmentThesis:
        """Full thesis using all 17 agents + debate."""
        return await self.generate_thesis(
            symbol=symbol,
            agent_ids=None,  # All agents
            include_debate=True,
            portfolio_value=portfolio_value,
        )

    async def multi_thesis(
        self,
        symbols: list[str],
        portfolio_value: float = 100_000.0,
    ) -> list[InvestmentThesis]:
        """Generate theses for multiple symbols (sequential to avoid LLM overload)."""
        results = []
        for sym in symbols:
            try:
                thesis = await self.quick_thesis(sym, portfolio_value)
                results.append(thesis)
            except Exception as e:
                logger.error("Thesis generation failed for %s: %s", sym, e)
        return results

    # ── Quant Scoring ────────────────────────────────────────

    def _compute_quant_score(
        self,
        symbol: str,
        portfolio_value: float,
    ) -> QuantScore:
        """Compute pure-math quantitative score."""
        closes = self._market_data.get_closes(symbol, period="1y")
        returns = self._market_data.get_returns(symbol, period="1y")

        # Technical indicators
        tech = {"trend": "neutral", "rsi_14": 50.0, "macd": 0}
        if len(closes) >= 26:
            tech = compute_indicators(closes)

        # GARCH volatility
        vol = {"regime": "normal", "current_annual_vol": 0.20}
        if len(returns) >= 10:
            vol = garch_volatility(returns)

        # ARIMA direction forecast
        arima = {"direction": "neutral", "pct_change": 0.0}
        if len(closes) >= 60:
            arima = simple_arima_forecast(closes, forecast_days=5)

        # Monte Carlo
        mc = {"prob_profit": 0.5}
        if len(returns) >= 20:
            mc = monte_carlo_simulation(returns, n_simulations=5000, n_days=30, initial_value=portfolio_value)

        # Risk metrics
        rm = {"sharpe_ratio": 0.0}
        if len(returns) >= 5:
            rm = risk_metrics(returns)

        # Kelly sizing
        win_rate = rm.get("win_rate", 0.5)
        avg_win = abs(rm.get("avg_win", 0.01))
        avg_loss = abs(rm.get("avg_loss", 0.01))
        wl_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0
        kelly = kelly_criterion(
            win_probability=win_rate,
            win_loss_ratio=wl_ratio,
            fraction=0.25,
            portfolio_value=portfolio_value,
        )

        # Composite score: weighted blend of all signals (-100 to +100)
        tech_score = 0.0
        trend = tech.get("trend", "neutral")
        if trend == "bullish":
            tech_score = 30
        elif trend == "bearish":
            tech_score = -30

        rsi = tech.get("rsi_14", 50)
        if rsi < 30:
            tech_score += 20  # Oversold = bullish
        elif rsi > 70:
            tech_score -= 20  # Overbought = bearish

        arima_score = 0.0
        if arima.get("direction") == "bullish":
            arima_score = min(20, arima.get("pct_change", 0) * 5)
        elif arima.get("direction") == "bearish":
            arima_score = max(-20, arima.get("pct_change", 0) * 5)

        mc_score = (mc.get("prob_profit", 0.5) - 0.5) * 40  # -20 to +20

        sharpe = rm.get("sharpe_ratio", 0)
        sharpe_score = max(-10, min(10, sharpe * 5))

        composite = tech_score + arima_score + mc_score + sharpe_score
        composite = max(-100, min(100, composite))

        # Determine MACD signal
        macd_val = tech.get("macd", 0)
        macd_sig = tech.get("macd_signal", 0)
        if isinstance(macd_val, (int, float)) and isinstance(macd_sig, (int, float)):
            macd_signal_str = "bullish" if macd_val > macd_sig else "bearish" if macd_val < macd_sig else "neutral"
        else:
            macd_signal_str = "neutral"

        return QuantScore(
            symbol=symbol,
            technical_trend=trend if isinstance(trend, str) else "neutral",
            rsi=float(rsi),
            macd_signal=macd_signal_str,
            volatility_regime=vol.get("regime", "normal"),
            annual_volatility=vol.get("current_annual_vol", 0.20),
            arima_direction=arima.get("direction", "neutral"),
            arima_pct_change=arima.get("pct_change", 0.0),
            monte_carlo_prob_profit=mc.get("prob_profit", 0.5),
            sharpe_ratio=rm.get("sharpe_ratio"),
            kelly_recommended_pct=kelly.recommended_pct,
            kelly_edge=kelly.edge,
            composite_score=round(composite, 1),
        )

    # ── Synthesis ────────────────────────────────────────────

    def _synthesize(
        self,
        thesis_id: str,
        symbol: str,
        quant: QuantScore,
        agent_signals: list[InvestmentSignal],
        debate_verdict: Optional[str],
        debate_id: Optional[str],
        portfolio_value: float,
        start_time: float,
    ) -> InvestmentThesis:
        """Blend quant + qualitative signals into final thesis."""

        # Agent consensus
        bullish_count = sum(1 for s in agent_signals if s.signal == "bullish")
        bearish_count = sum(1 for s in agent_signals if s.signal == "bearish")
        total_agents = len(agent_signals) or 1
        bull_pct = bullish_count / total_agents * 100
        bear_pct = bearish_count / total_agents * 100
        avg_conf = sum(s.confidence for s in agent_signals) / total_agents if agent_signals else 50

        # Weighted final signal
        # Quant weight: 40%, Agent consensus: 40%, Debate: 20%
        quant_direction = 1 if quant.composite_score > 15 else -1 if quant.composite_score < -15 else 0
        agent_direction = 1 if bull_pct > 60 else -1 if bear_pct > 60 else 0

        debate_direction = 0
        if debate_verdict:
            debate_direction = 1 if debate_verdict == "bullish" else -1 if debate_verdict == "bearish" else 0

        weighted = (
            quant_direction * 0.4 +
            agent_direction * 0.4 +
            debate_direction * 0.2
        )

        if weighted > 0.2:
            final_signal = "bullish"
            recommended_action = "buy"
        elif weighted < -0.2:
            final_signal = "bearish"
            recommended_action = "sell"
        else:
            final_signal = "neutral"
            recommended_action = "hold"

        # Confidence: blend of quant composite strength + agent agreement + avg confidence
        quant_conf = min(100, abs(quant.composite_score))
        agreement_conf = max(bull_pct, bear_pct)
        final_confidence = (quant_conf * 0.3 + agreement_conf * 0.3 + avg_conf * 0.4)
        final_confidence = max(0, min(100, final_confidence))

        # Position size: Kelly-based, capped
        if final_signal == "neutral" or final_confidence < 60:
            position_size = 0.0
        else:
            position_size = min(
                quant.kelly_recommended_pct,
                5.0,  # Hard cap
                final_confidence / 25,  # Scale with confidence
            )

        # Build narrative
        bull_points = []
        bear_points = []
        for s in agent_signals:
            if s.signal == "bullish" and s.thesis:
                bull_points.append(f"{s.agent_name}: {s.thesis[:100]}")
            elif s.signal == "bearish" and s.thesis:
                bear_points.append(f"{s.agent_name}: {s.thesis[:100]}")

        risk_factors = []
        if quant.volatility_regime == "high_volatility":
            risk_factors.append("High volatility regime — reduce position size")
        if quant.rsi > 70:
            risk_factors.append("RSI overbought — potential pullback")
        if quant.rsi < 30:
            risk_factors.append("RSI oversold — potential bounce")
        if quant.kelly_edge < 0:
            risk_factors.append("Negative Kelly edge — no mathematical edge detected")

        # Target and stop from strongest signal
        target_price = None
        stop_loss = None
        for s in sorted(agent_signals, key=lambda x: x.confidence, reverse=True):
            if s.target_price and not target_price:
                target_price = s.target_price
            if s.stop_loss and not stop_loss:
                stop_loss = s.stop_loss

        thesis_narrative = (
            f"{symbol}: {final_signal.upper()} with {final_confidence:.0f}% confidence. "
            f"Quant composite: {quant.composite_score:+.0f}/100 "
            f"(tech={quant.technical_trend}, vol={quant.volatility_regime}, "
            f"ARIMA={quant.arima_direction}, MC profit prob={quant.monte_carlo_prob_profit:.0%}). "
            f"Agent consensus: {bull_pct:.0f}% bull, {bear_pct:.0f}% bear "
            f"(avg confidence: {avg_conf:.0f}%). "
        )
        if debate_verdict:
            thesis_narrative += f"Debate verdict: {debate_verdict}. "
        if recommended_action != "hold":
            thesis_narrative += (
                f"Recommended: {recommended_action.upper()} {position_size:.1f}% of portfolio "
                f"(Kelly: {quant.kelly_recommended_pct:.1f}%, edge: {quant.kelly_edge:.3f})."
            )

        elapsed = round(time.monotonic() - start_time, 2)

        return InvestmentThesis(
            id=thesis_id,
            symbol=symbol,
            quant_score=quant,
            agent_signals=agent_signals,
            bull_consensus=round(bull_pct, 1),
            bear_consensus=round(bear_pct, 1),
            avg_confidence=round(avg_conf, 1),
            debate_verdict=debate_verdict,
            debate_id=debate_id,
            final_signal=final_signal,
            final_confidence=round(final_confidence, 1),
            recommended_action=recommended_action,
            position_size_pct=round(position_size, 2),
            target_price=target_price,
            stop_loss=stop_loss,
            thesis_narrative=thesis_narrative,
            key_bull_points=bull_points[:5],
            key_bear_points=bear_points[:5],
            risk_factors=risk_factors,
            agents_used=len(agent_signals),
            duration_seconds=elapsed,
        )

    # ── Retrieval ────────────────────────────────────────────

    def get_thesis(self, thesis_id: str) -> Optional[InvestmentThesis]:
        for t in self._theses:
            if t.id == thesis_id:
                return t
        return None

    def get_theses(self, symbol: Optional[str] = None, limit: int = 10) -> list[InvestmentThesis]:
        results = self._theses
        if symbol:
            results = [t for t in results if t.symbol == symbol.upper()]
        return results[-limit:]

    def get_quant_score(self, symbol: str, portfolio_value: float = 100_000.0) -> QuantScore:
        """Get quant score only (no LLM needed)."""
        return self._compute_quant_score(symbol, portfolio_value)

    def stats(self) -> dict:
        if not self._theses:
            return {"total_theses": 0}

        signals = [t.final_signal for t in self._theses]
        actions = [t.recommended_action for t in self._theses]
        return {
            "total_theses": len(self._theses),
            "avg_confidence": round(sum(t.final_confidence for t in self._theses) / len(self._theses), 1),
            "signals": {s: signals.count(s) for s in set(signals)},
            "actions": {a: actions.count(a) for a in set(actions)},
            "avg_agents_used": round(sum(t.agents_used for t in self._theses) / len(self._theses), 1),
            "avg_duration_seconds": round(sum(t.duration_seconds for t in self._theses) / len(self._theses), 1),
        }
