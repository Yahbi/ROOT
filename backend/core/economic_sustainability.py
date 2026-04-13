"""
Economic Self-Sustainability Engine — "Pay for yourself or die."

Manages the trading organism's financial survival:
- Reinvestment rules: 50% profits → trading, 30% → compute/API, 20% → reserve
- Survival mode: if balance < threshold → low-risk MM-only + alert
- Cost tracking: API calls, VPS, data feeds
- Revenue attribution: which strategies generate profit
- Auto-scaling: scale up winning strategies, kill losers

The system must self-fund or die — no perpetual subsidies.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.economic_sustainability")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Configuration ────────────────────────────────────────────

DEFAULT_REINVESTMENT_RULES = {
    "trading_capital_pct": 50,     # 50% of profits → trading
    "compute_reserve_pct": 30,     # 30% → API/VPS/data costs
    "cold_storage_pct": 20,        # 20% → cold storage (safety net)
}

DEFAULT_SURVIVAL_THRESHOLDS = {
    "critical_balance_usd": 100.0,    # Below this → EMERGENCY mode
    "warning_balance_usd": 500.0,     # Below this → LOW-RISK mode
    "healthy_balance_usd": 2000.0,    # Above this → FULL mode
    "vps_monthly_cost_usd": 20.0,     # Estimated monthly operating cost
    "api_monthly_cost_usd": 50.0,     # Estimated API costs
    "survival_weeks": 4,              # Must cover N weeks of costs
}


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class FinancialSnapshot:
    """Point-in-time financial state."""
    trading_balance: float
    compute_reserve: float
    cold_storage: float
    total_balance: float
    monthly_costs: float
    monthly_revenue: float
    net_monthly: float
    runway_months: float       # How many months until broke
    mode: str                  # "full" | "low_risk" | "emergency" | "paused"
    warnings: list[str]
    timestamp: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class ProfitAllocation:
    """How profits are distributed."""
    gross_profit: float
    to_trading: float
    to_compute: float
    to_cold_storage: float
    strategy_source: str
    timestamp: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class StrategyPnL:
    """P&L attribution per strategy."""
    strategy_name: str
    gross_pnl: float
    trade_count: int
    win_rate: float
    avg_return_pct: float
    contribution_pct: float    # % of total profits from this strategy
    status: str                # "scaling_up" | "active" | "scaling_down" | "killed"


# ── Economic Sustainability Engine ───────────────────────────

class EconomicSustainability:
    """Manages the organism's financial survival and growth."""

    def __init__(
        self,
        reinvestment_rules: Optional[dict] = None,
        survival_thresholds: Optional[dict] = None,
        notification_engine=None,
        bus=None,
    ) -> None:
        self._rules = reinvestment_rules or DEFAULT_REINVESTMENT_RULES.copy()
        self._thresholds = survival_thresholds or DEFAULT_SURVIVAL_THRESHOLDS.copy()
        self._notifications = notification_engine
        self._bus = bus

        # Balances
        self._trading_balance: float = 0.0
        self._compute_reserve: float = 0.0
        self._cold_storage: float = 0.0

        # Tracking
        self._allocations: list[ProfitAllocation] = []
        self._strategy_pnl: dict[str, dict] = {}
        self._monthly_costs: float = (
            self._thresholds["vps_monthly_cost_usd"] +
            self._thresholds["api_monthly_cost_usd"]
        )
        self._mode: str = "full"
        self._snapshots: list[FinancialSnapshot] = []

    def set_initial_balance(
        self,
        trading: float = 0.0,
        compute: float = 0.0,
        cold: float = 0.0,
    ) -> None:
        """Set initial balances (from external wallet/account sync)."""
        self._trading_balance = trading
        self._compute_reserve = compute
        self._cold_storage = cold
        self._update_mode()

    def record_profit(
        self,
        amount: float,
        strategy: str = "unknown",
    ) -> ProfitAllocation:
        """Allocate profit according to reinvestment rules."""
        if amount <= 0:
            return ProfitAllocation(
                gross_profit=amount,
                to_trading=amount,  # Losses come from trading
                to_compute=0,
                to_cold_storage=0,
                strategy_source=strategy,
            )

        to_trading = amount * (self._rules["trading_capital_pct"] / 100.0)
        to_compute = amount * (self._rules["compute_reserve_pct"] / 100.0)
        to_cold = amount * (self._rules["cold_storage_pct"] / 100.0)

        self._trading_balance += to_trading
        self._compute_reserve += to_compute
        self._cold_storage += to_cold

        allocation = ProfitAllocation(
            gross_profit=round(amount, 2),
            to_trading=round(to_trading, 2),
            to_compute=round(to_compute, 2),
            to_cold_storage=round(to_cold, 2),
            strategy_source=strategy,
        )
        self._allocations.append(allocation)

        # Track per-strategy P&L
        if strategy not in self._strategy_pnl:
            self._strategy_pnl[strategy] = {"pnl": 0, "trades": 0, "wins": 0}
        self._strategy_pnl[strategy]["pnl"] += amount
        self._strategy_pnl[strategy]["trades"] += 1
        if amount > 0:
            self._strategy_pnl[strategy]["wins"] += 1

        self._update_mode()
        return allocation

    def record_loss(self, amount: float, strategy: str = "unknown") -> None:
        """Record a trading loss."""
        self._trading_balance -= abs(amount)
        if strategy not in self._strategy_pnl:
            self._strategy_pnl[strategy] = {"pnl": 0, "trades": 0, "wins": 0}
        self._strategy_pnl[strategy]["pnl"] -= abs(amount)
        self._strategy_pnl[strategy]["trades"] += 1
        self._update_mode()

    def record_cost(self, amount: float, category: str = "api") -> None:
        """Record an operating cost (deducted from compute reserve)."""
        self._compute_reserve -= abs(amount)
        if self._compute_reserve < 0:
            # Dip into trading balance
            shortfall = abs(self._compute_reserve)
            self._trading_balance -= shortfall
            self._compute_reserve = 0
        self._update_mode()

    def _update_mode(self) -> None:
        """Update operating mode based on current balance."""
        total = self.total_balance
        critical = self._thresholds["critical_balance_usd"]
        warning = self._thresholds["warning_balance_usd"]
        healthy = self._thresholds["healthy_balance_usd"]

        old_mode = self._mode

        if total <= critical:
            self._mode = "paused"
        elif total <= warning:
            self._mode = "emergency"
        elif total <= healthy:
            self._mode = "low_risk"
        else:
            self._mode = "full"

        # Alert on mode change
        if self._mode != old_mode:
            logger.warning(
                "Economic mode changed: %s → %s (balance: $%.2f)",
                old_mode, self._mode, total,
            )
            if self._mode in ("emergency", "paused"):
                self._send_alert(
                    f"ECONOMIC {self._mode.upper()}: Balance ${total:.2f}. "
                    f"{'Trading PAUSED — manual intervention required.' if self._mode == 'paused' else 'Switching to low-risk MM-only mode.'}"
                )

    def _send_alert(self, message: str) -> None:
        """Send alert via notification engine."""
        if self._notifications:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._notifications.send(
                        title="Economic Sustainability Alert",
                        body=message,
                        level="critical",
                        source="economic_sustainability",
                    ))
            except Exception:
                pass
        logger.critical("ECONOMIC ALERT: %s", message)

    @property
    def total_balance(self) -> float:
        return self._trading_balance + self._compute_reserve + self._cold_storage

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def runway_months(self) -> float:
        if self._monthly_costs <= 0:
            return float('inf')
        return self.total_balance / self._monthly_costs

    def get_snapshot(self) -> FinancialSnapshot:
        """Get current financial state."""
        total = self.total_balance
        runway = self.runway_months
        monthly_revenue = self._estimate_monthly_revenue()

        warnings = []
        if self._mode == "paused":
            warnings.append("CRITICAL: Trading paused — balance below survival threshold")
        elif self._mode == "emergency":
            warnings.append("WARNING: Emergency mode — low-risk only")
        if runway < 3:
            warnings.append(f"Low runway: {runway:.1f} months of operating costs remaining")
        if self._compute_reserve < self._thresholds["api_monthly_cost_usd"]:
            warnings.append("Compute reserve below 1 month of API costs")

        snapshot = FinancialSnapshot(
            trading_balance=round(self._trading_balance, 2),
            compute_reserve=round(self._compute_reserve, 2),
            cold_storage=round(self._cold_storage, 2),
            total_balance=round(total, 2),
            monthly_costs=self._monthly_costs,
            monthly_revenue=round(monthly_revenue, 2),
            net_monthly=round(monthly_revenue - self._monthly_costs, 2),
            runway_months=round(runway, 1),
            mode=self._mode,
            warnings=warnings,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def _estimate_monthly_revenue(self) -> float:
        """Estimate monthly revenue from recent allocations."""
        if not self._allocations:
            return 0.0
        # Use last 30 allocations as proxy
        recent = self._allocations[-30:]
        total_profit = sum(a.gross_profit for a in recent)
        return max(0, total_profit)

    def get_strategy_performance(self) -> list[StrategyPnL]:
        """Get P&L by strategy with scaling recommendations."""
        total_profit = sum(max(0, s["pnl"]) for s in self._strategy_pnl.values())
        results = []

        for name, data in self._strategy_pnl.items():
            trades = data["trades"]
            wins = data["wins"]
            pnl = data["pnl"]
            win_rate = wins / trades if trades > 0 else 0
            avg_return = pnl / trades if trades > 0 else 0
            contribution = (max(0, pnl) / total_profit * 100) if total_profit > 0 else 0

            # Status: scale up winners, kill losers
            if trades >= 10 and win_rate > 0.6 and pnl > 0:
                status = "scaling_up"
            elif trades >= 10 and (win_rate < 0.35 or pnl < 0):
                status = "killed"
            elif trades >= 5 and pnl < 0:
                status = "scaling_down"
            else:
                status = "active"

            results.append(StrategyPnL(
                strategy_name=name,
                gross_pnl=round(pnl, 2),
                trade_count=trades,
                win_rate=round(win_rate, 3),
                avg_return_pct=round(avg_return * 100, 2) if avg_return else 0,
                contribution_pct=round(contribution, 1),
                status=status,
            ))

        results.sort(key=lambda x: x.gross_pnl, reverse=True)
        return results

    def should_trade(self) -> bool:
        """Whether the system is allowed to trade."""
        return self._mode in ("full", "low_risk")

    def max_position_multiplier(self) -> float:
        """Position size multiplier based on mode.

        full=1.0, low_risk=0.5, emergency=0.25, paused=0.0
        """
        return {
            "full": 1.0,
            "low_risk": 0.5,
            "emergency": 0.25,
            "paused": 0.0,
        }.get(self._mode, 0.0)

    def stats(self) -> dict:
        total = self.total_balance
        return {
            "mode": self._mode,
            "total_balance": round(total, 2),
            "trading_balance": round(self._trading_balance, 2),
            "compute_reserve": round(self._compute_reserve, 2),
            "cold_storage": round(self._cold_storage, 2),
            "monthly_costs": self._monthly_costs,
            "runway_months": round(self.runway_months, 1),
            "total_allocations": len(self._allocations),
            "strategies_tracked": len(self._strategy_pnl),
            "position_multiplier": self.max_position_multiplier(),
        }
