"""
Arbitrage & Market-Making Agent — LMSR spread harvesting + cross-market arb.

Implements:
- Softmax deviation detection (LMSR mispricing)
- Cross-market logical arbitrage (correlated markets summing != 100%)
- Pairs/stat-arb via cointegration
- Spread harvesting (bid-ask capture in prediction markets)
- Inventory management with fractional Kelly sizing

The PICO math core — runs pure math, no LLM needed at runtime for speed.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.core.quant_models import (
    detect_arbitrage,
    logical_arbitrage,
    kelly_prediction_market,
    cointegration_test,
    expected_value,
    bayesian_update,
)

logger = logging.getLogger("root.arb_agent")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class ArbOpportunity:
    """Detected arbitrage or spread opportunity."""
    id: str
    opportunity_type: str   # "logical_arb" | "spread" | "pairs" | "softmax_deviation" | "correlation_arb"
    markets: list[str]      # Market IDs or symbols involved
    prices: dict[str, float]  # Current prices
    expected_profit: float  # Estimated profit in USD
    risk_free: bool         # True if pure arbitrage (no directional risk)
    confidence: float       # 0-100
    kelly_size_pct: float   # Recommended position size
    reasoning: str
    expires_at: Optional[str] = None
    status: str = "detected"  # detected | executing | completed | expired
    created_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class SpreadPosition:
    """Active spread/arb position being managed."""
    id: str
    opportunity_id: str
    market_id: str
    side: str              # "yes" | "no" | "buy" | "sell"
    quantity: float
    entry_price: float
    current_price: float
    pnl: float
    status: str = "open"


# ── Arb Agent ────────────────────────────────────────────────

class ArbAgent:
    """Pure-math arbitrage and spread detection engine.

    Designed to run WITHOUT LLM for speed and cost efficiency.
    All strategies are mathematically derived.
    """

    def __init__(
        self,
        max_position_pct: float = 3.0,
        min_edge_pct: float = 1.0,
        max_concurrent_positions: int = 15,
        inventory_limit: float = 10_000.0,
    ) -> None:
        self._max_position_pct = max_position_pct
        self._min_edge_pct = min_edge_pct
        self._max_positions = max_concurrent_positions
        self._inventory_limit = inventory_limit
        self._opportunities: list[ArbOpportunity] = []
        self._positions: list[SpreadPosition] = []

    def scan_prediction_market_arb(
        self,
        markets: list[dict[str, Any]],
        portfolio_value: float = 100_000.0,
    ) -> list[ArbOpportunity]:
        """Scan prediction markets for arbitrage opportunities.

        Each market dict should have:
        - id: str
        - outcomes: list[dict] with {name, price}
        - related_markets: list[str] (IDs of correlated markets)

        Detects:
        1. Price sum != 1.0 (buy/sell all outcomes for risk-free profit)
        2. YES + NO > 1.0 or < 1.0
        3. Correlated markets with contradictory prices
        """
        opportunities = []

        for market in markets:
            market_id = market.get("id", "unknown")
            outcomes = market.get("outcomes", [])
            if not outcomes:
                continue

            prices = {o["name"]: o["price"] for o in outcomes if "name" in o and "price" in o}

            # 1. Check if prices sum to 1 (within tolerance)
            arb_result = detect_arbitrage(list(prices.values()), tolerance=0.02)

            if arb_result.arbitrage_detected:
                profit = arb_result.arbitrage_profit
                kelly = kelly_prediction_market(
                    true_probability=0.99,  # Near-certain profit
                    market_price=1.0 - profit,
                    fraction=0.25,
                    portfolio_value=portfolio_value,
                )

                opp = ArbOpportunity(
                    id=f"arb-{uuid.uuid4().hex[:8]}",
                    opportunity_type="logical_arb",
                    markets=[market_id],
                    prices=prices,
                    expected_profit=round(profit * kelly.max_position_usd, 2),
                    risk_free=True,
                    confidence=95.0,
                    kelly_size_pct=kelly.recommended_pct,
                    reasoning=(
                        f"Prices sum to {sum(prices.values()):.4f} (should be 1.0). "
                        f"Risk-free profit: {profit:.2%} per unit."
                    ),
                )
                opportunities.append(opp)
                self._opportunities.append(opp)

        return opportunities

    def scan_softmax_deviations(
        self,
        market_prices: dict[str, float],
        true_probabilities: dict[str, float],
        portfolio_value: float = 100_000.0,
    ) -> list[ArbOpportunity]:
        """Detect deviations between LMSR/softmax model and actual market prices.

        Compare model-implied fair prices against actual market prices.
        Trade when deviation exceeds minimum edge threshold.
        """
        opportunities = []

        for outcome, market_price in market_prices.items():
            true_prob = true_probabilities.get(outcome)
            if true_prob is None:
                continue

            # Calculate edge
            ev = expected_value(
                true_probability=true_prob,
                payout=1.0,
                cost=market_price,
            )

            if ev.is_positive_ev and ev.edge_pct > self._min_edge_pct:
                kelly = kelly_prediction_market(
                    true_probability=true_prob,
                    market_price=market_price,
                    fraction=0.25,
                    portfolio_value=portfolio_value,
                )

                opp = ArbOpportunity(
                    id=f"soft-{uuid.uuid4().hex[:8]}",
                    opportunity_type="softmax_deviation",
                    markets=[outcome],
                    prices={outcome: market_price},
                    expected_profit=round(ev.edge * kelly.max_position_usd, 2),
                    risk_free=False,
                    confidence=min(90, ev.edge_pct * 10),
                    kelly_size_pct=kelly.recommended_pct,
                    reasoning=(
                        f"Model: {true_prob:.2%}, Market: {market_price:.2%}, "
                        f"Edge: {ev.edge_pct:+.1f}%, EV: ${ev.expected_value:.2f}/unit. "
                        f"Kelly: {kelly.recommended_pct:.1f}%"
                    ),
                )
                opportunities.append(opp)
                self._opportunities.append(opp)

        return opportunities

    def scan_pairs_arb(
        self,
        symbol_a: str,
        symbol_b: str,
        prices_a: list[float],
        prices_b: list[float],
        portfolio_value: float = 100_000.0,
    ) -> Optional[ArbOpportunity]:
        """Detect pairs trading opportunity via cointegration."""
        result = cointegration_test(prices_a, prices_b)

        if result.get("error") or not result.get("is_cointegrated"):
            return None

        signal = result["signal"]
        if signal in ("no_trade", "hold"):
            return None

        z_score = abs(result["current_z_score"])
        confidence = min(90, z_score * 20 + 30)

        # Estimate profit based on mean reversion
        half_life = result.get("half_life_days")
        spread_std = result.get("spread_std", 0)
        expected_reversion = spread_std * min(z_score, 3)  # Capped at 3 sigma

        opp = ArbOpportunity(
            id=f"pair-{uuid.uuid4().hex[:8]}",
            opportunity_type="pairs",
            markets=[symbol_a, symbol_b],
            prices={symbol_a: prices_a[-1], symbol_b: prices_b[-1]},
            expected_profit=round(expected_reversion * portfolio_value * 0.02, 2),
            risk_free=False,
            confidence=confidence,
            kelly_size_pct=min(self._max_position_pct, confidence / 30),
            reasoning=(
                f"Cointegrated pair (half-life: {f'{half_life:.0f}d' if half_life else 'N/A'}). "
                f"Z-score: {result['current_z_score']:+.2f}, "
                f"Signal: {signal}, Hedge ratio: {result['hedge_ratio']:.3f}"
            ),
        )
        self._opportunities.append(opp)
        return opp

    def scan_cross_market_arb(
        self,
        correlated_prices: dict[str, float],
        constraint: str = "sum_equals_one",
        portfolio_value: float = 100_000.0,
    ) -> list[ArbOpportunity]:
        """Detect logical arbitrage across correlated markets."""
        result = logical_arbitrage(correlated_prices, constraint)

        opportunities = []
        for opp_data in result.get("opportunities", []):
            profit = opp_data.get("risk_free_profit", 0)
            opp = ArbOpportunity(
                id=f"xarb-{uuid.uuid4().hex[:8]}",
                opportunity_type="correlation_arb",
                markets=list(correlated_prices.keys()),
                prices=correlated_prices,
                expected_profit=round(profit * portfolio_value * 0.01, 2),
                risk_free=True,
                confidence=95.0,
                kelly_size_pct=min(self._max_position_pct, 4.0),
                reasoning=(
                    f"Cross-market arb: {opp_data['type']}. "
                    f"Total: {result['total']:.4f}, "
                    f"Risk-free profit: {profit:.2%}"
                ),
            )
            opportunities.append(opp)
            self._opportunities.append(opp)

        return opportunities

    def update_probability(
        self,
        prior: float,
        evidence_supports: bool,
        evidence_strength: float = 0.7,
    ) -> float:
        """Bayesian update of probability estimate given new evidence.

        Args:
            prior: Current probability estimate (0-1)
            evidence_supports: True if evidence supports the hypothesis
            evidence_strength: How diagnostic the evidence is (0.5-1.0)
        """
        if evidence_supports:
            return bayesian_update(prior, evidence_strength, 1 - evidence_strength)
        else:
            return bayesian_update(prior, 1 - evidence_strength, evidence_strength)

    def manage_inventory(
        self,
        current_inventory: float,
        new_trade_size: float,
    ) -> dict:
        """Check if a new trade fits within inventory limits."""
        projected = current_inventory + new_trade_size
        within_limits = abs(projected) <= self._inventory_limit

        return {
            "current_inventory": current_inventory,
            "new_trade_size": new_trade_size,
            "projected_inventory": projected,
            "inventory_limit": self._inventory_limit,
            "within_limits": within_limits,
            "utilization_pct": round(abs(projected) / self._inventory_limit * 100, 1),
            "headroom": round(self._inventory_limit - abs(projected), 2),
        }

    def get_opportunities(
        self,
        opportunity_type: Optional[str] = None,
        status: str = "detected",
        limit: int = 20,
    ) -> list[ArbOpportunity]:
        results = self._opportunities
        if opportunity_type:
            results = [o for o in results if o.opportunity_type == opportunity_type]
        if status:
            results = [o for o in results if o.status == status]
        return results[-limit:]

    def stats(self) -> dict:
        if not self._opportunities:
            return {"total_opportunities": 0}

        types = [o.opportunity_type for o in self._opportunities]
        return {
            "total_opportunities": len(self._opportunities),
            "risk_free": sum(1 for o in self._opportunities if o.risk_free),
            "by_type": {t: types.count(t) for t in set(types)},
            "total_expected_profit": round(sum(o.expected_profit for o in self._opportunities), 2),
            "avg_confidence": round(sum(o.confidence for o in self._opportunities) / len(self._opportunities), 1),
            "active_positions": len([p for p in self._positions if p.status == "open"]),
        }
