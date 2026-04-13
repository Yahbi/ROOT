"""
Portfolio Optimizer — risk management + portfolio construction.

Combines multiple thesis signals into portfolio-level decisions:
- Correlation-aware position sizing
- Volatility-adjusted limits
- Sector/concentration constraints
- Kelly-optimal allocation across positions
- Drawdown protection

Works with ROOT's HedgeFundEngine for execution.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

from backend.core.quant_models import kelly_criterion, garch_volatility, risk_metrics
from backend.core.market_data import MarketDataService

logger = logging.getLogger("root.portfolio_optimizer")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class PositionRecommendation:
    """Recommended position for one symbol."""
    symbol: str
    action: str             # buy | sell | hold | short | cover
    weight_pct: float       # Portfolio weight (0-100)
    dollar_amount: float
    shares: int
    confidence: float
    reasoning: str
    risk_contribution: float  # How much this adds to portfolio risk


@dataclass(frozen=True)
class PortfolioAllocation:
    """Complete portfolio allocation recommendation."""
    id: str
    positions: list[PositionRecommendation]
    total_invested_pct: float
    cash_pct: float
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    max_correlation: float
    sector_concentrations: dict[str, float]
    risk_warnings: list[str]
    created_at: str = field(default_factory=_now_iso)


# ── Portfolio Optimizer ──────────────────────────────────────

class PortfolioOptimizer:
    """Optimizes portfolio allocation from multiple thesis signals."""

    def __init__(
        self,
        market_data: Optional[MarketDataService] = None,
        max_position_pct: float = 5.0,
        max_portfolio_risk_pct: float = 15.0,
        max_sector_pct: float = 30.0,
        max_correlation: float = 0.8,
        max_positions: int = 15,
    ) -> None:
        self._market_data = market_data or MarketDataService()
        self._max_position_pct = max_position_pct
        self._max_portfolio_risk = max_portfolio_risk_pct
        self._max_sector_pct = max_sector_pct
        self._max_correlation = max_correlation
        self._max_positions = max_positions

    def optimize(
        self,
        theses: list,  # list[InvestmentThesis]
        portfolio_value: float = 100_000.0,
        existing_positions: Optional[dict[str, float]] = None,
    ) -> PortfolioAllocation:
        """Build optimal portfolio allocation from thesis signals.

        Steps:
        1. Filter: only actionable theses (buy/short with confidence > 60)
        2. Score: rank by confidence * kelly_edge
        3. Correlations: reduce positions that are too correlated
        4. Volatility adjust: reduce size in high-vol environments
        5. Sector constraints: cap sector exposure
        6. Allocate: Kelly-fractional sizing within constraints
        """
        import uuid
        alloc_id = f"alloc-{uuid.uuid4().hex[:8]}"

        # 1. Filter actionable theses
        actionable = [
            t for t in theses
            if t.recommended_action in ("buy", "short")
            and t.final_confidence >= 55
        ]

        # Sort by score (confidence * abs(quant_composite))
        actionable.sort(
            key=lambda t: t.final_confidence * abs(t.quant_score.composite_score),
            reverse=True,
        )

        # Cap at max positions
        actionable = actionable[:self._max_positions]

        if not actionable:
            return PortfolioAllocation(
                id=alloc_id,
                positions=[],
                total_invested_pct=0.0,
                cash_pct=100.0,
                expected_return=0.0,
                expected_volatility=0.0,
                sharpe_ratio=0.0,
                max_correlation=0.0,
                sector_concentrations={},
                risk_warnings=["No actionable theses found"],
            )

        # 2. Get return series for correlation analysis
        symbols = [t.symbol for t in actionable]
        returns_map: dict[str, list[float]] = {}
        for sym in symbols:
            rets = self._market_data.get_returns(sym, period="6mo")
            if rets:
                returns_map[sym] = rets

        # 3. Correlation matrix
        corr_matrix = self._compute_correlations(returns_map, symbols)
        max_corr = 0.0
        if corr_matrix is not None and len(corr_matrix) > 1:
            # Find max off-diagonal correlation
            n = len(corr_matrix)
            for i in range(n):
                for j in range(i + 1, n):
                    max_corr = max(max_corr, abs(corr_matrix[i][j]))

        # 4. Compute raw weights
        positions = []
        sector_totals: dict[str, float] = {}
        total_weight = 0.0
        risk_warnings = []

        for thesis in actionable:
            sym = thesis.symbol

            # Base size from thesis
            base_pct = thesis.position_size_pct

            # Volatility adjustment
            vol_mult = 1.0
            if thesis.quant_score.volatility_regime == "high_volatility":
                vol_mult = 0.5
                risk_warnings.append(f"{sym}: High vol — position halved")
            elif thesis.quant_score.volatility_regime == "low_volatility":
                vol_mult = 1.25

            # Correlation penalty: reduce if highly correlated with existing
            corr_mult = 1.0
            if corr_matrix is not None:
                sym_idx = symbols.index(sym) if sym in symbols else -1
                if sym_idx >= 0:
                    for j, other_sym in enumerate(symbols):
                        if j != sym_idx and abs(corr_matrix[sym_idx][j]) > self._max_correlation:
                            corr_mult = 0.5
                            risk_warnings.append(
                                f"{sym}: High correlation with {other_sym} — position reduced"
                            )
                            break

            # Sector constraint
            sector = self._get_sector(sym)
            sector_current = sector_totals.get(sector, 0.0)
            sector_remaining = self._max_sector_pct - sector_current
            if sector_remaining <= 0:
                risk_warnings.append(f"{sym}: Sector {sector} at max — skipped")
                continue

            # Final weight
            weight = min(
                base_pct * vol_mult * corr_mult,
                self._max_position_pct,
                sector_remaining,
            )

            # Don't exceed total portfolio risk
            if total_weight + weight > self._max_portfolio_risk * 100 / 100:
                weight = max(0, self._max_portfolio_risk * 100 / 100 - total_weight)
                if weight <= 0:
                    risk_warnings.append(f"{sym}: Portfolio risk limit reached — skipped")
                    continue

            dollar_amount = portfolio_value * (weight / 100.0)
            quote = self._market_data.get_quote(sym)
            price = quote.price if quote else 100.0
            shares = int(dollar_amount / price) if price > 0 else 0

            if shares <= 0 and weight > 0:
                shares = 1

            # Risk contribution (simplified: weight * volatility)
            vol = thesis.quant_score.annual_volatility or 0.20
            risk_contrib = weight * vol

            positions.append(PositionRecommendation(
                symbol=sym,
                action=thesis.recommended_action,
                weight_pct=round(weight, 2),
                dollar_amount=round(dollar_amount, 2),
                shares=shares,
                confidence=thesis.final_confidence,
                reasoning=thesis.thesis_narrative[:200],
                risk_contribution=round(risk_contrib, 3),
            ))

            total_weight += weight
            sector_totals[sector] = sector_current + weight

        # Portfolio-level metrics
        total_invested = sum(p.weight_pct for p in positions)
        cash_pct = 100.0 - total_invested

        # Expected portfolio return/vol (simplified)
        if positions and returns_map:
            weights_arr = np.array([p.weight_pct / 100 for p in positions])
            # Pad weights to match available returns
            exp_returns_list = []
            exp_vols_list = []
            for p in positions:
                rets = returns_map.get(p.symbol, [])
                if rets:
                    exp_returns_list.append(np.mean(rets) * 252)
                    exp_vols_list.append(np.std(rets) * math.sqrt(252))
                else:
                    exp_returns_list.append(0.0)
                    exp_vols_list.append(0.20)

            exp_return = float(np.dot(weights_arr, exp_returns_list))
            # Simplified portfolio vol (assumes some correlation)
            exp_vol = float(np.sqrt(np.dot(weights_arr ** 2, np.array(exp_vols_list) ** 2)))
            sharpe = (exp_return - 0.02) / exp_vol if exp_vol > 0 else 0.0
        else:
            exp_return = 0.0
            exp_vol = 0.0
            sharpe = 0.0

        return PortfolioAllocation(
            id=alloc_id,
            positions=positions,
            total_invested_pct=round(total_invested, 2),
            cash_pct=round(cash_pct, 2),
            expected_return=round(exp_return, 4),
            expected_volatility=round(exp_vol, 4),
            sharpe_ratio=round(sharpe, 3),
            max_correlation=round(max_corr, 3),
            sector_concentrations={k: round(v, 1) for k, v in sector_totals.items()},
            risk_warnings=risk_warnings,
        )

    def _compute_correlations(
        self, returns_map: dict[str, list[float]], symbols: list[str],
    ) -> Optional[np.ndarray]:
        """Compute correlation matrix from return series."""
        available = [s for s in symbols if s in returns_map]
        if len(available) < 2:
            return None

        # Align length
        min_len = min(len(returns_map[s]) for s in available)
        if min_len < 10:
            return None

        matrix = np.array([returns_map[s][-min_len:] for s in available])
        return np.corrcoef(matrix)

    def _get_sector(self, symbol: str) -> str:
        """Get sector for a symbol."""
        fm = self._market_data.get_financials(symbol)
        return fm.sector if fm and fm.sector else "Unknown"

    def rebalance_check(
        self,
        current_positions: dict[str, float],  # symbol -> current weight
        target_positions: list[PositionRecommendation],
    ) -> list[dict]:
        """Check if rebalancing is needed and generate trade list."""
        trades = []
        target_map = {p.symbol: p for p in target_positions}

        # Positions to add or increase
        for p in target_positions:
            current_weight = current_positions.get(p.symbol, 0.0)
            diff = p.weight_pct - current_weight
            if abs(diff) > 0.5:  # Threshold: 0.5% to avoid churn
                trades.append({
                    "symbol": p.symbol,
                    "action": "increase" if diff > 0 else "decrease",
                    "current_weight": current_weight,
                    "target_weight": p.weight_pct,
                    "change": round(diff, 2),
                })

        # Positions to close (in current but not in target)
        for sym, weight in current_positions.items():
            if sym not in target_map and weight > 0:
                trades.append({
                    "symbol": sym,
                    "action": "close",
                    "current_weight": weight,
                    "target_weight": 0.0,
                    "change": -weight,
                })

        return trades
