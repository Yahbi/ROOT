"""
Funding Rate Arbitrage Backtest

Strategy: Delta-neutral position (Long Spot + Short Perpetual)
- Enter when funding rate > 0.03% (collect funding from shorts)
- Exit when funding rate normalizes below 0.01%
- Stop-loss if basis diverges > 2%
- Funding collected every 8 hours (3x per day)

Simulated funding rate data based on realistic crypto market parameters.
"""

import random
import math
from dataclasses import dataclass
from typing import List, Tuple


# ─── Configuration ───────────────────────────────────────────────────────────

SEED = 42
STARTING_CAPITAL = 100.0
ENTRY_THRESHOLD = 0.0003      # 0.03%
EXIT_THRESHOLD = 0.0001       # 0.01%
BASIS_STOP = 0.02             # 2%
TRADING_FEE_RATE = 0.001      # 0.1% per side
SLIPPAGE_RATE = 0.0005        # 0.05%
ROUND_TRIP_COST = (TRADING_FEE_RATE + SLIPPAGE_RATE) * 2  # entry + exit

DAYS = 365
PERIODS_PER_DAY = 3           # every 8 hours
TOTAL_PERIODS = DAYS * PERIODS_PER_DAY

# Funding rate simulation parameters
FUNDING_MEAN = 0.0002         # 0.02%
FUNDING_STD = 0.0003          # 0.03%
FUNDING_MIN = -0.001          # -0.1%
FUNDING_MAX = 0.003           # 0.3%
SPIKE_PROBABILITY = 0.03      # 3% chance of a spike per period
SPIKE_MEAN = 0.001            # 0.1% spike center
SPIKE_STD = 0.0005            # 0.05% spike spread

# Basis simulation parameters
BASIS_MEAN = 0.001            # 0.1% average basis
BASIS_STD = 0.003             # 0.3% std
BASIS_MEAN_REVERSION = 0.1    # mean-reversion speed

RISK_FREE_RATE = 0.05         # 5% annual for Sharpe calculation


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FundingPeriod:
    period_index: int
    day: int
    period_in_day: int        # 0, 1, or 2
    funding_rate: float
    basis: float              # spot vs perp price difference


@dataclass(frozen=True)
class Trade:
    entry_period: int
    exit_period: int
    entry_day: int
    exit_day: int
    funding_collected: float  # total funding earned
    entry_cost: float         # round-trip trading cost
    pnl: float                # net P&L
    exit_reason: str          # "normalization" or "basis_stop"


@dataclass(frozen=True)
class BacktestResult:
    total_return_pct: float
    total_pnl: float
    num_trades: int
    win_rate: float
    max_drawdown_pct: float
    sharpe_ratio: float
    final_equity: float
    equity_curve: List[float]
    daily_returns: List[float]
    monthly_returns: List[Tuple[int, float]]
    trades: List[Trade]


# ─── Data Generation ────────────────────────────────────────────────────────

def generate_funding_rates(rng: random.Random) -> List[FundingPeriod]:
    """Generate realistic simulated funding rate data for 365 days."""
    periods: List[FundingPeriod] = []
    prev_funding = FUNDING_MEAN
    prev_basis = BASIS_MEAN

    for i in range(TOTAL_PERIODS):
        day = i // PERIODS_PER_DAY
        period_in_day = i % PERIODS_PER_DAY

        # Funding rate: AR(1) process with occasional spikes
        is_spike = rng.random() < SPIKE_PROBABILITY
        if is_spike:
            raw_funding = rng.gauss(SPIKE_MEAN, SPIKE_STD)
        else:
            # Mean-reverting with autocorrelation
            innovation = rng.gauss(0, FUNDING_STD * 0.5)
            raw_funding = 0.7 * prev_funding + 0.3 * FUNDING_MEAN + innovation

        funding_rate = max(FUNDING_MIN, min(FUNDING_MAX, raw_funding))

        # Basis: mean-reverting, correlated with funding
        basis_innovation = rng.gauss(0, BASIS_STD * 0.3)
        basis = (
            prev_basis * (1 - BASIS_MEAN_REVERSION)
            + BASIS_MEAN * BASIS_MEAN_REVERSION
            + basis_innovation
            + funding_rate * 2  # basis correlates with funding
        )

        period = FundingPeriod(
            period_index=i,
            day=day,
            period_in_day=period_in_day,
            funding_rate=funding_rate,
            basis=basis,
        )
        periods.append(period)
        prev_funding = funding_rate
        prev_basis = basis

    return periods


# ─── Backtest Engine ─────────────────────────────────────────────────────────

def run_backtest(periods: List[FundingPeriod]) -> BacktestResult:
    """Execute the funding rate arbitrage backtest."""
    equity = STARTING_CAPITAL
    peak_equity = equity
    max_drawdown = 0.0

    trades: List[Trade] = []
    equity_curve: List[float] = [equity]
    daily_equities: List[float] = [equity]

    # Position state (mutable within function scope only)
    in_position = False
    entry_period_idx = 0
    entry_day = 0
    accumulated_funding = 0.0

    for period in periods:
        if in_position:
            # Collect funding (we are short perp, positive funding = we receive)
            funding_payment = equity * period.funding_rate
            accumulated_funding += funding_payment
            equity += funding_payment

            # Check basis stop-loss
            if abs(period.basis) > BASIS_STOP:
                exit_cost = equity * ROUND_TRIP_COST
                pnl = accumulated_funding - exit_cost
                equity -= exit_cost

                trade = Trade(
                    entry_period=entry_period_idx,
                    exit_period=period.period_index,
                    entry_day=entry_day,
                    exit_day=period.day,
                    funding_collected=accumulated_funding,
                    entry_cost=exit_cost,
                    pnl=pnl,
                    exit_reason="basis_stop",
                )
                trades.append(trade)
                in_position = False
                accumulated_funding = 0.0

            # Check exit threshold
            elif period.funding_rate < EXIT_THRESHOLD:
                exit_cost = equity * ROUND_TRIP_COST
                pnl = accumulated_funding - exit_cost
                equity -= exit_cost

                trade = Trade(
                    entry_period=entry_period_idx,
                    exit_period=period.period_index,
                    entry_day=entry_day,
                    exit_day=period.day,
                    funding_collected=accumulated_funding,
                    entry_cost=exit_cost,
                    pnl=pnl,
                    exit_reason="normalization",
                )
                trades.append(trade)
                in_position = False
                accumulated_funding = 0.0

        else:
            # Check entry condition
            if period.funding_rate > ENTRY_THRESHOLD:
                entry_cost = equity * (TRADING_FEE_RATE + SLIPPAGE_RATE)
                equity -= entry_cost
                in_position = True
                entry_period_idx = period.period_index
                entry_day = period.day
                accumulated_funding = -entry_cost  # account for entry cost

        # Track equity
        equity_curve.append(equity)
        peak_equity = max(peak_equity, equity)
        drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)

        # Track daily equity (end of last period each day)
        if period.period_in_day == PERIODS_PER_DAY - 1:
            daily_equities.append(equity)

    # Close any open position at end
    if in_position:
        exit_cost = equity * ROUND_TRIP_COST
        pnl = accumulated_funding - exit_cost
        equity -= exit_cost

        last_period = periods[-1]
        trade = Trade(
            entry_period=entry_period_idx,
            exit_period=last_period.period_index,
            entry_day=entry_day,
            exit_day=last_period.day,
            funding_collected=accumulated_funding,
            entry_cost=exit_cost,
            pnl=pnl,
            exit_reason="end_of_backtest",
        )
        trades.append(trade)
        equity_curve.append(equity)

    # Calculate metrics
    total_pnl = equity - STARTING_CAPITAL
    total_return_pct = (total_pnl / STARTING_CAPITAL) * 100
    winning_trades = [t for t in trades if t.pnl > 0]
    win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0

    # Daily returns for Sharpe calculation
    daily_returns = _compute_daily_returns(daily_equities)
    sharpe = _compute_sharpe(daily_returns)

    # Monthly returns
    monthly_returns = _compute_monthly_returns(daily_equities)

    return BacktestResult(
        total_return_pct=total_return_pct,
        total_pnl=total_pnl,
        num_trades=len(trades),
        win_rate=win_rate,
        max_drawdown_pct=max_drawdown * 100,
        sharpe_ratio=sharpe,
        final_equity=equity,
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        monthly_returns=monthly_returns,
        trades=trades,
    )


def _compute_daily_returns(daily_equities: List[float]) -> List[float]:
    """Compute daily percentage returns from equity series."""
    returns = []
    for i in range(1, len(daily_equities)):
        prev = daily_equities[i - 1]
        if prev > 0:
            ret = (daily_equities[i] - prev) / prev
            returns.append(ret)
    return returns


def _compute_sharpe(daily_returns: List[float]) -> float:
    """Compute annualized Sharpe ratio."""
    if len(daily_returns) < 2:
        return 0.0

    mean_ret = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std_ret = math.sqrt(variance) if variance > 0 else 0.0

    if std_ret == 0:
        return 0.0

    daily_rf = RISK_FREE_RATE / 365
    excess_return = mean_ret - daily_rf
    daily_sharpe = excess_return / std_ret
    annualized_sharpe = daily_sharpe * math.sqrt(365)
    return annualized_sharpe


def _compute_monthly_returns(daily_equities: List[float]) -> List[Tuple[int, float]]:
    """Compute monthly returns (approximately 30-day periods)."""
    monthly: List[Tuple[int, float]] = []
    days_per_month = 30

    for month in range(12):
        start_idx = month * days_per_month
        end_idx = min((month + 1) * days_per_month, len(daily_equities) - 1)

        if start_idx >= len(daily_equities) or end_idx <= start_idx:
            break

        start_eq = daily_equities[start_idx]
        end_eq = daily_equities[end_idx]

        if start_eq > 0:
            ret = ((end_eq - start_eq) / start_eq) * 100
            monthly.append((month + 1, ret))

    return monthly


# ─── Reporting ───────────────────────────────────────────────────────────────

def print_report(result: BacktestResult) -> None:
    """Print formatted backtest results."""
    print("=" * 65)
    print("  FUNDING RATE ARBITRAGE BACKTEST RESULTS")
    print("=" * 65)
    print()

    print("--- Strategy Parameters ---")
    print(f"  Starting Capital:    ${STARTING_CAPITAL:.2f}")
    print(f"  Entry Threshold:     {ENTRY_THRESHOLD * 100:.2f}%")
    print(f"  Exit Threshold:      {EXIT_THRESHOLD * 100:.2f}%")
    print(f"  Basis Stop-Loss:     {BASIS_STOP * 100:.1f}%")
    print(f"  Trading Fee:         {TRADING_FEE_RATE * 100:.1f}% per side")
    print(f"  Slippage:            {SLIPPAGE_RATE * 100:.2f}%")
    print(f"  Round-Trip Cost:     {ROUND_TRIP_COST * 100:.2f}%")
    print(f"  Simulation Period:   {DAYS} days")
    print()

    print("--- Performance Summary ---")
    print(f"  Final Equity:        ${result.final_equity:.2f}")
    print(f"  Total P&L:           ${result.total_pnl:.2f}")
    print(f"  Total Return:        {result.total_return_pct:.2f}%")
    print(f"  Number of Trades:    {result.num_trades}")
    print(f"  Win Rate:            {result.win_rate:.1f}%")
    print(f"  Max Drawdown:        {result.max_drawdown_pct:.2f}%")
    print(f"  Sharpe Ratio:        {result.sharpe_ratio:.2f}")
    print()

    # Trade breakdown by exit reason
    norm_exits = [t for t in result.trades if t.exit_reason == "normalization"]
    basis_stops = [t for t in result.trades if t.exit_reason == "basis_stop"]
    eob_exits = [t for t in result.trades if t.exit_reason == "end_of_backtest"]

    print("--- Trade Breakdown ---")
    print(f"  Normalization Exits: {len(norm_exits)}")
    print(f"  Basis Stop Exits:   {len(basis_stops)}")
    print(f"  End-of-Backtest:    {len(eob_exits)}")
    print()

    if result.trades:
        pnls = [t.pnl for t in result.trades]
        avg_pnl = sum(pnls) / len(pnls)
        best_trade = max(pnls)
        worst_trade = min(pnls)
        durations = [
            (t.exit_period - t.entry_period) for t in result.trades
        ]
        avg_duration_periods = sum(durations) / len(durations)
        avg_duration_days = avg_duration_periods / PERIODS_PER_DAY

        print("--- Trade Statistics ---")
        print(f"  Average P&L:         ${avg_pnl:.4f}")
        print(f"  Best Trade:          ${best_trade:.4f}")
        print(f"  Worst Trade:         ${worst_trade:.4f}")
        print(f"  Avg Duration:        {avg_duration_days:.1f} days ({avg_duration_periods:.0f} periods)")
        print()

    print("--- Monthly Returns ---")
    for month_num, ret in result.monthly_returns:
        bar_len = int(abs(ret) * 10)
        bar_char = "+" if ret >= 0 else "-"
        bar = bar_char * min(bar_len, 40)
        print(f"  Month {month_num:2d}:  {ret:+7.2f}%  {bar}")
    print()

    # Equity curve summary (sampled points)
    print("--- Equity Curve (sampled) ---")
    curve = result.equity_curve
    sample_points = 20
    step = max(1, len(curve) // sample_points)
    for i in range(0, len(curve), step):
        day = i // PERIODS_PER_DAY
        eq = curve[i]
        bar_len = int((eq / STARTING_CAPITAL) * 30)
        bar = "#" * min(bar_len, 60)
        print(f"  Day {day:4d}: ${eq:8.2f}  {bar}")
    print()

    print("=" * 65)
    print("  Backtest complete.")
    print("=" * 65)


# ─── Funding Rate Distribution Analysis ─────────────────────────────────────

def print_funding_stats(periods: List[FundingPeriod]) -> None:
    """Print statistics about the generated funding rate data."""
    rates = [p.funding_rate for p in periods]

    mean_rate = sum(rates) / len(rates)
    sorted_rates = sorted(rates)
    median_rate = sorted_rates[len(sorted_rates) // 2]
    positive_count = sum(1 for r in rates if r > 0)
    above_entry = sum(1 for r in rates if r > ENTRY_THRESHOLD)

    print()
    print("--- Simulated Funding Rate Statistics ---")
    print(f"  Total Periods:       {len(rates)}")
    print(f"  Mean Rate:           {mean_rate * 100:.4f}%")
    print(f"  Median Rate:         {median_rate * 100:.4f}%")
    print(f"  Min Rate:            {min(rates) * 100:.4f}%")
    print(f"  Max Rate:            {max(rates) * 100:.4f}%")
    print(f"  Positive Rate:       {positive_count}/{len(rates)} ({positive_count / len(rates) * 100:.1f}%)")
    print(f"  Above Entry (0.03%): {above_entry}/{len(rates)} ({above_entry / len(rates) * 100:.1f}%)")
    print()


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    rng = random.Random(SEED)
    periods = generate_funding_rates(rng)

    print_funding_stats(periods)

    result = run_backtest(periods)
    print_report(result)


if __name__ == "__main__":
    main()
