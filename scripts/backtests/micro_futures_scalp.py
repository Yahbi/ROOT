"""
Micro Futures EMA/VWAP Scalping Strategy Backtest
==================================================
Instrument: MES (Micro E-mini S&P 500), $5 per point
Timeframe: 5-minute bars, 252 trading days
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
POINT_VALUE = 5.0          # $ per point for MES
COMMISSION_RT = 1.24       # round-trip commission
SLIPPAGE_PTS = 0.25        # points per trade (each side)
STARTING_CAPITAL = 500.0
BARS_PER_DAY = 72          # 9:30-15:25 in 5-min increments
TRADING_DAYS = 252
MAX_TRADES_PER_DAY = 4
SEED = 42

# Position sizing thresholds: (equity_threshold, contracts)
POSITION_TIERS = [
    (5000, 4),
    (2500, 3),
    (1000, 2),
    (0, 1),
]


# ---------------------------------------------------------------------------
# Data Generation
# ---------------------------------------------------------------------------
def generate_mes_data(n_days: int, seed: int) -> pd.DataFrame:
    """Generate realistic MES 5-minute bar data using geometric Brownian motion
    with intraday mean reversion, opening spike, lunch lull, and power hour."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    price = 4500.0  # starting price

    for day_idx in range(n_days):
        day_open = price
        # daily drift is small and random
        daily_drift = rng.normal(0.0002, 0.001)
        # daily target range 40-80 pts
        daily_vol = rng.uniform(40, 80) / np.sqrt(BARS_PER_DAY) / price

        cum_volume = 0.0
        cum_vp = 0.0  # volume * price (for VWAP)

        for bar_idx in range(BARS_PER_DAY):
            frac = bar_idx / BARS_PER_DAY

            # Volatility multiplier by time-of-day
            if frac < 0.10:          # first ~36 min: opening spike
                vol_mult = 1.8
            elif 0.35 < frac < 0.55: # lunch doldrums
                vol_mult = 0.6
            elif frac > 0.85:        # power hour (last ~45 min)
                vol_mult = 1.4
            else:
                vol_mult = 1.0

            # Mean-reversion toward day open (keeps range bounded)
            reversion = -0.15 * (price - day_open) / day_open

            sigma = daily_vol * vol_mult
            ret = daily_drift / BARS_PER_DAY + reversion / BARS_PER_DAY + sigma * rng.standard_normal()
            bar_mid = price * (1 + ret)

            # Generate OHLC from mid price
            bar_range = max(0.25, abs(rng.normal(3.0, 2.0)))
            half = bar_range / 2
            if rng.random() > 0.5:
                open_p = bar_mid - half * rng.uniform(0.2, 0.8)
                close_p = bar_mid + half * rng.uniform(0.2, 0.8)
            else:
                open_p = bar_mid + half * rng.uniform(0.2, 0.8)
                close_p = bar_mid - half * rng.uniform(0.2, 0.8)

            high_p = max(open_p, close_p) + half * rng.uniform(0.1, 0.5)
            low_p = min(open_p, close_p) - half * rng.uniform(0.1, 0.5)

            # Volume profile: U-shaped
            base_vol = 800
            vol_shape = 1.0 + 1.5 * ((frac - 0.5) ** 2) / 0.25
            volume = int(base_vol * vol_shape * rng.uniform(0.7, 1.3))

            cum_volume += volume
            cum_vp += volume * close_p
            vwap = cum_vp / cum_volume if cum_volume > 0 else close_p

            rows.append({
                "day": day_idx,
                "bar": bar_idx,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": volume,
                "vwap": round(vwap, 2),
            })

            price = close_p

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Indicator Calculation
# ---------------------------------------------------------------------------
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute EMA(9), EMA(20), EMA(50), RSI(14), ATR(14) per day."""
    results = []
    for _, day_df in df.groupby("day"):
        day_data = day_df.copy()
        close = day_data["close"]

        day_data = day_data.assign(
            ema9=close.ewm(span=9, adjust=False).mean(),
            ema20=close.ewm(span=20, adjust=False).mean(),
            ema50=close.ewm(span=50, adjust=False).mean(),
        )

        # RSI(14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(span=14, adjust=False).mean()
        avg_loss = loss.ewm(span=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        day_data = day_data.assign(rsi=100 - (100 / (1 + rs)))

        # ATR(14)
        tr = pd.concat([
            day_data["high"] - day_data["low"],
            (day_data["high"] - close.shift(1)).abs(),
            (day_data["low"] - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        day_data = day_data.assign(atr=tr.ewm(span=14, adjust=False).mean())

        results.append(day_data)

    return pd.concat(results, ignore_index=True)


# ---------------------------------------------------------------------------
# Trade Dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Trade:
    day: int
    bar: int
    direction: str       # "LONG" or "SHORT"
    entry_price: float
    stop_price: float
    target_price: float
    contracts: int


@dataclass(frozen=True)
class ClosedTrade:
    day: int
    entry_bar: int
    exit_bar: int
    direction: str
    entry_price: float
    exit_price: float
    contracts: int
    pnl: float           # net P&L after costs
    result: str           # "WIN", "LOSS", "EOD"


# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------
def get_position_size(equity: float) -> int:
    """Determine contract count based on equity tier."""
    for threshold, contracts in POSITION_TIERS:
        if equity >= threshold:
            return contracts
    return 1


def run_backtest(df: pd.DataFrame) -> tuple[list[ClosedTrade], list[float]]:
    """Execute the strategy and return closed trades + daily equity curve."""
    equity = STARTING_CAPITAL
    trades: list[ClosedTrade] = []
    daily_equity: list[float] = [equity]

    for day_idx in range(TRADING_DAYS):
        day_df = df[df["day"] == day_idx].reset_index(drop=True)
        if len(day_df) < 51:  # need at least 50 bars for EMA50 warmup
            daily_equity.append(equity)
            continue

        day_trades = 0
        open_trade: Optional[Trade] = None
        day_pnl = 0.0

        for i in range(51, len(day_df)):
            row = day_df.iloc[i]
            prev = day_df.iloc[i - 1]

            # --- Check exit on open trade ---
            if open_trade is not None:
                hit_stop = False
                hit_target = False

                if open_trade.direction == "LONG":
                    hit_stop = row["low"] <= open_trade.stop_price
                    hit_target = row["high"] >= open_trade.target_price
                else:
                    hit_stop = row["high"] >= open_trade.stop_price
                    hit_target = row["low"] <= open_trade.target_price

                # End-of-day forced exit (last bar)
                eod_exit = (i >= len(day_df) - 1)

                if hit_stop or hit_target or eod_exit:
                    if hit_target and hit_stop:
                        # Assume stop hit first if bar opened against us
                        if open_trade.direction == "LONG":
                            exit_price = open_trade.stop_price if row["open"] < prev["close"] else open_trade.target_price
                        else:
                            exit_price = open_trade.stop_price if row["open"] > prev["close"] else open_trade.target_price
                    elif hit_target:
                        exit_price = open_trade.target_price
                    elif hit_stop:
                        exit_price = open_trade.stop_price
                    else:
                        exit_price = row["close"]

                    # Apply slippage on exit
                    if open_trade.direction == "LONG":
                        exit_price -= SLIPPAGE_PTS
                    else:
                        exit_price += SLIPPAGE_PTS

                    # Calculate P&L
                    if open_trade.direction == "LONG":
                        raw_pnl = (exit_price - open_trade.entry_price) * POINT_VALUE * open_trade.contracts
                    else:
                        raw_pnl = (open_trade.entry_price - exit_price) * POINT_VALUE * open_trade.contracts

                    net_pnl = raw_pnl - COMMISSION_RT * open_trade.contracts

                    if hit_target and not hit_stop:
                        result = "WIN"
                    elif hit_stop:
                        result = "LOSS"
                    else:
                        result = "EOD"

                    closed = ClosedTrade(
                        day=day_idx,
                        entry_bar=open_trade.bar,
                        exit_bar=i,
                        direction=open_trade.direction,
                        entry_price=open_trade.entry_price,
                        exit_price=round(exit_price, 2),
                        contracts=open_trade.contracts,
                        pnl=round(net_pnl, 2),
                        result=result,
                    )
                    trades.append(closed)
                    day_pnl += net_pnl
                    open_trade = None

            # --- Check entry signals (no open position, under daily limit) ---
            if open_trade is None and day_trades < MAX_TRADES_PER_DAY and i < len(day_df) - 2:
                ema9 = row["ema9"]
                ema20 = row["ema20"]
                ema50 = row["ema50"]
                vwap = row["vwap"]
                rsi = row["rsi"]
                atr = row["atr"]
                prev_ema9 = prev["ema9"]
                prev_vwap = prev["vwap"]

                if pd.isna(rsi) or pd.isna(atr) or atr < 0.5:
                    continue

                contracts = get_position_size(equity + day_pnl)

                # LONG signal
                ema9_crosses_above_vwap = prev_ema9 <= prev_vwap and ema9 > vwap
                bullish_stack = ema9 > ema20 > ema50
                long_signal = ema9_crosses_above_vwap and bullish_stack and rsi > 50

                # SHORT signal
                ema9_crosses_below_vwap = prev_ema9 >= prev_vwap and ema9 < vwap
                bearish_stack = ema9 < ema20 < ema50
                short_signal = ema9_crosses_below_vwap and bearish_stack and rsi < 50

                if long_signal:
                    entry = row["close"] + SLIPPAGE_PTS
                    stop = entry - atr
                    target = entry + 2 * atr
                    open_trade = Trade(day_idx, i, "LONG", round(entry, 2),
                                       round(stop, 2), round(target, 2), contracts)
                    day_trades += 1

                elif short_signal:
                    entry = row["close"] - SLIPPAGE_PTS
                    stop = entry + atr
                    target = entry - 2 * atr
                    open_trade = Trade(day_idx, i, "SHORT", round(entry, 2),
                                       round(stop, 2), round(target, 2), contracts)
                    day_trades += 1

        equity += day_pnl
        daily_equity.append(equity)

    return trades, daily_equity


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def compute_metrics(
    trades: list[ClosedTrade],
    daily_equity: list[float],
) -> dict:
    """Compute strategy performance metrics."""
    if not trades:
        return {"error": "No trades generated"}

    pnls = np.array([t.pnl for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    equity_arr = np.array(daily_equity)

    # Daily returns
    daily_returns = np.diff(equity_arr) / np.maximum(equity_arr[:-1], 1.0)
    daily_returns = daily_returns[~np.isnan(daily_returns)]

    # Max drawdown
    peak = np.maximum.accumulate(equity_arr)
    drawdown = equity_arr - peak
    max_dd_dollar = drawdown.min()
    max_dd_idx = np.argmin(drawdown)
    max_dd_pct = (max_dd_dollar / peak[max_dd_idx] * 100) if peak[max_dd_idx] > 0 else 0

    # Daily P&L for best/worst day
    daily_pnl: dict[int, float] = {}
    for t in trades:
        daily_pnl[t.day] = daily_pnl.get(t.day, 0.0) + t.pnl
    daily_pnl_values = list(daily_pnl.values()) if daily_pnl else [0.0]

    # Profit factor
    gross_profit = wins.sum() if len(wins) > 0 else 0.0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 1.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe (annualized, using trading-day returns)
    sharpe = (
        (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252)
        if np.std(daily_returns) > 0 else 0.0
    )

    total_return_dollar = equity_arr[-1] - STARTING_CAPITAL
    total_return_pct = total_return_dollar / STARTING_CAPITAL * 100

    return {
        "total_return_dollar": round(total_return_dollar, 2),
        "total_return_pct": round(total_return_pct, 2),
        "final_equity": round(equity_arr[-1], 2),
        "num_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(pnls) * 100, 2),
        "avg_win": round(wins.mean(), 2) if len(wins) > 0 else 0.0,
        "avg_loss": round(losses.mean(), 2) if len(losses) > 0 else 0.0,
        "profit_factor": round(profit_factor, 2),
        "max_drawdown_dollar": round(max_dd_dollar, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "sharpe_ratio": round(sharpe, 2),
        "best_day": round(max(daily_pnl_values), 2),
        "worst_day": round(min(daily_pnl_values), 2),
        "long_trades": sum(1 for t in trades if t.direction == "LONG"),
        "short_trades": sum(1 for t in trades if t.direction == "SHORT"),
    }


def print_report(metrics: dict, trades: list[ClosedTrade], daily_equity: list[float]) -> None:
    """Print formatted backtest results."""
    sep = "=" * 60
    print(f"\n{sep}")
    print("  MES EMA/VWAP Scalping Strategy - Backtest Results")
    print(sep)
    print(f"  Period:            252 trading days (5-min bars)")
    print(f"  Starting Capital:  ${STARTING_CAPITAL:,.2f}")
    print(f"  Commission:        ${COMMISSION_RT} round-trip")
    print(f"  Slippage:          {SLIPPAGE_PTS} pts per trade")
    print(sep)

    print(f"\n  Total Return:      ${metrics['total_return_dollar']:>+10,.2f}  ({metrics['total_return_pct']:>+.2f}%)")
    print(f"  Final Equity:      ${metrics['final_equity']:>10,.2f}")
    print(f"  Number of Trades:  {metrics['num_trades']}")
    print(f"    Long:            {metrics['long_trades']}")
    print(f"    Short:           {metrics['short_trades']}")
    print(f"  Win Rate:          {metrics['win_rate_pct']:.2f}%")
    print(f"  Avg Win:           ${metrics['avg_win']:>+10,.2f}")
    print(f"  Avg Loss:          ${metrics['avg_loss']:>+10,.2f}")
    print(f"  Profit Factor:     {metrics['profit_factor']:.2f}")
    print(f"  Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:      ${metrics['max_drawdown_dollar']:>10,.2f}  ({metrics['max_drawdown_pct']:.2f}%)")
    print(f"  Best Day:          ${metrics['best_day']:>+10,.2f}")
    print(f"  Worst Day:         ${metrics['worst_day']:>+10,.2f}")

    # Position sizing milestones
    print(f"\n{sep}")
    print("  Position Sizing Milestones")
    print(sep)
    equity_arr = np.array(daily_equity)
    milestones = [
        (1000, 2, "Scale to 2 contracts"),
        (2500, 3, "Scale to 3 contracts"),
        (5000, 4, "Scale to 4 contracts"),
    ]
    for threshold, contracts, label in milestones:
        hit_days = np.where(equity_arr >= threshold)[0]
        if len(hit_days) > 0:
            print(f"  ${threshold:>5,} ({contracts}x) reached on day {hit_days[0]}: {label}")
        else:
            print(f"  ${threshold:>5,} ({contracts}x) NOT reached: {label}")

    # Win/Loss breakdown by result type
    result_counts = {}
    for t in trades:
        result_counts[t.result] = result_counts.get(t.result, 0) + 1
    print(f"\n  Exit Breakdown:")
    for result, count in sorted(result_counts.items()):
        print(f"    {result:>5}: {count}")

    print(f"\n{sep}\n")


def plot_equity_curve(daily_equity: list[float], output_path: str) -> None:
    """Save equity curve chart to file."""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(daily_equity, linewidth=1.2, color="#2563eb")
    ax.fill_between(range(len(daily_equity)), daily_equity, alpha=0.08, color="#2563eb")
    ax.axhline(y=STARTING_CAPITAL, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)

    # Mark position sizing thresholds
    for threshold, contracts, _ in [(1000, 2, ""), (2500, 3, ""), (5000, 4, "")]:
        ax.axhline(y=threshold, color="#f59e0b", linestyle=":", linewidth=0.7, alpha=0.5)
        ax.text(len(daily_equity) * 0.01, threshold + 20, f"${threshold} ({contracts}x)",
                fontsize=8, color="#f59e0b", alpha=0.8)

    ax.set_title("MES EMA/VWAP Scalping - Equity Curve", fontsize=13, fontweight="bold")
    ax.set_xlabel("Trading Day")
    ax.set_ylabel("Equity ($)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"  Equity curve saved to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("\n  Generating 252 days of MES 5-minute data...")
    df = generate_mes_data(TRADING_DAYS, SEED)
    print(f"  Generated {len(df):,} bars")

    print("  Computing indicators...")
    df = compute_indicators(df)

    print("  Running backtest...")
    trades, daily_equity = run_backtest(df)

    metrics = compute_metrics(trades, daily_equity)
    print_report(metrics, trades, daily_equity)

    chart_path = "/Users/yohan/Desktop/ROOT/scripts/backtests/micro_futures_scalp_equity.png"
    plot_equity_curve(daily_equity, chart_path)


if __name__ == "__main__":
    main()
