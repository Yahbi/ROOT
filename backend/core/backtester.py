"""
Hedge Fund Backtesting Engine — simulate strategies against historical signals.

Features:
- Full backtest with equity curve and performance metrics
- Walk-forward analysis (train/test splits)
- Monte Carlo simulation with confidence intervals
- SQLite persistence of all results
"""

from __future__ import annotations

import logging
import math
import random
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

from backend.config import DATA_DIR

logger = logging.getLogger("root.backtester")

_DB_PATH = DATA_DIR / "backtests.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS backtest_results (
    id TEXT PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    initial_capital REAL NOT NULL,
    final_capital REAL NOT NULL,
    total_return_pct REAL NOT NULL,
    annualized_return_pct REAL NOT NULL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    max_drawdown_pct REAL,
    win_rate REAL,
    total_trades INTEGER NOT NULL,
    profit_factor REAL,
    calmar_ratio REAL,
    created_at TEXT NOT NULL
);
"""

_INSERT_SQL = """
INSERT INTO backtest_results (
    id, strategy_name, start_date, end_date,
    initial_capital, final_capital, total_return_pct,
    annualized_return_pct, sharpe_ratio, sortino_ratio,
    max_drawdown_pct, win_rate, total_trades, profit_factor,
    calmar_ratio, created_at
) VALUES (
    :id, :strategy_name, :start_date, :end_date,
    :initial_capital, :final_capital, :total_return_pct,
    :annualized_return_pct, :sharpe_ratio, :sortino_ratio,
    :max_drawdown_pct, :win_rate, :total_trades, :profit_factor,
    :calmar_ratio, :created_at
);
"""


@dataclass(frozen=True)
class BacktestResult:
    """Immutable backtest result with all performance metrics."""
    id: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    profit_factor: float
    calmar_ratio: float
    created_at: str


def _compute_sharpe(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe ratio from daily returns."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / 252
    std = float(np.std(excess, ddof=1))
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * math.sqrt(252))


def _compute_sortino(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """Annualized Sortino ratio (downside deviation only)."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / 252
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float("inf") if float(np.mean(excess)) > 0 else 0.0
    downside_std = float(np.std(downside, ddof=1))
    if downside_std == 0:
        return 0.0
    return float(np.mean(excess) / downside_std * math.sqrt(252))


def _compute_max_drawdown(equity_curve: list[float]) -> float:
    """Maximum drawdown as a percentage (0-100)."""
    if len(equity_curve) < 2:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak * 100 if peak > 0 else 0.0
        if drawdown > max_dd:
            max_dd = drawdown
    return max_dd


def _annualized_return(total_return_pct: float, days: int) -> float:
    """Convert total return % to annualized return %."""
    if days <= 0:
        return 0.0
    years = days / 365.25
    if years == 0:
        return 0.0
    if total_return_pct <= -100:
        return -100.0
    ratio = 1 + total_return_pct / 100
    if ratio <= 0:
        return -100.0
    return (ratio ** (1 / years) - 1) * 100


def _simulate_trades(
    signals: list[dict[str, Any]],
    initial_capital: float,
) -> tuple[list[float], list[float], list[float]]:
    """Simulate trades from signals, return (equity_curve, trade_returns, daily_returns).

    Signals: [{"date": str, "symbol": str, "action": "buy"|"sell",
               "price": float, "quantity": int}, ...]
    """
    cash = initial_capital
    positions: dict[str, dict[str, Any]] = {}  # symbol -> {"quantity": int, "avg_price": float}
    equity_curve: list[float] = [initial_capital]
    trade_returns: list[float] = []

    sorted_signals = sorted(signals, key=lambda s: s.get("date", ""))

    for signal in sorted_signals:
        action = signal.get("action", "").lower()
        symbol = signal.get("symbol", "")
        price = float(signal.get("price", 0))
        quantity = int(signal.get("quantity", 0))

        if price <= 0 or quantity <= 0 or not symbol:
            continue

        if action == "buy":
            cost = price * quantity
            if cost > cash:
                # Reduce quantity to what we can afford
                quantity = int(cash / price)
                if quantity <= 0:
                    continue
                cost = price * quantity

            cash -= cost
            current = positions.get(symbol, {"quantity": 0, "avg_price": 0.0})
            total_qty = current["quantity"] + quantity
            if total_qty > 0:
                new_avg = (
                    (current["avg_price"] * current["quantity"] + price * quantity)
                    / total_qty
                )
            else:
                new_avg = price
            positions = {
                **positions,
                symbol: {"quantity": total_qty, "avg_price": new_avg},
            }

        elif action == "sell":
            current = positions.get(symbol)
            if current is None or current["quantity"] <= 0:
                continue
            sell_qty = min(quantity, current["quantity"])
            revenue = price * sell_qty
            trade_pnl = (price - current["avg_price"]) * sell_qty
            trade_return_pct = (
                (price - current["avg_price"]) / current["avg_price"] * 100
                if current["avg_price"] > 0 else 0.0
            )
            trade_returns.append(trade_return_pct)
            cash += revenue

            remaining_qty = current["quantity"] - sell_qty
            if remaining_qty <= 0:
                positions = {k: v for k, v in positions.items() if k != symbol}
            else:
                positions = {
                    **positions,
                    symbol: {"quantity": remaining_qty, "avg_price": current["avg_price"]},
                }

        # Compute portfolio value after this signal
        portfolio_value = cash
        for sym, pos in positions.items():
            # Use last known price for open positions
            portfolio_value += pos["quantity"] * price if sym == symbol else pos["quantity"] * pos["avg_price"]
        equity_curve.append(portfolio_value)

    # Compute daily returns from equity curve
    eq_arr = np.array(equity_curve)
    if len(eq_arr) > 1:
        daily_returns = np.diff(eq_arr) / eq_arr[:-1]
        daily_returns = np.nan_to_num(daily_returns, nan=0.0, posinf=0.0, neginf=0.0)
    else:
        daily_returns = np.array([0.0])

    return equity_curve, trade_returns, daily_returns.tolist()


def _row_to_result(row: sqlite3.Row) -> BacktestResult:
    """Convert a database row to a BacktestResult."""
    return BacktestResult(
        id=row["id"],
        strategy_name=row["strategy_name"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        initial_capital=row["initial_capital"],
        final_capital=row["final_capital"],
        total_return_pct=row["total_return_pct"],
        annualized_return_pct=row["annualized_return_pct"],
        sharpe_ratio=row["sharpe_ratio"],
        sortino_ratio=row["sortino_ratio"],
        max_drawdown_pct=row["max_drawdown_pct"],
        win_rate=row["win_rate"],
        total_trades=row["total_trades"],
        profit_factor=row["profit_factor"],
        calmar_ratio=row["calmar_ratio"],
        created_at=row["created_at"],
    )


class Backtester:
    """Hedge fund backtesting engine with SQLite persistence."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = str(db_path) if db_path else str(_DB_PATH)
        self._conn: Optional[sqlite3.Connection] = None

    def start(self) -> None:
        """Initialize database connection and create tables."""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()
        logger.info("Backtester started — db=%s", self._db_path)

    def stop(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
        logger.info("Backtester stopped")

    def _ensure_connection(self) -> sqlite3.Connection:
        """Return active connection or raise."""
        if self._conn is None:
            raise RuntimeError("Backtester not started — call start() first")
        return self._conn

    def _store_result(self, result: BacktestResult) -> None:
        """Persist a backtest result to SQLite."""
        conn = self._ensure_connection()
        conn.execute(_INSERT_SQL, asdict(result))
        conn.commit()

    def backtest(
        self,
        strategy_name: str,
        signals: list[dict[str, Any]],
        initial_capital: float = 100_000.0,
    ) -> BacktestResult:
        """Run a full backtest on the given signals.

        Args:
            strategy_name: Name of the strategy being tested.
            signals: List of signal dicts with date, symbol, action, price, quantity.
            initial_capital: Starting capital for the simulation.

        Returns:
            BacktestResult with all computed performance metrics.
        """
        if not signals:
            raise ValueError("Cannot backtest with empty signals list")
        if initial_capital <= 0:
            raise ValueError("Initial capital must be positive")

        equity_curve, trade_returns, daily_returns = _simulate_trades(
            signals, initial_capital,
        )

        final_capital = equity_curve[-1]
        total_return_pct = (final_capital - initial_capital) / initial_capital * 100

        # Date range
        sorted_dates = sorted(s.get("date", "") for s in signals if s.get("date"))
        start_date = sorted_dates[0] if sorted_dates else ""
        end_date = sorted_dates[-1] if sorted_dates else ""

        # Trading days
        days = max(len(equity_curve) - 1, 1)
        annualized = _annualized_return(total_return_pct, days)

        # Risk metrics
        daily_arr = np.array(daily_returns)
        sharpe = _compute_sharpe(daily_arr)
        sortino = _compute_sortino(daily_arr)
        max_dd = _compute_max_drawdown(equity_curve)

        # Trade statistics
        total_trades = len(trade_returns)
        winning = [r for r in trade_returns if r > 0]
        losing = [r for r in trade_returns if r <= 0]
        win_rate = len(winning) / max(total_trades, 1) * 100

        gross_profit = sum(winning) if winning else 0.0
        gross_loss = abs(sum(losing)) if losing else 0.0
        profit_factor = gross_profit / max(gross_loss, 0.001)

        calmar = annualized / max(max_dd, 0.001) if max_dd > 0 else 0.0

        result = BacktestResult(
            id=f"bt_{uuid.uuid4().hex[:12]}",
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=round(initial_capital, 2),
            final_capital=round(final_capital, 2),
            total_return_pct=round(total_return_pct, 4),
            annualized_return_pct=round(annualized, 4),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(min(sortino, 99.9999), 4),
            max_drawdown_pct=round(max_dd, 4),
            win_rate=round(win_rate, 2),
            total_trades=total_trades,
            profit_factor=round(profit_factor, 4),
            calmar_ratio=round(calmar, 4),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._store_result(result)
        logger.info(
            "Backtest complete: %s — return=%.2f%%, sharpe=%.2f, trades=%d",
            strategy_name, total_return_pct, sharpe, total_trades,
        )
        return result

    def walk_forward(
        self,
        strategy_name: str,
        signals: list[dict[str, Any]],
        train_pct: float = 0.7,
        initial_capital: float = 100_000.0,
    ) -> list[BacktestResult]:
        """Walk-forward analysis: split signals into train/test and backtest each.

        Args:
            strategy_name: Base strategy name (suffixed with -train/-test).
            signals: Full list of signals.
            train_pct: Fraction of signals for training (0.0-1.0).
            initial_capital: Starting capital for each split.

        Returns:
            List of two BacktestResults: [train_result, test_result].
        """
        if not signals:
            raise ValueError("Cannot walk-forward with empty signals list")
        if not 0.1 <= train_pct <= 0.9:
            raise ValueError("train_pct must be between 0.1 and 0.9")

        sorted_signals = sorted(signals, key=lambda s: s.get("date", ""))
        split_idx = max(1, int(len(sorted_signals) * train_pct))

        train_signals = sorted_signals[:split_idx]
        test_signals = sorted_signals[split_idx:]

        results: list[BacktestResult] = []

        if train_signals:
            train_result = self.backtest(
                strategy_name=f"{strategy_name}-train",
                signals=train_signals,
                initial_capital=initial_capital,
            )
            results.append(train_result)

        if test_signals:
            test_result = self.backtest(
                strategy_name=f"{strategy_name}-test",
                signals=test_signals,
                initial_capital=initial_capital,
            )
            results.append(test_result)

        logger.info(
            "Walk-forward complete: %s — train=%d signals, test=%d signals",
            strategy_name, len(train_signals), len(test_signals),
        )
        return results

    def monte_carlo(
        self,
        backtest_result: BacktestResult,
        simulations: int = 1000,
    ) -> dict[str, Any]:
        """Monte Carlo simulation: resample trade returns for confidence intervals.

        Args:
            backtest_result: A completed backtest result to simulate from.
            simulations: Number of random simulations to run.

        Returns:
            Dict with percentile confidence intervals for final capital.
        """
        if simulations <= 0:
            raise ValueError("simulations must be positive")
        if backtest_result.total_trades == 0:
            return {
                "source_id": backtest_result.id,
                "simulations": simulations,
                "p5": backtest_result.initial_capital,
                "p25": backtest_result.initial_capital,
                "p50": backtest_result.initial_capital,
                "p75": backtest_result.initial_capital,
                "p95": backtest_result.initial_capital,
            }

        # Reconstruct approximate trade returns from the result metrics
        # We use win_rate and profit_factor to generate synthetic trade returns
        total_trades = backtest_result.total_trades
        win_count = int(total_trades * backtest_result.win_rate / 100)
        lose_count = total_trades - win_count

        # Average win/loss from profit factor and total return
        total_return_per_trade = backtest_result.total_return_pct / max(total_trades, 1)

        if win_count > 0 and lose_count > 0:
            # profit_factor = gross_win / gross_loss
            # gross_win = avg_win * win_count
            # gross_loss = avg_loss * lose_count
            # avg_win * win_count = profit_factor * avg_loss * lose_count
            # total_return = avg_win * win_count - avg_loss * lose_count
            pf = max(backtest_result.profit_factor, 0.01)
            avg_loss = abs(total_return_per_trade * total_trades) / (pf * win_count + lose_count) if (pf * win_count + lose_count) > 0 else 1.0
            avg_win = pf * avg_loss * lose_count / max(win_count, 1)
        elif win_count > 0:
            avg_win = total_return_per_trade
            avg_loss = 0.0
        else:
            avg_win = 0.0
            avg_loss = abs(total_return_per_trade) if total_return_per_trade < 0 else 1.0

        # Build synthetic trade return distribution
        trade_returns: list[float] = []
        for _ in range(win_count):
            trade_returns.append(avg_win * (0.5 + random.random()))
        for _ in range(lose_count):
            trade_returns.append(-avg_loss * (0.5 + random.random()))

        if not trade_returns:
            trade_returns = [0.0]

        # Run simulations
        initial = backtest_result.initial_capital
        final_capitals: list[float] = []
        trade_arr = np.array(trade_returns)

        for _ in range(simulations):
            # Resample trades with replacement
            sampled = np.random.choice(trade_arr, size=total_trades, replace=True)
            # Compute final capital from resampled returns (as % of capital)
            capital = initial
            for ret_pct in sampled:
                capital *= (1 + ret_pct / 100)
                if capital <= 0:
                    capital = 0.0
                    break
            final_capitals.append(capital)

        final_arr = np.array(final_capitals)
        result = {
            "source_id": backtest_result.id,
            "simulations": simulations,
            "p5": round(float(np.percentile(final_arr, 5)), 2),
            "p25": round(float(np.percentile(final_arr, 25)), 2),
            "p50": round(float(np.percentile(final_arr, 50)), 2),
            "p75": round(float(np.percentile(final_arr, 75)), 2),
            "p95": round(float(np.percentile(final_arr, 95)), 2),
        }

        logger.info(
            "Monte Carlo complete: %d sims — p50=$%.0f [p5=$%.0f, p95=$%.0f]",
            simulations, result["p50"], result["p5"], result["p95"],
        )
        return result

    def get_results(self, limit: int = 20) -> list[BacktestResult]:
        """Retrieve stored backtest results, most recent first."""
        conn = self._ensure_connection()
        rows = conn.execute(
            "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ?",
            (min(limit, 1000),),
        ).fetchall()
        return [_row_to_result(row) for row in rows]

    def get_result(self, result_id: str) -> Optional[BacktestResult]:
        """Retrieve a single backtest result by ID."""
        conn = self._ensure_connection()
        row = conn.execute(
            "SELECT * FROM backtest_results WHERE id = ?",
            (result_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_result(row)
