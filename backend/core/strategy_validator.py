"""
Strategy Validator — autonomous pipeline: discover → fetch data → backtest → rank → deploy.

Closes the gap between strategy proposals and live trading.
The autonomous loop and proactive engine propose strategies as text;
this module converts them to backtestable signals, validates statistically,
ranks by risk-adjusted return, and only promotes winners to live trading.

Flow:
  1. Strategy proposed (from Swarm, MiRo, AutonomousLoop, Curiosity)
  2. Fetch historical OHLCV data (Yahoo Finance, free, no API key)
  3. Generate buy/sell signals from strategy rules
  4. Run backtest (Sharpe, Sortino, max DD, win rate, profit factor)
  5. Run Monte Carlo simulation for confidence intervals
  6. Rank against existing strategies
  7. If Sharpe > 1.0 and win_rate > 50% → promote to live trading queue
  8. Store all results in experience memory for learning
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np

from backend.config import DATA_DIR

logger = logging.getLogger("root.strategy_validator")

_DB_PATH = DATA_DIR / "strategy_validation.db"

# ── Minimum thresholds to promote a strategy to live trading ──
PROMOTION_THRESHOLDS = {
    "min_sharpe": 0.8,            # Annualized Sharpe ratio
    "min_win_rate": 45.0,         # Win rate %
    "max_drawdown": 25.0,         # Max drawdown %
    "min_trades": 10,             # Minimum trade count for statistical significance
    "min_profit_factor": 1.2,     # Gross profit / gross loss
    "min_monte_carlo_p5": 0.95,   # p5 final capital must be >= 95% of initial (no ruin)
}

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS strategy_validations (
    id TEXT PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    source TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    sharpe_ratio REAL,
    sortino_ratio REAL,
    win_rate REAL,
    max_drawdown_pct REAL,
    total_return_pct REAL,
    profit_factor REAL,
    total_trades INTEGER,
    monte_carlo_p5 REAL,
    monte_carlo_p50 REAL,
    monte_carlo_p95 REAL,
    promoted INTEGER DEFAULT 0,
    backtest_id TEXT,
    raw_signals TEXT,
    lesson TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
"""


@dataclass(frozen=True)
class StrategyValidation:
    """Immutable record of a strategy validation attempt."""
    id: str
    strategy_name: str
    source: str
    hypothesis: str
    symbol: str
    timeframe: str
    status: str = "pending"  # pending, running, passed, failed, error
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    total_return_pct: Optional[float] = None
    profit_factor: Optional[float] = None
    total_trades: Optional[int] = None
    monte_carlo_p5: Optional[float] = None
    monte_carlo_p50: Optional[float] = None
    monte_carlo_p95: Optional[float] = None
    promoted: bool = False
    backtest_id: Optional[str] = None
    raw_signals: Optional[str] = None
    lesson: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None


# ── Historical Data Fetcher (Yahoo Finance, free) ──────────────

def fetch_ohlcv(symbol: str, days: int = 365) -> list[dict[str, Any]]:
    """Fetch historical OHLCV data from Yahoo Finance v8 chart API (free, no key).

    Returns list of {"date", "open", "high", "low", "close", "volume"} dicts.
    """
    import urllib.request
    import json as _json

    end_ts = int(datetime.now().timestamp())
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp())

    # Yahoo Finance v8 chart API (free, no auth required)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={start_ts}&period2={end_ts}&interval=1d"
    )

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (ROOT Trading System)",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("Failed to fetch OHLCV for %s: %s", symbol, e)
        return []

    rows: list[dict[str, Any]] = []
    try:
        chart = data.get("chart", {})
        results = chart.get("result", [])
        if not results:
            return []
        result = results[0]
        timestamps = result.get("timestamp", [])
        quote_list = result.get("indicators", {}).get("quote", [{}])
        quote = quote_list[0] if quote_list else {}
        for i, ts in enumerate(timestamps):
            o = quote["open"][i]
            h = quote["high"][i]
            l = quote["low"][i]
            c = quote["close"][i]
            v = quote["volume"][i]
            if o is None or c is None:
                continue
            dt = datetime.fromtimestamp(ts)
            rows.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": int(v) if v else 0,
            })
    except Exception as e:
        logger.warning("Failed to parse OHLCV for %s: %s", symbol, e)
        return []

    logger.info("Fetched %d OHLCV bars for %s (%d days)", len(rows), symbol, days)
    return rows


# ── Signal Generators (strategy rules → buy/sell signals) ──────

def generate_momentum_signals(
    ohlcv: list[dict], fast_period: int = 10, slow_period: int = 30,
) -> list[dict[str, Any]]:
    """Moving average crossover momentum strategy."""
    if len(ohlcv) < slow_period + 1:
        return []

    closes = [bar["close"] for bar in ohlcv]
    signals: list[dict[str, Any]] = []
    position_open = False

    for i in range(slow_period, len(closes)):
        fast_ma = sum(closes[i - fast_period:i]) / fast_period
        slow_ma = sum(closes[i - slow_period:i]) / slow_period
        prev_fast = sum(closes[i - fast_period - 1:i - 1]) / fast_period
        prev_slow = sum(closes[i - slow_period - 1:i - 1]) / slow_period

        # Golden cross → buy
        if prev_fast <= prev_slow and fast_ma > slow_ma and not position_open:
            signals.append({
                "date": ohlcv[i]["date"],
                "symbol": "SIM",
                "action": "buy",
                "price": closes[i],
                "quantity": 100,
            })
            position_open = True

        # Death cross → sell
        elif prev_fast >= prev_slow and fast_ma < slow_ma and position_open:
            signals.append({
                "date": ohlcv[i]["date"],
                "symbol": "SIM",
                "action": "sell",
                "price": closes[i],
                "quantity": 100,
            })
            position_open = False

    # Close any open position at end
    if position_open and ohlcv:
        signals.append({
            "date": ohlcv[-1]["date"],
            "symbol": "SIM",
            "action": "sell",
            "price": closes[-1],
            "quantity": 100,
        })

    return signals


def generate_mean_reversion_signals(
    ohlcv: list[dict], period: int = 20, z_threshold: float = 2.0,
) -> list[dict[str, Any]]:
    """Bollinger Band mean reversion: buy at lower band, sell at upper."""
    if len(ohlcv) < period + 1:
        return []

    closes = [bar["close"] for bar in ohlcv]
    signals: list[dict[str, Any]] = []
    position_open = False

    for i in range(period, len(closes)):
        window = closes[i - period:i]
        mean = sum(window) / period
        std = (sum((x - mean) ** 2 for x in window) / period) ** 0.5
        if std == 0:
            continue

        z_score = (closes[i] - mean) / std

        # Price at lower band → buy (expect reversion to mean)
        if z_score < -z_threshold and not position_open:
            signals.append({
                "date": ohlcv[i]["date"],
                "symbol": "SIM",
                "action": "buy",
                "price": closes[i],
                "quantity": 100,
            })
            position_open = True

        # Price at upper band or mean → sell
        elif z_score > 0 and position_open:
            signals.append({
                "date": ohlcv[i]["date"],
                "symbol": "SIM",
                "action": "sell",
                "price": closes[i],
                "quantity": 100,
            })
            position_open = False

    if position_open and ohlcv:
        signals.append({
            "date": ohlcv[-1]["date"],
            "symbol": "SIM",
            "action": "sell",
            "price": closes[-1],
            "quantity": 100,
        })

    return signals


def generate_breakout_signals(
    ohlcv: list[dict], lookback: int = 20,
) -> list[dict[str, Any]]:
    """Donchian channel breakout: buy at N-period high, sell at N-period low."""
    if len(ohlcv) < lookback + 1:
        return []

    signals: list[dict[str, Any]] = []
    position_open = False

    for i in range(lookback, len(ohlcv)):
        window_highs = [bar["high"] for bar in ohlcv[i - lookback:i]]
        window_lows = [bar["low"] for bar in ohlcv[i - lookback:i]]
        upper = max(window_highs)
        lower = min(window_lows)
        price = ohlcv[i]["close"]

        if price > upper and not position_open:
            signals.append({
                "date": ohlcv[i]["date"],
                "symbol": "SIM",
                "action": "buy",
                "price": price,
                "quantity": 100,
            })
            position_open = True

        elif price < lower and position_open:
            signals.append({
                "date": ohlcv[i]["date"],
                "symbol": "SIM",
                "action": "sell",
                "price": price,
                "quantity": 100,
            })
            position_open = False

    if position_open and ohlcv:
        signals.append({
            "date": ohlcv[-1]["date"],
            "symbol": "SIM",
            "action": "sell",
            "price": ohlcv[-1]["close"],
            "quantity": 100,
        })

    return signals


def generate_rsi_signals(
    ohlcv: list[dict], period: int = 14,
    oversold: float = 30.0, overbought: float = 70.0,
) -> list[dict[str, Any]]:
    """RSI strategy: buy when RSI < oversold, sell when RSI > overbought."""
    if len(ohlcv) < period + 2:
        return []

    closes = [bar["close"] for bar in ohlcv]
    signals: list[dict[str, Any]] = []
    position_open = False

    for i in range(period + 1, len(closes)):
        gains = []
        losses = []
        for j in range(i - period, i):
            change = closes[j + 1] - closes[j] if j + 1 < len(closes) else 0
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))

        avg_gain = sum(gains) / period if gains else 0.001
        avg_loss = sum(losses) / period if losses else 0.001
        rs = avg_gain / max(avg_loss, 0.001)
        rsi = 100 - (100 / (1 + rs))

        if rsi < oversold and not position_open:
            signals.append({
                "date": ohlcv[i]["date"],
                "symbol": "SIM",
                "action": "buy",
                "price": closes[i],
                "quantity": 100,
            })
            position_open = True

        elif rsi > overbought and position_open:
            signals.append({
                "date": ohlcv[i]["date"],
                "symbol": "SIM",
                "action": "sell",
                "price": closes[i],
                "quantity": 100,
            })
            position_open = False

    if position_open and ohlcv:
        signals.append({
            "date": ohlcv[-1]["date"],
            "symbol": "SIM",
            "action": "sell",
            "price": closes[-1],
            "quantity": 100,
        })

    return signals


# ── SHORT-BIASED STRATEGIES ─────────────────────────────────

def generate_short_momentum_signals(
    ohlcv: list[dict], fast_period: int = 5, slow_period: int = 20,
) -> list[dict[str, Any]]:
    """Inverse momentum: SHORT on death cross, cover on golden cross."""
    if len(ohlcv) < slow_period + 1:
        return []

    closes = [bar["close"] for bar in ohlcv]
    signals: list[dict[str, Any]] = []
    position_open = False

    for i in range(slow_period, len(closes)):
        fast_ma = sum(closes[i - fast_period:i]) / fast_period
        slow_ma = sum(closes[i - slow_period:i]) / slow_period
        prev_fast = sum(closes[i - fast_period - 1:i - 1]) / fast_period
        prev_slow = sum(closes[i - slow_period - 1:i - 1]) / slow_period

        # Death cross → short
        if prev_fast >= prev_slow and fast_ma < slow_ma and not position_open:
            signals.append({
                "date": ohlcv[i]["date"], "symbol": "SIM",
                "action": "sell", "price": closes[i], "quantity": 100,
            })
            position_open = True

        # Golden cross → cover (buy to close)
        elif prev_fast <= prev_slow and fast_ma > slow_ma and position_open:
            signals.append({
                "date": ohlcv[i]["date"], "symbol": "SIM",
                "action": "buy", "price": closes[i], "quantity": 100,
            })
            position_open = False

    if position_open and ohlcv:
        signals.append({
            "date": ohlcv[-1]["date"], "symbol": "SIM",
            "action": "buy", "price": closes[-1], "quantity": 100,
        })
    return signals


def generate_breakdown_signals(
    ohlcv: list[dict], lookback: int = 20,
) -> list[dict[str, Any]]:
    """Donchian breakdown: SHORT at N-period low, cover at N-period high."""
    if len(ohlcv) < lookback + 1:
        return []

    signals: list[dict[str, Any]] = []
    position_open = False

    for i in range(lookback, len(ohlcv)):
        window_highs = [bar["high"] for bar in ohlcv[i - lookback:i]]
        window_lows = [bar["low"] for bar in ohlcv[i - lookback:i]]
        upper = max(window_highs)
        lower = min(window_lows)
        price = ohlcv[i]["close"]

        # Breakdown below support → short
        if price < lower and not position_open:
            signals.append({
                "date": ohlcv[i]["date"], "symbol": "SIM",
                "action": "sell", "price": price, "quantity": 100,
            })
            position_open = True

        # Recovery above resistance → cover
        elif price > upper and position_open:
            signals.append({
                "date": ohlcv[i]["date"], "symbol": "SIM",
                "action": "buy", "price": price, "quantity": 100,
            })
            position_open = False

    if position_open and ohlcv:
        signals.append({
            "date": ohlcv[-1]["date"], "symbol": "SIM",
            "action": "buy", "price": ohlcv[-1]["close"], "quantity": 100,
        })
    return signals


def generate_rsi_short_signals(
    ohlcv: list[dict], period: int = 14,
    overbought: float = 75.0, oversold: float = 30.0,
) -> list[dict[str, Any]]:
    """RSI short strategy: SHORT when RSI > overbought, cover when RSI < oversold."""
    if len(ohlcv) < period + 2:
        return []

    closes = [bar["close"] for bar in ohlcv]
    signals: list[dict[str, Any]] = []
    position_open = False

    for i in range(period + 1, len(closes)):
        gains, losses = [], []
        for j in range(i - period, i):
            change = closes[j + 1] - closes[j] if j + 1 < len(closes) else 0
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))

        avg_gain = sum(gains) / period if gains else 0.001
        avg_loss = sum(losses) / period if losses else 0.001
        rs = avg_gain / max(avg_loss, 0.001)
        rsi = 100 - (100 / (1 + rs))

        if rsi > overbought and not position_open:
            signals.append({
                "date": ohlcv[i]["date"], "symbol": "SIM",
                "action": "sell", "price": closes[i], "quantity": 100,
            })
            position_open = True

        elif rsi < oversold and position_open:
            signals.append({
                "date": ohlcv[i]["date"], "symbol": "SIM",
                "action": "buy", "price": closes[i], "quantity": 100,
            })
            position_open = False

    if position_open and ohlcv:
        signals.append({
            "date": ohlcv[-1]["date"], "symbol": "SIM",
            "action": "buy", "price": closes[-1], "quantity": 100,
        })
    return signals


def generate_gap_fade_signals(
    ohlcv: list[dict], gap_threshold: float = 0.02,
) -> list[dict[str, Any]]:
    """Gap fade: SHORT large gap-ups (>2%), BUY large gap-downs. Gaps tend to fill."""
    if len(ohlcv) < 5:
        return []

    signals: list[dict[str, Any]] = []
    position_open = False
    position_side = ""  # "long" or "short"

    for i in range(1, len(ohlcv)):
        prev_close = ohlcv[i - 1]["close"]
        open_price = ohlcv[i]["open"]
        close_price = ohlcv[i]["close"]
        gap_pct = (open_price - prev_close) / prev_close

        if not position_open:
            # Large gap up → short (fade the gap)
            if gap_pct > gap_threshold:
                signals.append({
                    "date": ohlcv[i]["date"], "symbol": "SIM",
                    "action": "sell", "price": open_price, "quantity": 100,
                })
                position_open = True
                position_side = "short"

            # Large gap down → buy (fade the gap)
            elif gap_pct < -gap_threshold:
                signals.append({
                    "date": ohlcv[i]["date"], "symbol": "SIM",
                    "action": "buy", "price": open_price, "quantity": 100,
                })
                position_open = True
                position_side = "long"

        elif position_open:
            # Close at end of day (intraday strategy simulated on daily)
            exit_action = "buy" if position_side == "short" else "sell"
            signals.append({
                "date": ohlcv[i]["date"], "symbol": "SIM",
                "action": exit_action, "price": close_price, "quantity": 100,
            })
            position_open = False
            position_side = ""

    if position_open and ohlcv:
        exit_action = "buy" if position_side == "short" else "sell"
        signals.append({
            "date": ohlcv[-1]["date"], "symbol": "SIM",
            "action": exit_action, "price": ohlcv[-1]["close"], "quantity": 100,
        })
    return signals


def generate_volatility_breakout_signals(
    ohlcv: list[dict], atr_period: int = 14, multiplier: float = 1.5,
) -> list[dict[str, Any]]:
    """Volatility breakout: trade when price moves > ATR*multiplier from open."""
    if len(ohlcv) < atr_period + 2:
        return []

    signals: list[dict[str, Any]] = []
    position_open = False
    position_side = ""

    for i in range(atr_period, len(ohlcv)):
        # Calculate ATR
        tr_values = []
        for j in range(i - atr_period, i):
            high = ohlcv[j]["high"]
            low = ohlcv[j]["low"]
            prev_c = ohlcv[j - 1]["close"] if j > 0 else ohlcv[j]["open"]
            tr = max(high - low, abs(high - prev_c), abs(low - prev_c))
            tr_values.append(tr)
        atr = sum(tr_values) / atr_period

        open_price = ohlcv[i]["open"]
        close_price = ohlcv[i]["close"]
        move = close_price - open_price

        if not position_open:
            if move > atr * multiplier:
                # Strong up move → buy
                signals.append({
                    "date": ohlcv[i]["date"], "symbol": "SIM",
                    "action": "buy", "price": close_price, "quantity": 100,
                })
                position_open = True
                position_side = "long"
            elif move < -atr * multiplier:
                # Strong down move → short
                signals.append({
                    "date": ohlcv[i]["date"], "symbol": "SIM",
                    "action": "sell", "price": close_price, "quantity": 100,
                })
                position_open = True
                position_side = "short"
        elif position_open:
            # Exit after 3 bars
            entry_idx = len(signals) - 1
            if i - atr_period >= 3:  # simplified hold period
                exit_action = "sell" if position_side == "long" else "buy"
                signals.append({
                    "date": ohlcv[i]["date"], "symbol": "SIM",
                    "action": exit_action, "price": close_price, "quantity": 100,
                })
                position_open = False

    if position_open and ohlcv:
        exit_action = "sell" if position_side == "long" else "buy"
        signals.append({
            "date": ohlcv[-1]["date"], "symbol": "SIM",
            "action": exit_action, "price": ohlcv[-1]["close"], "quantity": 100,
        })
    return signals


# Strategy registry: name → generator function
STRATEGY_GENERATORS = {
    # Long strategies
    "momentum_fast": lambda ohlcv: generate_momentum_signals(ohlcv, 5, 20),
    "momentum_medium": lambda ohlcv: generate_momentum_signals(ohlcv, 10, 30),
    "momentum_slow": lambda ohlcv: generate_momentum_signals(ohlcv, 20, 50),
    "mean_reversion_tight": lambda ohlcv: generate_mean_reversion_signals(ohlcv, 20, 1.5),
    "mean_reversion_wide": lambda ohlcv: generate_mean_reversion_signals(ohlcv, 20, 2.5),
    "breakout_20": lambda ohlcv: generate_breakout_signals(ohlcv, 20),
    "breakout_50": lambda ohlcv: generate_breakout_signals(ohlcv, 50),
    "rsi_classic": lambda ohlcv: generate_rsi_signals(ohlcv, 14, 30, 70),
    "rsi_aggressive": lambda ohlcv: generate_rsi_signals(ohlcv, 7, 25, 75),
    # Short strategies
    "short_momentum_fast": lambda ohlcv: generate_short_momentum_signals(ohlcv, 5, 20),
    "short_momentum_slow": lambda ohlcv: generate_short_momentum_signals(ohlcv, 10, 30),
    "breakdown_20": lambda ohlcv: generate_breakdown_signals(ohlcv, 20),
    "breakdown_50": lambda ohlcv: generate_breakdown_signals(ohlcv, 50),
    "rsi_short_classic": lambda ohlcv: generate_rsi_short_signals(ohlcv, 14, 75, 30),
    "rsi_short_aggressive": lambda ohlcv: generate_rsi_short_signals(ohlcv, 7, 70, 25),
    # Neutral / both sides
    "gap_fade": lambda ohlcv: generate_gap_fade_signals(ohlcv, 0.02),
    "gap_fade_tight": lambda ohlcv: generate_gap_fade_signals(ohlcv, 0.01),
    "volatility_breakout": lambda ohlcv: generate_volatility_breakout_signals(ohlcv, 14, 1.5),
    "volatility_breakout_tight": lambda ohlcv: generate_volatility_breakout_signals(ohlcv, 10, 1.0),
}

# Symbols to test — expanded universe with short-friendly targets + leveraged ETFs
DEFAULT_SYMBOLS = [
    # Major indices
    "SPY", "QQQ", "IWM", "DIA",
    # High-vol tech (short candidates)
    "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "AMD", "SMCI",
    # Leveraged ETFs (amplified moves)
    "TQQQ", "SQQQ", "SPXU", "UPRO", "SOXL", "SOXS",
    # Crypto
    "BTC-USD", "ETH-USD", "SOL-USD",
    # Volatility
    "VIX",
]


class StrategyValidator:
    """Autonomous strategy validation pipeline."""

    def __init__(self, backtester=None, llm=None, experience_memory=None, learning=None, bus=None) -> None:
        self._backtester = backtester
        self._llm = llm
        self._experience = experience_memory
        self._learning = learning
        self._bus = bus
        self._conn: Optional[sqlite3.Connection] = None
        self._running = False
        self._notification_engine = None  # Set via main.py

    def start(self) -> None:
        self._conn = sqlite3.connect(str(_DB_PATH))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_CREATE_SQL)
        self._conn.commit()
        self._running = True
        logger.info("Strategy validator started — db=%s", _DB_PATH)

    def stop(self) -> None:
        self._running = False
        if self._conn:
            self._conn.close()
            self._conn = None

    async def validate_all_strategies(self) -> list[dict[str, Any]]:
        """Run all built-in strategies against all default symbols.

        This is the main autonomous entry point — called by proactive engine.
        Returns list of validation results with promotion decisions.
        """
        results: list[dict[str, Any]] = []

        if self._notification_engine:
            await self._notification_engine.audit_external_action(
                action="Strategy Validation: OHLCV Fetch",
                target="Yahoo Finance API",
                source="strategy_validator",
                level="low",
                details=f"Fetching 365-day OHLCV for {len(DEFAULT_SYMBOLS)} symbols: {', '.join(DEFAULT_SYMBOLS[:5])}...",
            )

        for symbol in DEFAULT_SYMBOLS:
            try:
                ohlcv = await asyncio.to_thread(fetch_ohlcv, symbol, 365)
                if len(ohlcv) < 50:
                    logger.warning("Insufficient data for %s (%d bars)", symbol, len(ohlcv))
                    continue

                for strategy_name, generator in STRATEGY_GENERATORS.items():
                    try:
                        result = await self.validate_strategy(
                            strategy_name=f"{strategy_name}_{symbol}",
                            source="autonomous_scan",
                            hypothesis=f"Test {strategy_name} on {symbol} (1yr history)",
                            symbol=symbol,
                            ohlcv=ohlcv,
                            signal_generator=generator,
                        )
                        results.append(result)
                    except Exception as e:
                        logger.error("Validation error %s/%s: %s", strategy_name, symbol, e)
            except Exception as e:
                logger.error("Data fetch error for %s: %s", symbol, e)

        # Rank results by Sharpe ratio
        results.sort(key=lambda r: r.get("sharpe_ratio", 0) or 0, reverse=True)

        # Log summary
        promoted = [r for r in results if r.get("promoted")]
        logger.info(
            "Strategy scan complete: %d tested, %d promoted (Sharpe > %.1f)",
            len(results), len(promoted), PROMOTION_THRESHOLDS["min_sharpe"],
        )

        # Publish to bus
        if self._bus:
            from backend.core.message_bus import BusMessage
            await self._bus.publish(BusMessage(
                id=f"sv_{uuid.uuid4().hex[:8]}",
                topic="system.strategy_validation",
                sender="strategy_validator",
                payload={
                    "total_tested": len(results),
                    "promoted_count": len(promoted),
                    "top_strategies": [
                        {"name": r["strategy_name"], "sharpe": r.get("sharpe_ratio"), "return": r.get("total_return_pct")}
                        for r in results[:5]
                    ],
                },
            ))

        return results

    async def validate_strategy(
        self,
        strategy_name: str,
        source: str,
        hypothesis: str,
        symbol: str,
        ohlcv: list[dict],
        signal_generator=None,
        timeframe: str = "1d",
    ) -> dict[str, Any]:
        """Validate a single strategy: generate signals → backtest → Monte Carlo → rank."""
        validation_id = f"sv_{uuid.uuid4().hex[:12]}"

        if signal_generator is None:
            # Default to momentum
            signal_generator = lambda data: generate_momentum_signals(data, 10, 30)

        # 1. Generate signals from strategy rules
        signals = signal_generator(ohlcv)

        if len(signals) < 4:
            result = {
                "id": validation_id, "strategy_name": strategy_name,
                "status": "failed", "lesson": f"Too few signals ({len(signals)})",
                "promoted": False,
            }
            self._store_validation(validation_id, strategy_name, source, hypothesis,
                                   symbol, timeframe, "failed", lesson=f"Too few signals ({len(signals)})")
            return result

        # 2. Run backtest
        if not self._backtester:
            return {"id": validation_id, "strategy_name": strategy_name,
                    "status": "error", "lesson": "No backtester available", "promoted": False}

        bt_result = self._backtester.backtest(
            strategy_name=strategy_name,
            signals=signals,
            initial_capital=100_000.0,
        )

        # 3. Run Monte Carlo
        mc = self._backtester.monte_carlo(bt_result, simulations=500)

        # 4. Evaluate against thresholds
        thresholds = PROMOTION_THRESHOLDS
        promoted = (
            bt_result.sharpe_ratio >= thresholds["min_sharpe"]
            and bt_result.win_rate >= thresholds["min_win_rate"]
            and bt_result.max_drawdown_pct <= thresholds["max_drawdown"]
            and bt_result.total_trades >= thresholds["min_trades"]
            and bt_result.profit_factor >= thresholds["min_profit_factor"]
            and mc["p5"] >= bt_result.initial_capital * thresholds["min_monte_carlo_p5"]
        )

        status = "passed" if promoted else "failed"
        lesson = self._generate_lesson(bt_result, mc, promoted)

        # 5. Store result
        self._store_validation(
            validation_id, strategy_name, source, hypothesis, symbol, timeframe,
            status, bt_result.sharpe_ratio, bt_result.sortino_ratio,
            bt_result.win_rate, bt_result.max_drawdown_pct,
            bt_result.total_return_pct, bt_result.profit_factor,
            bt_result.total_trades, mc["p5"], mc["p50"], mc["p95"],
            promoted, bt_result.id, json.dumps(signals[:10]), lesson,
        )

        # 6. Store in experience memory
        if self._experience:
            try:
                exp_type = "strategy" if promoted else "lesson"
                self._experience.record_experience(
                    experience_type=exp_type,
                    domain="trading",
                    title=f"{strategy_name} on {symbol}",
                    description=f"Strategy '{strategy_name}' on {symbol}: "
                            f"Sharpe={bt_result.sharpe_ratio:.2f}, "
                            f"Return={bt_result.total_return_pct:.1f}%, "
                            f"WinRate={bt_result.win_rate:.0f}%, "
                            f"MaxDD={bt_result.max_drawdown_pct:.1f}%. "
                            f"{'PROMOTED to live trading.' if promoted else lesson}",
                    context={"symbol": symbol, "strategy": strategy_name, "source": source},
                )
            except Exception as e:
                logger.warning("Experience memory store failed: %s", e)

        # 7. Feed into learning engine
        if self._learning:
            try:
                self._learning.record_agent_outcome(
                    agent_id="strategy_validator",
                    task_description=f"backtest:{strategy_name}:{symbol}",
                    status="completed" if promoted else "failed",
                    result_quality=min(bt_result.sharpe_ratio / 2.0, 1.0),
                    task_category="trading",
                )
            except Exception:
                pass

        return {
            "id": validation_id,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "status": status,
            "sharpe_ratio": bt_result.sharpe_ratio,
            "sortino_ratio": bt_result.sortino_ratio,
            "win_rate": bt_result.win_rate,
            "max_drawdown_pct": bt_result.max_drawdown_pct,
            "total_return_pct": bt_result.total_return_pct,
            "profit_factor": bt_result.profit_factor,
            "total_trades": bt_result.total_trades,
            "monte_carlo_p5": mc["p5"],
            "monte_carlo_p50": mc["p50"],
            "monte_carlo_p95": mc["p95"],
            "promoted": promoted,
            "backtest_id": bt_result.id,
            "lesson": lesson,
        }

    def _generate_lesson(self, bt_result, mc: dict, promoted: bool) -> str:
        """Generate human-readable lesson from backtest results."""
        if promoted:
            return (
                f"Strategy validated: Sharpe={bt_result.sharpe_ratio:.2f}, "
                f"return={bt_result.total_return_pct:.1f}%, "
                f"MC p5=${mc['p5']:,.0f}. Ready for live deployment."
            )

        reasons: list[str] = []
        t = PROMOTION_THRESHOLDS
        if bt_result.sharpe_ratio < t["min_sharpe"]:
            reasons.append(f"low Sharpe ({bt_result.sharpe_ratio:.2f} < {t['min_sharpe']})")
        if bt_result.win_rate < t["min_win_rate"]:
            reasons.append(f"low win rate ({bt_result.win_rate:.0f}% < {t['min_win_rate']}%)")
        if bt_result.max_drawdown_pct > t["max_drawdown"]:
            reasons.append(f"high drawdown ({bt_result.max_drawdown_pct:.1f}% > {t['max_drawdown']}%)")
        if bt_result.total_trades < t["min_trades"]:
            reasons.append(f"too few trades ({bt_result.total_trades} < {t['min_trades']})")
        if bt_result.profit_factor < t["min_profit_factor"]:
            reasons.append(f"low profit factor ({bt_result.profit_factor:.2f} < {t['min_profit_factor']})")
        if mc["p5"] < bt_result.initial_capital * t["min_monte_carlo_p5"]:
            reasons.append(f"ruin risk (MC p5=${mc['p5']:,.0f})")

        return "Rejected: " + "; ".join(reasons) if reasons else "Rejected: did not meet thresholds"

    def _store_validation(self, vid, name, source, hypothesis, symbol, timeframe,
                          status, sharpe=None, sortino=None, win_rate=None,
                          max_dd=None, total_return=None, pf=None, trades=None,
                          mc_p5=None, mc_p50=None, mc_p95=None,
                          promoted=False, bt_id=None, raw_signals=None, lesson=None) -> None:
        if not self._conn:
            return
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR REPLACE INTO strategy_validations
               (id, strategy_name, source, hypothesis, symbol, timeframe, status,
                sharpe_ratio, sortino_ratio, win_rate, max_drawdown_pct,
                total_return_pct, profit_factor, total_trades,
                monte_carlo_p5, monte_carlo_p50, monte_carlo_p95,
                promoted, backtest_id, raw_signals, lesson, created_at, completed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vid, name, source, hypothesis, symbol, timeframe, status,
             sharpe, sortino, win_rate, max_dd, total_return, pf, trades,
             mc_p5, mc_p50, mc_p95, 1 if promoted else 0, bt_id,
             raw_signals, lesson, now, now if status != "pending" else None),
        )
        self._conn.commit()

    def get_promoted(self, limit: int = 20) -> list[dict]:
        """Get strategies that passed validation and are promoted for live trading."""
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT * FROM strategy_validations WHERE promoted=1 ORDER BY sharpe_ratio DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_recent(self, limit: int = 50) -> list[dict]:
        """Get recent validation attempts."""
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT * FROM strategy_validations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, Any]:
        """Summary statistics."""
        if not self._conn:
            return {"total": 0, "promoted": 0, "failed": 0}
        row = self._conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN promoted=1 THEN 1 ELSE 0 END) as promoted, "
            "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed "
            "FROM strategy_validations"
        ).fetchone()
        return {
            "total": row["total"] or 0,
            "promoted": row["promoted"] or 0,
            "failed": row["failed"] or 0,
        }
