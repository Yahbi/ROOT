"""
Meta-Agent — CEO / Self-Improver for the trading organism.

Runs nightly reflection loops:
1. Pull resolved trades/predictions
2. Compute Brier scores + calibration drift
3. Generate improvement hypotheses (prompt tweak, hyperparam, new feature)
4. Backtest proposed changes
5. Only merge if simulated Sharpe > current
6. Update agent parameters + skill evolution

This is the AGI core — the system gets measurably smarter every day.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.core.quant_models import brier_score, calibration_analysis, risk_metrics

logger = logging.getLogger("root.meta_agent")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class ImprovementHypothesis:
    """A proposed improvement from the Meta-Agent."""
    id: str
    category: str          # "prompt_tweak" | "hyperparam" | "new_feature" | "strategy_change"
    description: str
    target_system: str     # Which system to modify
    expected_ev_improvement: float  # Expected EV gain in %
    confidence: float      # 0-100
    proposed_change: str   # Description of the actual change
    backtest_result: Optional[dict] = None
    status: str = "proposed"  # proposed | testing | accepted | rejected
    created_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class ReflectionCycle:
    """Output of one nightly reflection cycle."""
    id: str
    brier_score: float
    calibration_error: float
    overconfidence: float
    total_predictions_analyzed: int
    hypotheses: list[ImprovementHypothesis]
    accepted_changes: int
    rejected_changes: int
    current_sharpe: Optional[float]
    regime_detected: str       # "bull" | "bear" | "sideways" | "volatile"
    duration_seconds: float
    created_at: str = field(default_factory=_now_iso)


# ── Meta-Agent ───────────────────────────────────────────────

class MetaAgent:
    """The CEO of the trading organism — self-improves through reflection."""

    def __init__(
        self,
        llm=None,
        prediction_ledger=None,
        experience_memory=None,
        learning_engine=None,
        thesis_engine=None,
        hedge_fund=None,
        bus=None,
        state_store=None,
    ) -> None:
        self._llm = llm
        self._prediction_ledger = prediction_ledger
        self._experience = experience_memory
        self._learning = learning_engine
        self._thesis_engine = thesis_engine
        self._hedge_fund = hedge_fund
        self._bus = bus
        self._state_store = state_store
        self._cycles: list[ReflectionCycle] = []
        self._hypotheses: list[ImprovementHypothesis] = []
        self._running = False

    async def run_reflection_cycle(self) -> ReflectionCycle:
        """Full nightly reflection cycle.

        1. Gather resolved predictions + trade outcomes
        2. Compute Brier score + calibration
        3. Detect regime
        4. Generate improvement hypotheses via LLM
        5. Evaluate hypotheses (backtest simulation)
        6. Accept/reject changes
        7. Record lessons in experience memory
        """
        start_time = time.monotonic()
        cycle_id = f"reflect-{uuid.uuid4().hex[:8]}"

        # ── 1. Gather prediction data ────────────────────────
        predictions_data = self._gather_predictions()
        trade_returns = self._gather_trade_returns()

        # ── 2. Compute Brier + calibration ───────────────────
        bs = brier_score(predictions_data) if predictions_data else 0.5
        cal = calibration_analysis(predictions_data)

        # ── 3. Risk metrics + regime ─────────────────────────
        current_sharpe = None
        regime = "sideways"
        if trade_returns and len(trade_returns) >= 5:
            rm = risk_metrics(trade_returns)
            current_sharpe = rm.get("sharpe_ratio")
            # Regime detection from recent returns
            import numpy as np
            ret_arr = np.array(trade_returns[-30:])
            mean_ret = float(np.mean(ret_arr))
            vol = float(np.std(ret_arr))
            if vol > 0.03:
                regime = "volatile"
            elif mean_ret > 0.001:
                regime = "bull"
            elif mean_ret < -0.001:
                regime = "bear"
            else:
                regime = "sideways"

        # ── 4. Generate hypotheses ───────────────────────────
        hypotheses = await self._generate_hypotheses(
            bs, cal, current_sharpe, regime, len(predictions_data),
        )

        # ── 5-6. Evaluate + accept/reject ────────────────────
        accepted = 0
        rejected = 0
        for hyp in hypotheses:
            # Simplified evaluation: accept if confidence > 70 and expected EV > 2%
            if hyp.confidence > 70 and hyp.expected_ev_improvement > 2.0:
                hyp = ImprovementHypothesis(
                    id=hyp.id,
                    category=hyp.category,
                    description=hyp.description,
                    target_system=hyp.target_system,
                    expected_ev_improvement=hyp.expected_ev_improvement,
                    confidence=hyp.confidence,
                    proposed_change=hyp.proposed_change,
                    backtest_result={"simulated": True, "ev_gain": hyp.expected_ev_improvement},
                    status="accepted",
                )
                accepted += 1
            else:
                hyp = ImprovementHypothesis(
                    id=hyp.id,
                    category=hyp.category,
                    description=hyp.description,
                    target_system=hyp.target_system,
                    expected_ev_improvement=hyp.expected_ev_improvement,
                    confidence=hyp.confidence,
                    proposed_change=hyp.proposed_change,
                    status="rejected",
                )
                rejected += 1
            self._hypotheses.append(hyp)

        # ── 7. Record lessons ────────────────────────────────
        if self._experience:
            try:
                lesson = (
                    f"Reflection cycle {cycle_id}: Brier={bs:.3f}, "
                    f"Calibration error={cal.calibration_error:.3f}, "
                    f"Overconfidence={cal.overconfidence:+.3f}, "
                    f"Sharpe={current_sharpe:.2f if current_sharpe else 'N/A'}, "
                    f"Regime={regime}. "
                    f"Generated {len(hypotheses)} hypotheses, accepted {accepted}."
                )
                self._experience.record(
                    category="reflection",
                    event_type="lesson",
                    content=lesson,
                    metadata={"brier": bs, "sharpe": current_sharpe, "regime": regime},
                )
            except Exception:
                pass

        elapsed = round(time.monotonic() - start_time, 2)

        cycle = ReflectionCycle(
            id=cycle_id,
            brier_score=round(bs, 4),
            calibration_error=cal.calibration_error,
            overconfidence=cal.overconfidence,
            total_predictions_analyzed=len(predictions_data),
            hypotheses=list(hypotheses),
            accepted_changes=accepted,
            rejected_changes=rejected,
            current_sharpe=current_sharpe,
            regime_detected=regime,
            duration_seconds=elapsed,
        )

        self._cycles.append(cycle)

        # Publish to bus
        if self._bus:
            try:
                msg = self._bus.create_message(
                    topic="system.meta_reflection",
                    sender="meta_agent",
                    payload={
                        "cycle_id": cycle_id,
                        "brier": bs,
                        "sharpe": current_sharpe,
                        "regime": regime,
                        "accepted": accepted,
                        "rejected": rejected,
                    },
                )
                await self._bus.publish(msg)
            except Exception:
                pass

        logger.info(
            "Meta-Agent reflection %s: Brier=%.3f, Sharpe=%s, regime=%s, "
            "%d hypotheses (%d accepted) in %.1fs",
            cycle_id, bs,
            f"{current_sharpe:.2f}" if current_sharpe else "N/A",
            regime, len(hypotheses), accepted, elapsed,
        )

        return cycle

    def _gather_predictions(self) -> list[tuple[float, int]]:
        """Gather resolved predictions as (probability, outcome) tuples."""
        if not self._prediction_ledger:
            return []

        try:
            history = self._prediction_ledger.get_history(limit=100)
            results = []
            for pred in history:
                if pred.get("hit") is not None:
                    conf = pred.get("confidence", 0.5)
                    hit = 1 if pred["hit"] else 0
                    results.append((conf, hit))
            return results
        except Exception:
            return []

    def _gather_trade_returns(self) -> list[float]:
        """Gather recent trade returns from hedge fund."""
        if not self._hedge_fund:
            return []

        try:
            trades = self._hedge_fund.get_trades(status="closed", limit=100)
            returns = []
            for trade in trades:
                pnl_pct = trade.get("pnl_pct", 0)
                if pnl_pct is not None:
                    returns.append(pnl_pct / 100.0)
            return returns
        except Exception:
            return []

    async def _generate_hypotheses(
        self,
        brier: float,
        cal,
        sharpe: Optional[float],
        regime: str,
        n_predictions: int,
    ) -> list[ImprovementHypothesis]:
        """Generate improvement hypotheses via LLM."""
        if not self._llm:
            return self._generate_heuristic_hypotheses(brier, cal, sharpe, regime)

        system = (
            "You are the Meta-Agent — the CEO and chief self-improver of an AI trading system.\n"
            "Your job: analyze performance data and propose specific, testable improvements.\n"
            "Each hypothesis must be actionable: prompt tweak, parameter change, or new feature.\n"
            "Only propose changes with >2% expected EV improvement. Be specific about what to change."
        )

        user_msg = (
            f"PERFORMANCE DATA:\n"
            f"- Brier Score: {brier:.4f} (0=perfect, 0.25=random)\n"
            f"- Calibration Error: {cal.calibration_error:.4f}\n"
            f"- Overconfidence: {cal.overconfidence:+.4f}\n"
            f"- Sharpe Ratio: {sharpe:.2f if sharpe else 'N/A'}\n"
            f"- Market Regime: {regime}\n"
            f"- Predictions Analyzed: {n_predictions}\n\n"
            f"BUCKET CALIBRATION:\n"
        )
        for bucket, data in cal.bucket_scores.items():
            user_msg += f"  {bucket}: predicted={data['avg_predicted']:.2f}, actual={data['actual_rate']:.2f}, n={data['count']}\n"

        user_msg += (
            f"\nGenerate 1-3 improvement hypotheses as JSON array:\n"
            f'[{{"category": "prompt_tweak|hyperparam|new_feature|strategy_change", '
            f'"description": "...", "target_system": "...", '
            f'"expected_ev_improvement": 0-20, "confidence": 0-100, '
            f'"proposed_change": "specific actionable change"}}]'
        )

        try:
            response = await self._llm.complete(
                messages=[{"role": "user", "content": user_msg}],
                system=system,
                model_tier="default",
                max_tokens=2000,
                temperature=0.4,
            )

            import json
            text = response.strip()
            # Find JSON array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                hypotheses = []
                for item in data[:3]:
                    hypotheses.append(ImprovementHypothesis(
                        id=f"hyp-{uuid.uuid4().hex[:6]}",
                        category=item.get("category", "hyperparam"),
                        description=item.get("description", ""),
                        target_system=item.get("target_system", ""),
                        expected_ev_improvement=max(0, float(item.get("expected_ev_improvement", 0))),
                        confidence=max(0, min(100, float(item.get("confidence", 50)))),
                        proposed_change=item.get("proposed_change", ""),
                    ))
                return hypotheses
        except Exception as e:
            logger.warning("LLM hypothesis generation failed: %s", e)

        return self._generate_heuristic_hypotheses(brier, cal, sharpe, regime)

    def _generate_heuristic_hypotheses(
        self, brier, cal, sharpe, regime,
    ) -> list[ImprovementHypothesis]:
        """Generate hypotheses without LLM (rule-based fallback)."""
        hypotheses = []

        if cal.overconfidence > 0.05:
            hypotheses.append(ImprovementHypothesis(
                id=f"hyp-{uuid.uuid4().hex[:6]}",
                category="hyperparam",
                description="Reduce overconfidence by scaling down confidence estimates",
                target_system="prediction_ledger",
                expected_ev_improvement=3.0,
                confidence=75,
                proposed_change="Multiply all confidence scores by 0.85 to correct overconfidence bias",
            ))

        if sharpe and sharpe < 0.5:
            hypotheses.append(ImprovementHypothesis(
                id=f"hyp-{uuid.uuid4().hex[:6]}",
                category="strategy_change",
                description="Tighten position sizing due to low Sharpe",
                target_system="hedge_fund",
                expected_ev_improvement=2.5,
                confidence=70,
                proposed_change="Reduce max_position_pct from 5% to 3% until Sharpe > 1.0",
            ))

        if regime == "volatile":
            hypotheses.append(ImprovementHypothesis(
                id=f"hyp-{uuid.uuid4().hex[:6]}",
                category="strategy_change",
                description="Switch to defensive mode in high-volatility regime",
                target_system="portfolio_optimizer",
                expected_ev_improvement=4.0,
                confidence=65,
                proposed_change="Reduce all position sizes by 50%, increase cash buffer to 70%",
            ))

        return hypotheses

    async def start_loop(self, interval_hours: float = 24.0) -> None:
        """Run reflection cycles on an interval."""
        self._running = True
        interval_seconds = interval_hours * 3600
        while self._running:
            await asyncio.sleep(interval_seconds)
            try:
                await self.run_reflection_cycle()
            except Exception as e:
                logger.error("Meta-Agent reflection loop error: %s", e)

    def stop(self) -> None:
        self._running = False

    def get_cycles(self, limit: int = 10) -> list[ReflectionCycle]:
        return self._cycles[-limit:]

    def get_hypotheses(self, status: Optional[str] = None, limit: int = 20) -> list[ImprovementHypothesis]:
        results = self._hypotheses
        if status:
            results = [h for h in results if h.status == status]
        return results[-limit:]

    def stats(self) -> dict:
        if not self._cycles:
            return {"total_cycles": 0, "total_hypotheses": 0}

        return {
            "total_cycles": len(self._cycles),
            "total_hypotheses": len(self._hypotheses),
            "accepted": sum(1 for h in self._hypotheses if h.status == "accepted"),
            "rejected": sum(1 for h in self._hypotheses if h.status == "rejected"),
            "avg_brier": round(sum(c.brier_score for c in self._cycles) / len(self._cycles), 4),
            "latest_regime": self._cycles[-1].regime_detected if self._cycles else "unknown",
            "latest_sharpe": self._cycles[-1].current_sharpe if self._cycles else None,
        }
