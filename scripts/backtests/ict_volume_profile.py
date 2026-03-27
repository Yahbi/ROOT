"""
ICT Fair Value Gap + Volume Profile POC Mean Reversion Backtester
================================================================
Simulates 252 trading days of ES/MES futures on 15-minute data.

Strategy 1: ICT FVG Trading (1H context, 15-min entry)
Strategy 2: Volume Profile POC Mean Reversion (session-based)

Author: Backtest Engine
"""

import random
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum


# ── Configuration ────────────────────────────────────────────────────────────

STARTING_CAPITAL = 500.0
POINT_VALUE = 5.0        # MES: $5/point
COMMISSION_RT = 1.24     # round-trip per contract
SLIPPAGE_PTS = 0.5       # points per side
TRADING_DAYS = 252
BARS_PER_SESSION = 27    # 9:30–16:00 in 15-min bars
BARS_PER_1H = 4          # 4 × 15-min = 1 hour
EMA_PERIOD = 20
ATR_PERIOD = 14
MAX_FVG_TRADES_PER_DAY = 3
SEED = 42


# ── Data Structures ─────────────────────────────────────────────────────────

class Direction(Enum):
    LONG = 1
    SHORT = -1


@dataclass(frozen=True)
class Bar:
    open: float
    high: float
    low: float
    close: float
    volume: int
    delta: float  # buy_volume - sell_volume


@dataclass(frozen=True)
class Trade:
    direction: Direction
    entry_price: float
    stop_price: float
    targets: Tuple[Tuple[float, float], ...]  # (price, fraction)
    day: int
    bar_idx: int


@dataclass
class TradeResult:
    direction: Direction
    entry_price: float
    exit_price: float
    pnl_points: float
    pnl_dollars: float
    day: int


@dataclass
class StrategyStats:
    name: str
    trades: List[TradeResult] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)


# ── Synthetic Data Generator ────────────────────────────────────────────────

def generate_session_bars(
    rng: random.Random,
    prev_close: float,
    volatility_regime: float,
) -> List[Bar]:
    """Generate 27 realistic 15-min bars for one ES session."""
    bars: List[Bar] = []
    price = prev_close
    daily_range = rng.uniform(50, 80) * volatility_regime
    bar_range = daily_range / BARS_PER_SESSION

    # Intraday bias: slight trend for the day
    daily_drift = rng.choice([-1, 1]) * rng.uniform(0.1, 0.6)

    for i in range(BARS_PER_SESSION):
        # Morning volatility spike, midday lull, close ramp
        time_factor = _intraday_volatility_factor(i, BARS_PER_SESSION)
        local_range = bar_range * time_factor * rng.uniform(0.6, 1.5)

        drift = daily_drift * (local_range * 0.15)
        noise = rng.gauss(0, local_range * 0.3)
        move = drift + noise

        bar_open = price
        bar_close = price + move

        wick_up = abs(rng.gauss(0, local_range * 0.3))
        wick_down = abs(rng.gauss(0, local_range * 0.3))

        bar_high = max(bar_open, bar_close) + wick_up
        bar_low = min(bar_open, bar_close) - wick_down

        volume = int(rng.uniform(800, 4000) * time_factor)
        # Delta: biased toward trend direction
        delta_bias = 0.3 if move > 0 else -0.3
        delta = volume * (delta_bias + rng.gauss(0, 0.2))

        bars.append(Bar(
            open=round(bar_open, 2),
            high=round(bar_high, 2),
            low=round(bar_low, 2),
            close=round(bar_close, 2),
            volume=volume,
            delta=round(delta, 0),
        ))
        price = bar_close

    return bars


def _intraday_volatility_factor(bar_idx: int, total: int) -> float:
    """U-shaped intraday volatility: high open/close, low midday."""
    x = bar_idx / max(total - 1, 1)
    return 0.7 + 1.2 * (4 * (x - 0.5) ** 2)


def generate_all_sessions(rng: random.Random) -> List[List[Bar]]:
    """Generate 252 sessions of 15-min bars with volatility clustering."""
    sessions: List[List[Bar]] = []
    price = 4500.0  # starting ES price
    vol_regime = 1.0

    for _ in range(TRADING_DAYS):
        # Volatility clustering via mean-reverting regime
        vol_regime = max(0.5, min(2.0,
            vol_regime + rng.gauss(0, 0.08)))
        session = generate_session_bars(rng, price, vol_regime)
        sessions.append(session)
        price = session[-1].close

    return sessions


# ── Indicator Helpers ────────────────────────────────────────────────────────

def compute_ema(values: List[float], period: int) -> List[float]:
    """Compute EMA over a list of values."""
    if not values:
        return []
    multiplier = 2.0 / (period + 1)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * multiplier + ema[-1] * (1 - multiplier))
    return ema


def build_1h_bars(session_bars: List[Bar]) -> List[Bar]:
    """Aggregate 15-min bars into 1H bars (groups of 4)."""
    hourly: List[Bar] = []
    for start in range(0, len(session_bars), BARS_PER_1H):
        chunk = session_bars[start:start + BARS_PER_1H]
        if not chunk:
            break
        hourly.append(Bar(
            open=chunk[0].open,
            high=max(b.high for b in chunk),
            low=min(b.low for b in chunk),
            close=chunk[-1].close,
            volume=sum(b.volume for b in chunk),
            delta=sum(b.delta for b in chunk),
        ))
    return hourly


def compute_atr(bars: List[Bar], period: int) -> float:
    """Compute ATR from a list of bars."""
    if len(bars) < 2:
        return max(b.high - b.low for b in bars) if bars else 5.0
    trs: List[float] = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        trs.append(tr)
    if len(trs) <= period:
        return sum(trs) / len(trs) if trs else 5.0
    return sum(trs[-period:]) / period


# ── Strategy 1: ICT Fair Value Gap ──────────────────────────────────────────

def find_fvgs_on_1h(hourly_bars: List[Bar]) -> List[Tuple[int, Direction, float, float]]:
    """
    Detect FVG patterns on 1H bars.
    Returns list of (bar_index, direction, zone_low, zone_high).
    Bullish FVG: candle1.high < candle3.low  → gap between them
    Bearish FVG: candle1.low > candle3.high  → gap between them
    """
    fvgs: List[Tuple[int, Direction, float, float]] = []
    for i in range(2, len(hourly_bars)):
        c1, c3 = hourly_bars[i - 2], hourly_bars[i]

        # Bullish FVG
        if c1.high < c3.low:
            fvgs.append((i, Direction.LONG, c1.high, c3.low))

        # Bearish FVG
        if c1.low > c3.high:
            fvgs.append((i, Direction.SHORT, c3.high, c1.low))

    return fvgs


def run_fvg_strategy(
    sessions: List[List[Bar]],
    all_1h_closes: List[float],
) -> StrategyStats:
    """Execute ICT FVG strategy across all sessions."""
    stats = StrategyStats(name="ICT FVG")
    capital = STARTING_CAPITAL
    stats.equity_curve.append(capital)

    # Build running 1H EMA across all sessions
    ema_values = compute_ema(all_1h_closes, EMA_PERIOD)
    hourly_idx_offset = 0

    for day_idx, session in enumerate(sessions):
        hourly = build_1h_bars(session)
        day_trades = 0

        # Get EMA direction at start of this session
        ema_start = hourly_idx_offset
        ema_end = ema_start + len(hourly)
        if ema_end > len(ema_values) or ema_end < 2:
            hourly_idx_offset += len(hourly)
            stats.equity_curve.append(capital)
            continue

        trend_up = ema_values[min(ema_end - 1, len(ema_values) - 1)] > ema_values[max(ema_start, 0)]

        # Find FVGs on 1H chart
        fvgs = find_fvgs_on_1h(hourly)

        for fvg_bar_idx, direction, zone_low, zone_high in fvgs:
            if day_trades >= MAX_FVG_TRADES_PER_DAY:
                break

            # Only trade if FVG aligns with trend
            if direction == Direction.LONG and not trend_up:
                continue
            if direction == Direction.SHORT and trend_up:
                continue

            # Check if price retraces into FVG zone on 15-min bars
            # Look at 15-min bars AFTER the FVG formed
            start_15m = fvg_bar_idx * BARS_PER_1H
            for bar_i in range(start_15m, min(start_15m + 8, len(session))):
                bar = session[bar_i]

                if direction == Direction.LONG and bar.low <= zone_high and bar.close > zone_low:
                    entry = max(zone_low, bar.close)
                    stop = zone_low - SLIPPAGE_PTS
                    risk = entry - stop
                    if risk <= 0 or risk > 20:
                        continue

                    # Scale-out targets: 50% at 2R, 25% at 3R, 25% at 4R
                    targets = (
                        (entry + 2 * risk, 0.50),
                        (entry + 3 * risk, 0.25),
                        (entry + 4 * risk, 0.25),
                    )
                    result = _simulate_scaled_exit(
                        direction, entry, stop, targets, session, bar_i, day_idx
                    )
                    if result is not None:
                        capital = _apply_trade(capital, result, stats)
                        day_trades += 1
                    break

                elif direction == Direction.SHORT and bar.high >= zone_low and bar.close < zone_high:
                    entry = min(zone_high, bar.close)
                    stop = zone_high + SLIPPAGE_PTS
                    risk = stop - entry
                    if risk <= 0 or risk > 20:
                        continue

                    targets = (
                        (entry - 2 * risk, 0.50),
                        (entry - 3 * risk, 0.25),
                        (entry - 4 * risk, 0.25),
                    )
                    result = _simulate_scaled_exit(
                        direction, entry, stop, targets, session, bar_i, day_idx
                    )
                    if result is not None:
                        capital = _apply_trade(capital, result, stats)
                        day_trades += 1
                    break

        hourly_idx_offset += len(hourly)
        stats.equity_curve.append(capital)

    return stats


def _simulate_scaled_exit(
    direction: Direction,
    entry: float,
    stop: float,
    targets: Tuple[Tuple[float, float], ...],
    session: List[Bar],
    entry_bar: int,
    day: int,
) -> Optional[TradeResult]:
    """Simulate a scaled-out trade over remaining session bars."""
    remaining_targets = list(targets)
    filled_pnl = 0.0
    filled_fraction = 0.0

    for bar in session[entry_bar + 1:]:
        # Check stop first
        if direction == Direction.LONG:
            if bar.low <= stop:
                # Stopped out on remaining portion
                unfilled = 1.0 - filled_fraction
                filled_pnl += (stop - entry - SLIPPAGE_PTS) * unfilled
                return _make_result(direction, entry, stop, filled_pnl, day)

            # Check targets
            new_remaining = []
            for tp, frac in remaining_targets:
                if bar.high >= tp:
                    filled_pnl += (tp - entry - SLIPPAGE_PTS) * frac
                    filled_fraction += frac
                else:
                    new_remaining.append((tp, frac))
            remaining_targets = new_remaining

        else:  # SHORT
            if bar.high >= stop:
                unfilled = 1.0 - filled_fraction
                filled_pnl += (entry - stop - SLIPPAGE_PTS) * unfilled
                return _make_result(direction, entry, stop, filled_pnl, day)

            new_remaining = []
            for tp, frac in remaining_targets:
                if bar.low <= tp:
                    filled_pnl += (entry - tp - SLIPPAGE_PTS) * frac
                    filled_fraction += frac
                else:
                    new_remaining.append((tp, frac))
            remaining_targets = new_remaining

        if not remaining_targets:
            break

    # End of session: close remaining at last bar's close
    if remaining_targets:
        last_close = session[-1].close
        unfilled = 1.0 - filled_fraction
        if direction == Direction.LONG:
            filled_pnl += (last_close - entry - SLIPPAGE_PTS) * unfilled
        else:
            filled_pnl += (entry - last_close - SLIPPAGE_PTS) * unfilled

    return _make_result(direction, entry, entry + filled_pnl, filled_pnl, day)


def _make_result(
    direction: Direction,
    entry: float,
    exit_price: float,
    pnl_pts: float,
    day: int,
) -> TradeResult:
    pnl_dollars = pnl_pts * POINT_VALUE - COMMISSION_RT
    return TradeResult(
        direction=direction,
        entry_price=round(entry, 2),
        exit_price=round(exit_price, 2),
        pnl_points=round(pnl_pts, 2),
        pnl_dollars=round(pnl_dollars, 2),
        day=day,
    )


# ── Strategy 2: Volume Profile POC Mean Reversion ───────────────────────────

def compute_session_profile(bars: List[Bar]) -> Tuple[float, float, float]:
    """
    Compute session POC, VAH, VAL from bar data.
    Uses a simplified TPO-style approach: discretize price into ticks,
    count volume at each level, find POC and 70% value area.
    """
    if not bars:
        return 0.0, 0.0, 0.0

    tick = 0.25  # ES tick size
    volume_at_price: dict[int, int] = {}

    for bar in bars:
        levels = max(1, int((bar.high - bar.low) / tick))
        vol_per_level = bar.volume // max(levels, 1)
        for step in range(levels + 1):
            price_level = int(round((bar.low + step * tick) / tick))
            volume_at_price[price_level] = (
                volume_at_price.get(price_level, 0) + vol_per_level
            )

    if not volume_at_price:
        mid = (bars[0].open + bars[-1].close) / 2
        return mid, mid + 10, mid - 10

    # POC: price level with highest volume
    poc_tick = max(volume_at_price, key=volume_at_price.get)
    poc = poc_tick * tick

    # Value area: expand from POC until 70% of total volume
    total_vol = sum(volume_at_price.values())
    target_vol = total_vol * 0.70
    sorted_levels = sorted(volume_at_price.keys())
    poc_pos = sorted_levels.index(poc_tick)

    accumulated = volume_at_price[poc_tick]
    lo_idx, hi_idx = poc_pos, poc_pos

    while accumulated < target_vol and (lo_idx > 0 or hi_idx < len(sorted_levels) - 1):
        up_vol = volume_at_price.get(
            sorted_levels[min(hi_idx + 1, len(sorted_levels) - 1)], 0
        ) if hi_idx < len(sorted_levels) - 1 else 0
        down_vol = volume_at_price.get(
            sorted_levels[max(lo_idx - 1, 0)], 0
        ) if lo_idx > 0 else 0

        if up_vol >= down_vol and hi_idx < len(sorted_levels) - 1:
            hi_idx += 1
            accumulated += volume_at_price[sorted_levels[hi_idx]]
        elif lo_idx > 0:
            lo_idx -= 1
            accumulated += volume_at_price[sorted_levels[lo_idx]]
        else:
            hi_idx = min(hi_idx + 1, len(sorted_levels) - 1)
            accumulated += volume_at_price.get(sorted_levels[hi_idx], 0)

    val = sorted_levels[lo_idx] * tick
    vah = sorted_levels[hi_idx] * tick

    return poc, vah, val


def run_vpoc_strategy(sessions: List[List[Bar]]) -> StrategyStats:
    """Execute Volume Profile POC mean reversion strategy."""
    stats = StrategyStats(name="Volume Profile POC")
    capital = STARTING_CAPITAL
    stats.equity_curve.append(capital)

    # Use previous day's profile to define zones for current day
    prev_poc, prev_vah, prev_val = None, None, None

    for day_idx, session in enumerate(sessions):
        # Compute today's profile (used for next day)
        poc, vah, val = compute_session_profile(session)
        atr = compute_atr(session, ATR_PERIOD)

        if prev_poc is None:
            prev_poc, prev_vah, prev_val = poc, vah, val
            stats.equity_curve.append(capital)
            continue

        # Trade using previous day's levels
        traded_long = False
        traded_short = False

        for bar_i, bar in enumerate(session):
            if bar_i < 2:  # skip first 2 bars (opening noise)
                continue

            # LONG: price touches prev VAL + bullish reversal + positive delta
            if (
                not traded_long
                and bar.low <= prev_val
                and bar.close > bar.open  # bullish candle
                and bar.close > prev_val  # closes back above VAL (reversal)
                and bar.delta > 0          # positive delta
            ):
                entry = bar.close + SLIPPAGE_PTS
                stop = prev_val - 0.5 * atr
                risk = entry - stop
                target = prev_poc
                reward = target - entry

                if risk > 0 and risk < 15 and reward > 0 and reward / risk >= 1.5:
                    result = _simulate_single_target(
                        Direction.LONG, entry, stop, target,
                        session, bar_i, day_idx,
                    )
                    capital = _apply_trade(capital, result, stats)
                    traded_long = True

            # SHORT: price touches prev VAH + bearish reversal + negative delta
            if (
                not traded_short
                and bar.high >= prev_vah
                and bar.close < bar.open   # bearish candle
                and bar.close < prev_vah   # closes back below VAH (reversal)
                and bar.delta < 0           # negative delta
            ):
                entry = bar.close - SLIPPAGE_PTS
                stop = prev_vah + 0.5 * atr
                risk = stop - entry
                target = prev_poc
                reward = entry - target

                if risk > 0 and risk < 15 and reward > 0 and reward / risk >= 1.5:
                    result = _simulate_single_target(
                        Direction.SHORT, entry, stop, target,
                        session, bar_i, day_idx,
                    )
                    capital = _apply_trade(capital, result, stats)
                    traded_short = True

            if traded_long and traded_short:
                break

        prev_poc, prev_vah, prev_val = poc, vah, val
        stats.equity_curve.append(capital)

    return stats


def _simulate_single_target(
    direction: Direction,
    entry: float,
    stop: float,
    target: float,
    session: List[Bar],
    entry_bar: int,
    day: int,
) -> TradeResult:
    """Simulate a single-target trade."""
    for bar in session[entry_bar + 1:]:
        if direction == Direction.LONG:
            if bar.low <= stop:
                pnl = stop - entry - SLIPPAGE_PTS
                return _make_result(direction, entry, stop, pnl, day)
            if bar.high >= target:
                pnl = target - entry - SLIPPAGE_PTS
                return _make_result(direction, entry, target, pnl, day)
        else:
            if bar.high >= stop:
                pnl = entry - stop - SLIPPAGE_PTS
                return _make_result(direction, entry, stop, pnl, day)
            if bar.low <= target:
                pnl = entry - target - SLIPPAGE_PTS
                return _make_result(direction, entry, target, pnl, day)

    # End of session
    last = session[-1].close
    if direction == Direction.LONG:
        pnl = last - entry - SLIPPAGE_PTS
    else:
        pnl = entry - last - SLIPPAGE_PTS
    return _make_result(direction, entry, last, pnl, day)


# ── Trade Application ───────────────────────────────────────────────────────

def _apply_trade(
    capital: float,
    result: TradeResult,
    stats: StrategyStats,
) -> float:
    """Apply a trade result to capital and record it."""
    stats.trades.append(result)
    return capital + result.pnl_dollars


# ── Analytics ────────────────────────────────────────────────────────────────

def compute_metrics(stats: StrategyStats) -> dict:
    """Compute comprehensive performance metrics."""
    trades = stats.trades
    if not trades:
        return {"name": stats.name, "total_trades": 0}

    wins = [t for t in trades if t.pnl_dollars > 0]
    losses = [t for t in trades if t.pnl_dollars <= 0]
    pnls = [t.pnl_dollars for t in trades]

    total_return = sum(pnls)
    win_rate = len(wins) / len(trades) * 100

    avg_win = sum(t.pnl_dollars for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.pnl_dollars for t in losses) / len(losses) if losses else 0

    gross_profit = sum(t.pnl_dollars for t in wins)
    gross_loss = abs(sum(t.pnl_dollars for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe (daily returns approximation)
    daily_returns = _daily_returns(stats.equity_curve)
    sharpe = _sharpe_ratio(daily_returns)

    # Max drawdown
    max_dd, max_dd_pct = _max_drawdown(stats.equity_curve)

    long_trades = [t for t in trades if t.direction == Direction.LONG]
    short_trades = [t for t in trades if t.direction == Direction.SHORT]

    final_equity = stats.equity_curve[-1] if stats.equity_curve else STARTING_CAPITAL

    return {
        "name": stats.name,
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "total_return": round(total_return, 2),
        "total_return_pct": round(total_return / STARTING_CAPITAL * 100, 1),
        "profit_factor": round(profit_factor, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 1),
        "final_equity": round(final_equity, 2),
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "long_wins": len([t for t in long_trades if t.pnl_dollars > 0]),
        "short_wins": len([t for t in short_trades if t.pnl_dollars > 0]),
    }


def _daily_returns(equity_curve: List[float]) -> List[float]:
    """Compute daily returns from equity curve."""
    returns: List[float] = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i - 1] != 0:
            returns.append(
                (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            )
    return returns


def _sharpe_ratio(returns: List[float], periods: int = 252) -> float:
    """Annualized Sharpe ratio (risk-free rate assumed 0)."""
    if len(returns) < 2:
        return 0.0
    mean_r = sum(returns) / len(returns)
    std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1))
    if std_r == 0:
        return 0.0
    return (mean_r / std_r) * math.sqrt(periods)


def _max_drawdown(equity_curve: List[float]) -> Tuple[float, float]:
    """Return (max_drawdown_dollars, max_drawdown_percent)."""
    if len(equity_curve) < 2:
        return 0.0, 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    for eq in equity_curve[1:]:
        if eq > peak:
            peak = eq
        dd = peak - eq
        dd_pct = dd / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
    return max_dd, max_dd_pct


# ── Combined Strategy ────────────────────────────────────────────────────────

def combine_strategies(
    s1: StrategyStats,
    s2: StrategyStats,
) -> StrategyStats:
    """Merge two strategies running simultaneously on same capital."""
    combined = StrategyStats(name="Combined (FVG + VPOC)")

    # Merge trades sorted by day
    all_trades = sorted(s1.trades + s2.trades, key=lambda t: (t.day, t.pnl_dollars))
    combined.trades = all_trades

    # Build combined equity curve day by day
    capital = STARTING_CAPITAL
    combined.equity_curve.append(capital)

    # Group trades by day
    day_pnl: dict[int, float] = {}
    for t in all_trades:
        day_pnl[t.day] = day_pnl.get(t.day, 0) + t.pnl_dollars

    for day in range(TRADING_DAYS):
        capital += day_pnl.get(day, 0)
        combined.equity_curve.append(capital)

    return combined


# ── Display ──────────────────────────────────────────────────────────────────

def print_metrics(metrics: dict) -> None:
    """Pretty-print strategy metrics."""
    name = metrics["name"]
    w = 50
    print(f"\n{'=' * w}")
    print(f"  {name}")
    print(f"{'=' * w}")

    if metrics["total_trades"] == 0:
        print("  No trades generated.")
        return

    print(f"  {'Total Trades:':<28} {metrics['total_trades']}")
    print(f"  {'Wins / Losses:':<28} {metrics['wins']} / {metrics['losses']}")
    print(f"  {'Win Rate:':<28} {metrics['win_rate']}%")
    print(f"  {'Avg Win:':<28} ${metrics['avg_win']}")
    print(f"  {'Avg Loss:':<28} ${metrics['avg_loss']}")
    print(f"  {'Long Trades (wins):':<28} {metrics['long_trades']} ({metrics['long_wins']})")
    print(f"  {'Short Trades (wins):':<28} {metrics['short_trades']} ({metrics['short_wins']})")
    print(f"  {'-' * (w - 4)}")
    print(f"  {'Total Return:':<28} ${metrics['total_return']}  ({metrics['total_return_pct']}%)")
    print(f"  {'Final Equity:':<28} ${metrics['final_equity']}")
    print(f"  {'Profit Factor:':<28} {metrics['profit_factor']}")
    print(f"  {'Sharpe Ratio:':<28} {metrics['sharpe']}")
    print(f"  {'Max Drawdown:':<28} ${metrics['max_drawdown']}  ({metrics['max_drawdown_pct']}%)")
    print(f"{'=' * w}")


def print_comparison(m1: dict, m2: dict, mc: dict) -> None:
    """Side-by-side comparison table."""
    w = 72
    print(f"\n{'=' * w}")
    print(f"  SIDE-BY-SIDE COMPARISON")
    print(f"{'=' * w}")

    header = f"  {'Metric':<22} {'FVG':>14} {'VPOC':>14} {'Combined':>14}"
    print(header)
    print(f"  {'-' * (w - 4)}")

    rows = [
        ("Total Trades", "total_trades", ""),
        ("Win Rate", "win_rate", "%"),
        ("Avg Win", "avg_win", "$"),
        ("Avg Loss", "avg_loss", "$"),
        ("Total Return", "total_return", "$"),
        ("Return %", "total_return_pct", "%"),
        ("Profit Factor", "profit_factor", ""),
        ("Sharpe Ratio", "sharpe", ""),
        ("Max Drawdown", "max_drawdown", "$"),
        ("Max DD %", "max_drawdown_pct", "%"),
        ("Final Equity", "final_equity", "$"),
    ]

    for label, key, unit in rows:
        v1 = m1.get(key, "N/A")
        v2 = m2.get(key, "N/A")
        vc = mc.get(key, "N/A")
        prefix = "$" if unit == "$" else ""
        suffix = "%" if unit == "%" else ""
        s1 = f"{prefix}{v1}{suffix}"
        s2 = f"{prefix}{v2}{suffix}"
        sc = f"{prefix}{vc}{suffix}"
        print(f"  {label:<22} {s1:>14} {s2:>14} {sc:>14}")

    print(f"{'=' * w}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  ICT FVG + Volume Profile POC Backtester")
    print(f"  {TRADING_DAYS} trading days | MES ($5/pt) | Start: ${STARTING_CAPITAL}")
    print("=" * 60)

    rng = random.Random(SEED)
    print("\n[1/4] Generating synthetic ES 15-min data...")
    sessions = generate_all_sessions(rng)

    # Pre-compute all 1H closes for running EMA
    all_1h_closes: List[float] = []
    for session in sessions:
        hourly = build_1h_bars(session)
        for h in hourly:
            all_1h_closes.append(h.close)

    print(f"       {len(sessions)} sessions, {sum(len(s) for s in sessions)} bars total")

    print("\n[2/4] Running ICT FVG Strategy...")
    fvg_stats = run_fvg_strategy(sessions, all_1h_closes)
    fvg_metrics = compute_metrics(fvg_stats)
    print_metrics(fvg_metrics)

    print("\n[3/4] Running Volume Profile POC Strategy...")
    vpoc_stats = run_vpoc_strategy(sessions)
    vpoc_metrics = compute_metrics(vpoc_stats)
    print_metrics(vpoc_metrics)

    print("\n[4/4] Computing combined results...")
    combined_stats = combine_strategies(fvg_stats, vpoc_stats)
    combined_metrics = compute_metrics(combined_stats)
    print_metrics(combined_metrics)

    print_comparison(fvg_metrics, vpoc_metrics, combined_metrics)

    print("\nBacktest complete.")


if __name__ == "__main__":
    main()
