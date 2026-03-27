"""
Backtesting Script for Two Crypto Day Trading Strategies on BTC.

Strategy 1: VWAP Bounce/Rejection
Strategy 2: Liquidation Cascade Trading

Uses simulated 15-minute BTC data (365 days) with realistic volatility.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple

# ─── Configuration ───────────────────────────────────────────────────────────

SEED = 42
STARTING_CAPITAL = 100.0
STARTING_BTC_PRICE = 60_000.0
BARS_PER_DAY = 96
TOTAL_DAYS = 365
TOTAL_BARS = BARS_PER_DAY * TOTAL_DAYS
MAKER_FEE = 0.0004
TAKER_FEE = 0.0006
SLIPPAGE = 0.0002
RISK_FREE_RATE = 0.04  # annualized


# ─── Data Generation ─────────────────────────────────────────────────────────

def generate_btc_data(seed: int = SEED) -> dict:
    """
    Generate realistic 15-min BTC OHLCV data using GBM with fat tails.

    Returns dict with arrays: open, high, low, close, volume,
    plus simulated funding_rate and liquidation_cluster arrays.
    """
    rng = np.random.default_rng(seed)

    daily_vol = 0.03  # ~3% daily vol midpoint
    bar_vol = daily_vol / np.sqrt(BARS_PER_DAY)

    # Student-t returns with df=5 for fat tails, scaled to match bar_vol
    t_samples = rng.standard_t(df=5, size=TOTAL_BARS)
    # Scale: std of t(df=5) = sqrt(df/(df-2)) = sqrt(5/3) ≈ 1.29
    t_std = np.sqrt(5.0 / 3.0)
    returns = t_samples * (bar_vol / t_std)

    # Add regime shifts: trending vs ranging periods
    regime_length = BARS_PER_DAY * 10  # ~10 day regimes
    num_regimes = TOTAL_BARS // regime_length + 1
    drift_per_regime = rng.choice(
        [-0.0001, -0.00005, 0.0, 0.00005, 0.0001],
        size=num_regimes,
        p=[0.15, 0.2, 0.3, 0.2, 0.15],
    )
    drift = np.repeat(drift_per_regime, regime_length)[:TOTAL_BARS]
    returns = returns + drift

    # Build close prices
    log_prices = np.log(STARTING_BTC_PRICE) + np.cumsum(returns)
    close = np.exp(log_prices)

    # Generate OHLV from close
    intra_noise = rng.uniform(0.0005, 0.002, size=TOTAL_BARS)
    high = close * (1.0 + intra_noise * rng.uniform(0.5, 1.5, size=TOTAL_BARS))
    low = close * (1.0 - intra_noise * rng.uniform(0.5, 1.5, size=TOTAL_BARS))

    open_prices = np.empty(TOTAL_BARS)
    open_prices[0] = STARTING_BTC_PRICE
    open_prices[1:] = close[:-1] * (1.0 + rng.normal(0, 0.0002, size=TOTAL_BARS - 1))

    # Ensure high >= max(open, close) and low <= min(open, close)
    high = np.maximum(high, np.maximum(open_prices, close))
    low = np.minimum(low, np.minimum(open_prices, close))

    # Volume: base + spikes during high volatility
    base_volume = 500 + 300 * np.abs(rng.standard_normal(TOTAL_BARS))
    vol_spike = np.where(np.abs(returns) > 2 * bar_vol, 3.0, 1.0)
    volume = base_volume * vol_spike

    # Simulate funding rate (oscillates, mean-reverts to 0.01%)
    funding = np.zeros(TOTAL_BARS)
    funding[0] = 0.0001
    for i in range(1, TOTAL_BARS):
        funding[i] = funding[i - 1] * 0.99 + 0.0001 * 0.01 + rng.normal(0, 0.00005)
    funding = np.clip(funding, -0.001, 0.003)

    # Simulate liquidation cluster levels (price levels where liquidations pool)
    # Clusters form near round numbers and recent swing highs/lows
    liq_clusters = np.zeros(TOTAL_BARS)
    lookback = BARS_PER_DAY * 2
    for i in range(lookback, TOTAL_BARS):
        recent_high = np.max(high[i - lookback : i])
        recent_low = np.min(low[i - lookback : i])
        range_size = recent_high - recent_low
        # Cluster density: how close price is to recent extremes
        dist_to_high = abs(close[i] - recent_high) / range_size if range_size > 0 else 1.0
        dist_to_low = abs(close[i] - recent_low) / range_size if range_size > 0 else 1.0
        liq_clusters[i] = 1.0 / (1.0 + min(dist_to_high, dist_to_low))

    return {
        "open": open_prices,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "funding_rate": funding,
        "liq_cluster_density": liq_clusters,
    }


# ─── Indicator Calculations ──────────────────────────────────────────────────

def calc_vwap_rolling(close: np.ndarray, volume: np.ndarray, period: int = 96) -> np.ndarray:
    """Rolling VWAP over `period` bars (default: 1 day = 96 bars)."""
    vwap = np.full_like(close, np.nan)
    cum_pv = np.cumsum(close * volume)
    cum_v = np.cumsum(volume)
    for i in range(period, len(close)):
        pv = cum_pv[i] - cum_pv[i - period]
        v = cum_v[i] - cum_v[i - period]
        vwap[i] = pv / v if v > 0 else close[i]
    return vwap


def calc_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI using exponential moving average of gains/losses."""
    rsi = np.full_like(close, 50.0)
    deltas = np.diff(close)

    avg_gain = 0.0
    avg_loss = 0.0

    # Seed with SMA
    for j in range(period):
        if j < len(deltas):
            d = deltas[j]
            if d > 0:
                avg_gain += d
            else:
                avg_loss += abs(d)
    avg_gain /= period
    avg_loss /= period

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - 100.0 / (1.0 + rs)

    for i in range(period + 1, len(close)):
        d = deltas[i - 1]
        gain = max(d, 0.0)
        loss = abs(min(d, 0.0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)
    return rsi


def calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range."""
    atr = np.full_like(close, np.nan)
    tr = np.zeros(len(close))
    for i in range(1, len(close)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    # SMA seed
    atr[period] = np.mean(tr[1 : period + 1])
    for i in range(period + 1, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def calc_volume_ma(volume: np.ndarray, period: int = 20) -> np.ndarray:
    """Simple moving average of volume."""
    vma = np.full_like(volume, np.nan)
    cum = np.cumsum(volume)
    vma[period - 1 :] = (cum[period - 1 :] - np.concatenate(([0], cum[: -period]))) / period
    return vma


# ─── Trade and Portfolio ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Trade:
    direction: int  # 1 = long, -1 = short
    entry_price: float
    entry_bar: int
    stop_loss: float
    take_profit: float
    position_size_usd: float
    leverage: float
    # For scaled exits (liquidation strategy)
    scale_targets: Tuple[float, ...] = ()
    scale_pcts: Tuple[float, ...] = ()


@dataclass
class TradeResult:
    direction: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    bars_held: int
    is_win: bool


def apply_slippage(price: float, direction: int, is_entry: bool) -> float:
    """Apply slippage: worse price on entry, worse on exit."""
    if is_entry:
        return price * (1.0 + direction * SLIPPAGE)
    return price * (1.0 - direction * SLIPPAGE)


def calc_fee(notional: float, is_maker: bool) -> float:
    return notional * (MAKER_FEE if is_maker else TAKER_FEE)


# ─── Strategy 1: VWAP Bounce/Rejection ───────────────────────────────────────

def run_vwap_strategy(data: dict) -> List[TradeResult]:
    """
    VWAP Bounce/Rejection strategy on 15-min BTC data.

    Long: price touches VWAP from above, bullish candle, vol > 1.5x avg, RSI > 40
    Short: price touches VWAP from below, bearish candle, vol > 1.5x avg, RSI < 60
    Stop: 1 ATR beyond entry
    TP: 2:1 R:R
    Trailing: breakeven after 1R, then trail 0.5 ATR
    """
    o, h, l, c, v = data["open"], data["high"], data["low"], data["close"], data["volume"]
    leverage = 10.0

    vwap = calc_vwap_rolling(c, v, 96)
    rsi = calc_rsi(c, 14)
    atr = calc_atr(h, l, c, 14)
    vol_ma = calc_volume_ma(v, 20)

    results: List[TradeResult] = []
    capital = STARTING_CAPITAL
    in_trade = False
    current_trade = None
    trailing_stop = None
    breakeven_triggered = False

    warmup = 96 + 20  # max of vwap(96), vol_ma(20), atr(14), rsi(14)

    for i in range(warmup, TOTAL_BARS):
        if np.isnan(vwap[i]) or np.isnan(atr[i]) or np.isnan(vol_ma[i]):
            continue

        if in_trade:
            # Check exit conditions
            trade = current_trade
            direction = trade.direction
            risk = abs(trade.entry_price - trade.stop_loss)

            # Check stop loss (including trailing)
            active_stop = trailing_stop if trailing_stop is not None else trade.stop_loss
            hit_stop = (direction == 1 and l[i] <= active_stop) or (
                direction == -1 and h[i] >= active_stop
            )
            hit_tp = (direction == 1 and h[i] >= trade.take_profit) or (
                direction == -1 and l[i] <= trade.take_profit
            )

            if hit_stop or hit_tp:
                if hit_tp:
                    exit_price = trade.take_profit
                else:
                    exit_price = active_stop

                exit_price = apply_slippage(exit_price, direction, is_entry=False)
                notional = trade.position_size_usd
                entry_fee = calc_fee(notional, is_maker=True)
                exit_fee = calc_fee(notional, is_maker=False)
                raw_pnl = direction * (exit_price - trade.entry_price) / trade.entry_price * notional
                pnl = raw_pnl - entry_fee - exit_fee
                pnl_pct = pnl / capital * 100.0

                capital = max(capital + pnl, 0.01)
                results.append(
                    TradeResult(
                        direction=direction,
                        entry_price=trade.entry_price,
                        exit_price=exit_price,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        bars_held=i - trade.entry_bar,
                        is_win=pnl > 0,
                    )
                )
                in_trade = False
                current_trade = None
                trailing_stop = None
                breakeven_triggered = False
                continue

            # Update trailing stop
            current_pnl_r = direction * (c[i] - trade.entry_price) / risk if risk > 0 else 0
            if not breakeven_triggered and current_pnl_r >= 1.0:
                breakeven_triggered = True
                trailing_stop = trade.entry_price

            if breakeven_triggered:
                trail_dist = 0.5 * atr[i]
                if direction == 1:
                    new_trail = c[i] - trail_dist
                    if trailing_stop is None or new_trail > trailing_stop:
                        trailing_stop = new_trail
                else:
                    new_trail = c[i] + trail_dist
                    if trailing_stop is None or new_trail < trailing_stop:
                        trailing_stop = new_trail
            continue

        # Check for entry signals
        if capital < 1.0:
            continue

        bullish = c[i] > o[i]
        bearish = c[i] < o[i]
        vol_high = v[i] > 1.5 * vol_ma[i]
        price_near_vwap = abs(c[i] - vwap[i]) / c[i] < 0.003  # within 0.3%

        direction = 0
        # Long: price near VWAP from above + bullish + volume + RSI > 40
        if price_near_vwap and c[i] >= vwap[i] and bullish and vol_high and rsi[i] > 40:
            # Confirm bounce: previous bar low touched or crossed VWAP
            if l[i] <= vwap[i] * 1.001:
                direction = 1

        # Short: price near VWAP from below + bearish + volume + RSI < 60
        if direction == 0 and price_near_vwap and c[i] <= vwap[i] and bearish and vol_high and rsi[i] < 60:
            if h[i] >= vwap[i] * 0.999:
                direction = -1

        if direction != 0:
            entry_price = apply_slippage(c[i], direction, is_entry=True)
            current_atr = atr[i]
            stop_dist = current_atr
            risk_amount = stop_dist

            if direction == 1:
                stop_loss = entry_price - stop_dist
                take_profit = entry_price + 2.0 * risk_amount
            else:
                stop_loss = entry_price + stop_dist
                take_profit = entry_price - 2.0 * risk_amount

            position_size = capital * leverage
            current_trade = Trade(
                direction=direction,
                entry_price=entry_price,
                entry_bar=i,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size_usd=position_size,
                leverage=leverage,
            )
            in_trade = True
            breakeven_triggered = False
            trailing_stop = None

    return results


# ─── Strategy 2: Liquidation Cascade Trading ─────────────────────────────────

def run_liquidation_strategy(data: dict) -> List[TradeResult]:
    """
    Liquidation Cascade strategy on 15-min BTC data.

    Entry: Price within 0.5% of simulated liquidation cluster
           + 3-bar momentum > 0.3%
    Exit: Scale out 50% at 1R, 30% at 2R, 20% at 3R
    Stop: 1% beyond entry
    """
    o, h, l, c, v = data["open"], data["high"], data["low"], data["close"], data["volume"]
    liq_density = data["liq_cluster_density"]
    leverage = 5.0

    atr = calc_atr(h, l, c, 14)
    results: List[TradeResult] = []
    capital = STARTING_CAPITAL
    in_trade = False
    current_trade = None
    remaining_pct = 1.0
    scale_idx = 0

    warmup = BARS_PER_DAY * 2 + 14  # for liq clusters + atr

    for i in range(warmup, TOTAL_BARS):
        if np.isnan(atr[i]):
            continue

        if in_trade:
            trade = current_trade
            direction = trade.direction

            # Check stop
            hit_stop = (direction == 1 and l[i] <= trade.stop_loss) or (
                direction == -1 and h[i] >= trade.stop_loss
            )

            if hit_stop:
                exit_price = apply_slippage(trade.stop_loss, direction, is_entry=False)
                notional = trade.position_size_usd * remaining_pct
                entry_fee = calc_fee(notional, is_maker=False)
                exit_fee = calc_fee(notional, is_maker=False)
                raw_pnl = direction * (exit_price - trade.entry_price) / trade.entry_price * notional
                pnl = raw_pnl - entry_fee - exit_fee
                capital = max(capital + pnl, 0.01)
                results.append(
                    TradeResult(
                        direction=direction,
                        entry_price=trade.entry_price,
                        exit_price=exit_price,
                        pnl=pnl,
                        pnl_pct=pnl / max(capital, 0.01) * 100.0,
                        bars_held=i - trade.entry_bar,
                        is_win=pnl > 0,
                    )
                )
                in_trade = False
                current_trade = None
                remaining_pct = 1.0
                scale_idx = 0
                continue

            # Check scale-out targets
            if scale_idx < len(trade.scale_targets):
                target = trade.scale_targets[scale_idx]
                hit_target = (direction == 1 and h[i] >= target) or (
                    direction == -1 and l[i] <= target
                )
                if hit_target:
                    pct_to_close = trade.scale_pcts[scale_idx]
                    exit_price = apply_slippage(target, direction, is_entry=False)
                    notional = trade.position_size_usd * pct_to_close
                    entry_fee = calc_fee(notional, is_maker=True)
                    exit_fee = calc_fee(notional, is_maker=False)
                    raw_pnl = direction * (exit_price - trade.entry_price) / trade.entry_price * notional
                    pnl = raw_pnl - entry_fee - exit_fee
                    capital = max(capital + pnl, 0.01)
                    results.append(
                        TradeResult(
                            direction=direction,
                            entry_price=trade.entry_price,
                            exit_price=exit_price,
                            pnl=pnl,
                            pnl_pct=pnl / max(capital, 0.01) * 100.0,
                            bars_held=i - trade.entry_bar,
                            is_win=pnl > 0,
                        )
                    )
                    remaining_pct -= pct_to_close
                    scale_idx += 1

                    if remaining_pct <= 0.01:
                        in_trade = False
                        current_trade = None
                        remaining_pct = 1.0
                        scale_idx = 0
            continue

        # Check entry
        if capital < 1.0:
            continue

        # High liquidation density threshold
        if liq_density[i] < 0.6:
            continue

        # 3-bar momentum
        if i < 3:
            continue
        momentum = (c[i] - c[i - 3]) / c[i - 3]

        direction = 0
        if momentum > 0.003:
            direction = 1  # long into liquidation cascade (short squeeze)
        elif momentum < -0.003:
            direction = -1  # short into liquidation cascade (long squeeze)

        if direction != 0:
            entry_price = apply_slippage(c[i], direction, is_entry=True)
            stop_dist = entry_price * 0.01  # 1% stop
            risk = stop_dist

            if direction == 1:
                stop_loss = entry_price - stop_dist
                t1 = entry_price + risk
                t2 = entry_price + 2.0 * risk
                t3 = entry_price + 3.0 * risk
            else:
                stop_loss = entry_price + stop_dist
                t1 = entry_price - risk
                t2 = entry_price - 2.0 * risk
                t3 = entry_price - 3.0 * risk

            position_size = capital * leverage
            current_trade = Trade(
                direction=direction,
                entry_price=entry_price,
                entry_bar=i,
                stop_loss=stop_loss,
                take_profit=t3,  # final target
                position_size_usd=position_size,
                leverage=leverage,
                scale_targets=(t1, t2, t3),
                scale_pcts=(0.5, 0.3, 0.2),
            )
            in_trade = True
            remaining_pct = 1.0
            scale_idx = 0

    return results


# ─── Performance Metrics ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyMetrics:
    name: str
    total_return_pct: float
    final_capital: float
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float


def compute_metrics(name: str, results: List[TradeResult], starting_capital: float) -> StrategyMetrics:
    if not results:
        return StrategyMetrics(
            name=name, total_return_pct=0, final_capital=starting_capital,
            num_trades=0, win_rate=0, avg_win=0, avg_loss=0,
            profit_factor=0, max_drawdown_pct=0, sharpe_ratio=0,
        )

    pnls = np.array([t.pnl for t in results])
    equity = starting_capital + np.cumsum(pnls)
    final = equity[-1]
    total_return = (final - starting_capital) / starting_capital * 100.0

    wins = [t.pnl for t in results if t.is_win]
    losses = [t.pnl for t in results if not t.is_win]
    win_rate = len(wins) / len(results) * 100.0 if results else 0.0
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0
    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.001
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown
    peak = starting_capital
    max_dd = 0.0
    for eq in equity:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100.0
        if dd > max_dd:
            max_dd = dd

    # Sharpe (annualized, assuming ~6 trades/day as rough estimate)
    if len(pnls) > 1:
        mean_pnl = np.mean(pnls)
        std_pnl = np.std(pnls, ddof=1)
        trades_per_year = len(results)  # already one year of data
        if std_pnl > 0:
            sharpe = (mean_pnl / std_pnl) * np.sqrt(trades_per_year)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    return StrategyMetrics(
        name=name,
        total_return_pct=round(total_return, 2),
        final_capital=round(final, 2),
        num_trades=len(results),
        win_rate=round(win_rate, 2),
        avg_win=round(avg_win, 4),
        avg_loss=round(avg_loss, 4),
        profit_factor=round(profit_factor, 3),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 3),
    )


# ─── Display ─────────────────────────────────────────────────────────────────

def print_metrics(m: StrategyMetrics) -> None:
    print(f"\n{'=' * 55}")
    print(f"  {m.name}")
    print(f"{'=' * 55}")
    print(f"  Starting Capital:    ${STARTING_CAPITAL:.2f}")
    print(f"  Final Capital:       ${m.final_capital:.2f}")
    print(f"  Total Return:        {m.total_return_pct:+.2f}%")
    print(f"  Number of Trades:    {m.num_trades}")
    print(f"  Win Rate:            {m.win_rate:.2f}%")
    print(f"  Avg Win:             ${m.avg_win:.4f}")
    print(f"  Avg Loss:            ${m.avg_loss:.4f}")
    print(f"  Profit Factor:       {m.profit_factor:.3f}")
    print(f"  Max Drawdown:        {m.max_drawdown_pct:.2f}%")
    print(f"  Sharpe Ratio:        {m.sharpe_ratio:.3f}")
    print(f"{'=' * 55}")


def print_comparison(m1: StrategyMetrics, m2: StrategyMetrics) -> None:
    print(f"\n{'=' * 70}")
    print(f"  STRATEGY COMPARISON")
    print(f"{'=' * 70}")
    header = f"  {'Metric':<22} {'VWAP Bounce':>18} {'Liq Cascade':>18}"
    print(header)
    print(f"  {'-' * 58}")

    rows = [
        ("Total Return", f"{m1.total_return_pct:+.2f}%", f"{m2.total_return_pct:+.2f}%"),
        ("Final Capital", f"${m1.final_capital:.2f}", f"${m2.final_capital:.2f}"),
        ("Num Trades", f"{m1.num_trades}", f"{m2.num_trades}"),
        ("Win Rate", f"{m1.win_rate:.2f}%", f"{m2.win_rate:.2f}%"),
        ("Avg Win", f"${m1.avg_win:.4f}", f"${m2.avg_win:.4f}"),
        ("Avg Loss", f"${m1.avg_loss:.4f}", f"${m2.avg_loss:.4f}"),
        ("Profit Factor", f"{m1.profit_factor:.3f}", f"{m2.profit_factor:.3f}"),
        ("Max Drawdown", f"{m1.max_drawdown_pct:.2f}%", f"{m2.max_drawdown_pct:.2f}%"),
        ("Sharpe Ratio", f"{m1.sharpe_ratio:.3f}", f"{m2.sharpe_ratio:.3f}"),
        ("Leverage", "10x", "5x"),
    ]
    for label, v1, v2 in rows:
        print(f"  {label:<22} {v1:>18} {v2:>18}")
    print(f"{'=' * 70}")

    # Verdict
    score1, score2 = 0, 0
    if m1.total_return_pct > m2.total_return_pct:
        score1 += 1
    else:
        score2 += 1
    if m1.sharpe_ratio > m2.sharpe_ratio:
        score1 += 1
    else:
        score2 += 1
    if m1.max_drawdown_pct < m2.max_drawdown_pct:
        score1 += 1
    else:
        score2 += 1
    if m1.profit_factor > m2.profit_factor:
        score1 += 1
    else:
        score2 += 1

    winner = m1.name if score1 > score2 else m2.name if score2 > score1 else "TIE"
    print(f"\n  Verdict: {winner} wins ({score1}-{score2})")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Generating 365 days of simulated BTC 15-min data...")
    print(f"  Bars: {TOTAL_BARS} | Starting price: ${STARTING_BTC_PRICE:,.0f}")
    print(f"  Starting capital: ${STARTING_CAPITAL:.2f}")
    data = generate_btc_data()

    price_min = np.min(data["close"])
    price_max = np.max(data["close"])
    price_final = data["close"][-1]
    print(f"  Price range: ${price_min:,.0f} - ${price_max:,.0f} | Final: ${price_final:,.0f}")

    print("\nRunning Strategy 1: VWAP Bounce/Rejection (10x leverage)...")
    vwap_results = run_vwap_strategy(data)
    vwap_metrics = compute_metrics("VWAP Bounce/Rejection", vwap_results, STARTING_CAPITAL)
    print_metrics(vwap_metrics)

    print("\nRunning Strategy 2: Liquidation Cascade (5x leverage)...")
    liq_results = run_liquidation_strategy(data)
    liq_metrics = compute_metrics("Liquidation Cascade", liq_results, STARTING_CAPITAL)
    print_metrics(liq_metrics)

    print_comparison(vwap_metrics, liq_metrics)

    # Trade direction breakdown
    for name, results in [("VWAP", vwap_results), ("Liquidation", liq_results)]:
        longs = [t for t in results if t.direction == 1]
        shorts = [t for t in results if t.direction == -1]
        long_wr = sum(1 for t in longs if t.is_win) / len(longs) * 100 if longs else 0
        short_wr = sum(1 for t in shorts if t.is_win) / len(shorts) * 100 if shorts else 0
        print(f"  {name}: {len(longs)} longs ({long_wr:.1f}% WR), {len(shorts)} shorts ({short_wr:.1f}% WR)")


if __name__ == "__main__":
    main()
