"""
0DTE Opening Range Breakout (ORB) Backtesting Script
=====================================================
Simulates SPY 0DTE options trading using the ORB strategy:
- Opening range: 9:30-9:35 ET (first 5 minutes)
- Buy ATM call on break above range high
- Buy ATM put on break below range low
- First breakout only, 1 trade per day max
- TP: 100% gain | SL: 50% loss | Time stop: 3:50 PM
"""

import numpy as np
from dataclasses import dataclass, replace
from typing import Optional


# ── Configuration ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    starting_capital: float = 100.0
    num_trading_days: int = 252
    commission_per_contract: float = 0.65
    tp_pct: float = 1.0       # 100% gain
    sl_pct: float = 0.50      # 50% loss
    time_stop_minute: int = 380  # 3:50 PM = minute 380 from 9:30
    or_minutes: int = 5
    trading_minutes: int = 390   # 9:30 to 4:00 = 390 min
    risk_pct_min: float = 0.05
    risk_pct_max: float = 0.10
    spy_daily_return_mean: float = 0.0004
    spy_daily_return_std: float = 0.011
    or_range_pct_of_daily: tuple = (0.15, 0.25)
    breakout_success_rate: float = 0.42
    gamma_amplification_min: float = 2.0
    gamma_amplification_max: float = 4.0
    reversal_loss_min: float = 0.50
    reversal_loss_max: float = 0.80
    seed: int = 42


@dataclass(frozen=True)
class TradeResult:
    day: int
    date_label: str
    direction: str          # "CALL" or "PUT"
    entry_premium: float
    exit_premium: float
    pnl: float
    pnl_pct: float
    exit_reason: str        # "TP", "SL", "TIME_STOP"
    capital_before: float
    capital_after: float


@dataclass(frozen=True)
class IntradayPath:
    minutes: np.ndarray      # price path relative to open (pct)
    or_high_pct: float       # opening range high (pct from open)
    or_low_pct: float        # opening range low (pct from open)
    daily_return_pct: float


# ── Simulation Engine ─────────────────────────────────────────────────────

def generate_intraday_path(
    rng: np.random.Generator,
    config: Config,
) -> IntradayPath:
    """Generate a realistic intraday price path as pct moves from open."""
    daily_return = rng.normal(config.spy_daily_return_mean, config.spy_daily_return_std)
    daily_range_pct = abs(daily_return) + rng.exponential(0.005)
    daily_range_pct = max(daily_range_pct, 0.003)

    or_frac = rng.uniform(*config.or_range_pct_of_daily)
    or_range = daily_range_pct * or_frac

    total_minutes = config.trading_minutes
    drift_per_min = daily_return / total_minutes
    vol_per_min = config.spy_daily_return_std / np.sqrt(total_minutes)

    increments = rng.normal(drift_per_min, vol_per_min, size=total_minutes)

    mean_reversion_strength = 0.002
    path = np.zeros(total_minutes)
    path[0] = increments[0]
    for i in range(1, total_minutes):
        path[i] = path[i - 1] + increments[i] - mean_reversion_strength * path[i - 1]

    or_segment = path[:config.or_minutes]
    or_high = np.max(or_segment)
    or_low = np.min(or_segment)
    actual_or_range = or_high - or_low

    if actual_or_range < 1e-8:
        or_high = or_segment[-1] + or_range / 2
        or_low = or_segment[-1] - or_range / 2
    else:
        scale = or_range / actual_or_range
        or_center = (or_high + or_low) / 2
        or_high = or_center + (or_high - or_center) * scale
        or_low = or_center + (or_low - or_center) * scale

    return IntradayPath(
        minutes=path,
        or_high_pct=or_high,
        or_low_pct=or_low,
        daily_return_pct=daily_return,
    )


def simulate_option_pnl(
    path: IntradayPath,
    config: Config,
    rng: np.random.Generator,
) -> Optional[tuple]:
    """
    Simulate a single day's ORB trade.
    Returns (pnl_pct, exit_reason, direction) or None if no breakout.
    """
    or_high = path.or_high_pct
    or_low = path.or_low_pct
    or_range = or_high - or_low

    if or_range < 1e-8:
        return None

    direction = None
    breakout_level = None
    breakout_minute = None

    for minute in range(config.or_minutes, config.time_stop_minute):
        price = path.minutes[minute]
        if price > or_high:
            direction = "CALL"
            breakout_level = or_high
            breakout_minute = minute
            break
        elif price < or_low:
            direction = "PUT"
            breakout_level = or_low
            breakout_minute = minute
            break

    if direction is None:
        return None

    is_successful = rng.random() < config.breakout_success_rate
    gamma_amp = rng.uniform(config.gamma_amplification_min, config.gamma_amplification_max)
    reversal_loss = rng.uniform(config.reversal_loss_min, config.reversal_loss_max)

    remaining_minutes = config.time_stop_minute - breakout_minute
    if remaining_minutes <= 0:
        return None

    peak_favorable_pct = 0.0
    peak_adverse_pct = 0.0

    for minute in range(breakout_minute + 1, config.time_stop_minute + 1):
        if minute >= len(path.minutes):
            break
        price = path.minutes[minute]

        if direction == "CALL":
            move_from_breakout = (price - breakout_level) / or_range
        else:
            move_from_breakout = (breakout_level - price) / or_range

        favorable = max(0.0, move_from_breakout)
        adverse = max(0.0, -move_from_breakout)

        option_gain_pct = favorable * gamma_amp
        option_loss_pct = adverse * reversal_loss

        if option_gain_pct >= config.tp_pct:
            return (config.tp_pct, "TP", direction)

        if option_loss_pct >= config.sl_pct:
            return (-config.sl_pct, "SL", direction)

        peak_favorable_pct = max(peak_favorable_pct, option_gain_pct)
        peak_adverse_pct = max(peak_adverse_pct, option_loss_pct)

    if is_successful and peak_favorable_pct > 0.2:
        final_pnl = peak_favorable_pct * rng.uniform(0.4, 0.8)
    elif peak_adverse_pct > 0.1:
        final_pnl = -peak_adverse_pct * rng.uniform(0.5, 1.0)
    else:
        final_pnl = rng.uniform(-0.15, 0.10)

    final_pnl = max(-config.sl_pct, min(config.tp_pct, final_pnl))
    return (final_pnl, "TIME_STOP", direction)


def calculate_position_size(
    capital: float,
    config: Config,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """Calculate position size using Kelly criterion, bounded by config limits."""
    if avg_loss == 0 or avg_win == 0:
        return capital * config.risk_pct_min

    b = avg_win / abs(avg_loss)
    kelly = (win_rate * b - (1 - win_rate)) / b if b > 0 else 0
    kelly = max(0, min(kelly, 0.25))
    kelly_fraction = 0.5 * kelly

    risk_pct = max(config.risk_pct_min, min(config.risk_pct_max, kelly_fraction))
    return capital * risk_pct


# ── Backtest Runner ───────────────────────────────────────────────────────

def run_backtest(config: Config) -> tuple:
    """Run the full backtest simulation. Returns (trades, equity_curve)."""
    rng = np.random.default_rng(config.seed)
    capital = config.starting_capital
    trades = []
    equity_curve = [capital]

    running_wins = 0
    running_losses = 0
    running_win_total = 0.0
    running_loss_total = 0.0

    for day in range(config.num_trading_days):
        path = generate_intraday_path(rng, config)
        result = simulate_option_pnl(path, config, rng)

        if result is None:
            equity_curve.append(capital)
            continue

        pnl_pct, exit_reason, direction = result

        if running_wins + running_losses >= 10:
            win_rate = running_wins / (running_wins + running_losses)
            avg_w = running_win_total / max(1, running_wins)
            avg_l = running_loss_total / max(1, running_losses)
        else:
            win_rate = 0.42
            avg_w = 0.80
            avg_l = 0.40

        premium = calculate_position_size(capital, config, win_rate, avg_w, avg_l)
        premium = max(premium, 0.50)

        num_contracts = max(1, int(premium / 2.0))
        total_commission = config.commission_per_contract * num_contracts * 2

        dollar_pnl = premium * pnl_pct - total_commission
        new_capital = capital + dollar_pnl

        month_num = (day // 21) + 1
        date_label = f"M{month_num:02d}-D{(day % 21) + 1:02d}"

        trade = TradeResult(
            day=day,
            date_label=date_label,
            direction=direction,
            entry_premium=premium,
            exit_premium=premium * (1 + pnl_pct),
            pnl=dollar_pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
            capital_before=capital,
            capital_after=new_capital,
        )
        trades.append(trade)

        if pnl_pct > 0:
            running_wins += 1
            running_win_total += pnl_pct
        else:
            running_losses += 1
            running_loss_total += abs(pnl_pct)

        capital = new_capital
        equity_curve.append(capital)

    return trades, equity_curve


# ── Analytics ─────────────────────────────────────────────────────────────

def compute_metrics(trades: list, equity_curve: list, config: Config) -> dict:
    """Compute all backtest performance metrics."""
    if not trades:
        return {"error": "No trades executed"}

    pnls = np.array([t.pnl for t in trades])
    pnl_pcts = np.array([t.pnl_pct for t in trades])
    wins = pnls > 0
    losses = pnls <= 0

    total_return = (equity_curve[-1] - config.starting_capital) / config.starting_capital
    num_trades = len(trades)
    win_rate = np.sum(wins) / num_trades if num_trades > 0 else 0
    avg_win = np.mean(pnl_pcts[wins]) if np.any(wins) else 0
    avg_loss = np.mean(pnl_pcts[losses]) if np.any(losses) else 0

    equity = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / running_max
    max_drawdown = np.min(drawdowns)

    daily_returns = np.diff(equity) / equity[:-1]
    daily_returns = daily_returns[daily_returns != 0]
    sharpe = (
        np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
        if len(daily_returns) > 1 and np.std(daily_returns) > 0
        else 0
    )

    exit_counts = {}
    for t in trades:
        exit_counts[t.exit_reason] = exit_counts.get(t.exit_reason, 0) + 1

    direction_counts = {}
    for t in trades:
        direction_counts[t.direction] = direction_counts.get(t.direction, 0) + 1

    monthly_pnl = {}
    for t in trades:
        month = t.date_label.split("-")[0]
        monthly_pnl[month] = monthly_pnl.get(month, 0) + t.pnl

    return {
        "total_return_pct": total_return * 100,
        "final_capital": equity_curve[-1],
        "num_trades": num_trades,
        "win_rate_pct": win_rate * 100,
        "avg_win_pct": avg_win * 100,
        "avg_loss_pct": avg_loss * 100,
        "profit_factor": (
            abs(np.sum(pnls[wins]) / np.sum(pnls[losses]))
            if np.any(losses) and np.sum(pnls[losses]) != 0
            else float("inf")
        ),
        "max_drawdown_pct": max_drawdown * 100,
        "sharpe_ratio": sharpe,
        "exit_counts": exit_counts,
        "direction_counts": direction_counts,
        "monthly_pnl": monthly_pnl,
        "total_commissions": sum(
            config.commission_per_contract * max(1, int(t.entry_premium / 2.0)) * 2
            for t in trades
        ),
    }


def print_equity_curve_ascii(equity_curve: list, width: int = 60, height: int = 20):
    """Render a simple ASCII equity curve."""
    equity = np.array(equity_curve)
    n = len(equity)
    if n <= 1:
        return

    step = max(1, n // width)
    sampled = equity[::step][:width]
    min_val = np.min(sampled)
    max_val = np.max(sampled)
    val_range = max_val - min_val if max_val > min_val else 1.0

    print("\n  Equity Curve")
    print("  " + "=" * (width + 8))

    for row in range(height, -1, -1):
        threshold = min_val + (row / height) * val_range
        label = f"${threshold:7.2f} |"
        line = []
        for val in sampled:
            if val >= threshold:
                line.append("#")
            else:
                line.append(" ")
        if row % 5 == 0:
            print(f"  {label}{''.join(line)}")
        else:
            print(f"          |{''.join(line)}")

    print(f"          +{''.join(['-'] * len(sampled))}")
    print(f"           Day 1{' ' * (len(sampled) - 10)}Day {n - 1}")


def print_report(metrics: dict, equity_curve: list, config: Config):
    """Print formatted backtest report."""
    print("\n" + "=" * 65)
    print("  0DTE OPENING RANGE BREAKOUT (ORB) - BACKTEST RESULTS")
    print("=" * 65)

    print(f"\n  Starting Capital:      ${config.starting_capital:.2f}")
    print(f"  Final Capital:         ${metrics['final_capital']:.2f}")
    print(f"  Total Return:          {metrics['total_return_pct']:+.2f}%")
    print(f"  Total Commissions:     ${metrics['total_commissions']:.2f}")

    print(f"\n  {'─' * 40}")
    print(f"  Number of Trades:      {metrics['num_trades']}")
    print(f"  Win Rate:              {metrics['win_rate_pct']:.1f}%")
    print(f"  Avg Win:               {metrics['avg_win_pct']:+.1f}%")
    print(f"  Avg Loss:              {metrics['avg_loss_pct']:+.1f}%")
    print(f"  Profit Factor:         {metrics['profit_factor']:.2f}")
    print(f"  Sharpe Ratio:          {metrics['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:          {metrics['max_drawdown_pct']:.2f}%")

    print(f"\n  {'─' * 40}")
    print("  Exit Breakdown:")
    for reason, count in sorted(metrics["exit_counts"].items()):
        pct = count / metrics["num_trades"] * 100
        print(f"    {reason:12s}  {count:4d}  ({pct:.1f}%)")

    print(f"\n  Direction Breakdown:")
    for d, count in sorted(metrics["direction_counts"].items()):
        pct = count / metrics["num_trades"] * 100
        print(f"    {d:12s}  {count:4d}  ({pct:.1f}%)")

    print(f"\n  {'─' * 40}")
    print("  Monthly P&L Breakdown:")
    print(f"  {'Month':>7s}  {'P&L':>10s}  {'Bar':>20s}")
    max_abs = max(abs(v) for v in metrics["monthly_pnl"].values()) if metrics["monthly_pnl"] else 1
    for month in sorted(metrics["monthly_pnl"].keys()):
        pnl = metrics["monthly_pnl"][month]
        bar_len = int(abs(pnl) / max_abs * 15) if max_abs > 0 else 0
        bar = ("+" * bar_len) if pnl >= 0 else ("-" * bar_len)
        color_indicator = " " if pnl >= 0 else " "
        print(f"  {month:>7s}  ${pnl:>9.2f} {color_indicator}{bar}")

    print_equity_curve_ascii(equity_curve)

    print(f"\n{'=' * 65}")
    print("  Simulation complete. Seed={}, Days={}".format(config.seed, config.num_trading_days))
    print(f"{'=' * 65}\n")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    config = Config()
    trades, equity_curve = run_backtest(config)
    metrics = compute_metrics(trades, equity_curve, config)
    print_report(metrics, equity_curve, config)


if __name__ == "__main__":
    main()
