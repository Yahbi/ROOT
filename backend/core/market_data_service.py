"""Comprehensive market data service with multi-source aggregation and technical indicators."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
import numpy as np

logger = logging.getLogger("root.market_data")

_YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
_FINNHUB_BASE = "https://finnhub.io/api/v1"
_ALPACA_BASE = "https://paper-api.alpaca.markets"

# Map user-friendly intervals to Yahoo Finance parameters
_YAHOO_INTERVAL_MAP: dict[str, tuple[str, str]] = {
    "1m": ("1m", "1d"),
    "5m": ("5m", "5d"),
    "15m": ("15m", "5d"),
    "30m": ("30m", "1mo"),
    "1h": ("1h", "1mo"),
    "1d": ("1d", "1y"),
    "1wk": ("1wk", "5y"),
    "1mo": ("1mo", "10y"),
}


@dataclass(frozen=True)
class Candle:
    """Single OHLCV candle."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class IndicatorResult:
    """Technical indicator calculation result."""
    sma_10: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None
    rsi_14: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bollinger_upper: float | None = None
    bollinger_middle: float | None = None
    bollinger_lower: float | None = None
    atr_14: float | None = None
    volume_sma_20: float | None = None


class MarketDataService:
    """Aggregates market data from Yahoo Finance, Finnhub, and Alpaca."""

    def __init__(
        self,
        finnhub_api_key: str = "",
        alpaca_api_key: str = "",
        alpaca_api_secret: str = "",
    ) -> None:
        self._finnhub_key = finnhub_api_key or os.getenv("FINNHUB_API_KEY", "")
        self._alpaca_key = alpaca_api_key or os.getenv("ALPACA_API_KEY", "")
        self._alpaca_secret = alpaca_api_secret or os.getenv("ALPACA_API_SECRET", "")
        self._request_count = 0
        self._error_count = 0
        self._last_request_ts: float = 0.0

    # ── Public API ─────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> dict:
        """Get current price from best available source.

        Priority: Finnhub (real-time) -> Yahoo (delayed) -> Alpaca (market hours only).
        """
        symbol = symbol.upper().strip()
        if not symbol:
            return {"error": "symbol is required"}

        # Try Finnhub first (real-time)
        if self._finnhub_key:
            quote = await self._finnhub_quote(symbol)
            if "error" not in quote and quote.get("current_price"):
                quote["source"] = "finnhub"
                return quote

        # Fallback to Yahoo Finance
        yahoo_quote = await self._yahoo_quote(symbol)
        if "error" not in yahoo_quote and yahoo_quote.get("current_price"):
            yahoo_quote["source"] = "yahoo"
            return yahoo_quote

        # Last resort: Alpaca
        if self._alpaca_key:
            alpaca_quote = await self._alpaca_quote(symbol)
            if "error" not in alpaca_quote:
                alpaca_quote["source"] = "alpaca"
                return alpaca_quote

        return {"error": f"Could not fetch quote for {symbol} from any source"}

    async def get_ohlcv(
        self, symbol: str, interval: str = "1d", limit: int = 100
    ) -> list[dict]:
        """Get OHLCV candles from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol.
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo).
            limit: Maximum number of candles to return.

        Returns:
            List of dicts with timestamp, open, high, low, close, volume.
        """
        symbol = symbol.upper().strip()
        if not symbol:
            return []

        yahoo_interval, yahoo_range = _YAHOO_INTERVAL_MAP.get(interval, ("1d", "1y"))
        candles = await self._yahoo_ohlcv(symbol, yahoo_interval, yahoo_range)

        if not candles:
            return []

        # Trim to requested limit (take most recent)
        if len(candles) > limit:
            candles = candles[-limit:]

        return candles

    def calculate_indicators(self, candles: list[dict]) -> dict:
        """Calculate technical indicators from OHLCV data.

        Computes SMA, EMA, RSI, MACD, Bollinger Bands, ATR, and Volume SMA
        from a list of candle dicts.
        """
        if not candles or len(candles) < 2:
            return {"error": "Insufficient data for indicator calculation", "candles": len(candles) if candles else 0}

        closes = np.array([c["close"] for c in candles], dtype=np.float64)
        highs = np.array([c["high"] for c in candles], dtype=np.float64)
        lows = np.array([c["low"] for c in candles], dtype=np.float64)
        volumes = np.array([c["volume"] for c in candles], dtype=np.float64)

        result: dict[str, Any] = {}

        # ── SMA (Simple Moving Average) ───────────────────────
        for period in (10, 20, 50, 200):
            sma = self._calc_sma(closes, period)
            result[f"sma_{period}"] = round(sma, 4) if sma is not None else None

        # ── EMA (Exponential Moving Average) ───────────────────
        for period in (12, 26):
            ema = self._calc_ema(closes, period)
            result[f"ema_{period}"] = round(ema, 4) if ema is not None else None

        # ── RSI (Relative Strength Index, 14 period) ──────────
        rsi = self._calc_rsi(closes, 14)
        result["rsi_14"] = round(rsi, 2) if rsi is not None else None

        # ── MACD (12, 26, 9) ──────────────────────────────────
        macd_line, macd_signal, macd_hist = self._calc_macd(closes, 12, 26, 9)
        result["macd"] = {
            "line": round(macd_line, 4) if macd_line is not None else None,
            "signal": round(macd_signal, 4) if macd_signal is not None else None,
            "histogram": round(macd_hist, 4) if macd_hist is not None else None,
        }

        # ── Bollinger Bands (20 period, 2 std) ────────────────
        bb_upper, bb_middle, bb_lower = self._calc_bollinger(closes, 20, 2.0)
        result["bollinger_bands"] = {
            "upper": round(bb_upper, 4) if bb_upper is not None else None,
            "middle": round(bb_middle, 4) if bb_middle is not None else None,
            "lower": round(bb_lower, 4) if bb_lower is not None else None,
        }

        # ── ATR (Average True Range, 14 period) ───────────────
        atr = self._calc_atr(highs, lows, closes, 14)
        result["atr_14"] = round(atr, 4) if atr is not None else None

        # ── Volume SMA (20 period) ────────────────────────────
        vol_sma = self._calc_sma(volumes, 20)
        result["volume_sma_20"] = round(vol_sma, 0) if vol_sma is not None else None

        # ── Meta ──────────────────────────────────────────────
        result["candle_count"] = len(candles)
        result["latest_close"] = round(float(closes[-1]), 4)
        result["latest_volume"] = int(volumes[-1])

        return result

    async def get_full_analysis(self, symbol: str) -> dict:
        """Get quote + OHLCV candles + all technical indicators in one call."""
        symbol = symbol.upper().strip()
        if not symbol:
            return {"error": "symbol is required"}

        # Fetch quote and candles concurrently
        import asyncio
        quote_task = asyncio.create_task(self.get_quote(symbol))
        candles_task = asyncio.create_task(self.get_ohlcv(symbol, interval="1d", limit=200))

        quote = await quote_task
        candles = await candles_task

        result: dict[str, Any] = {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "quote": quote,
        }

        if candles:
            indicators = self.calculate_indicators(candles)
            result["indicators"] = indicators
            result["candle_count"] = len(candles)
        else:
            result["indicators"] = {"error": "No candle data available"}
            result["candle_count"] = 0

        return result

    def stats(self) -> dict:
        """Return service statistics."""
        return {
            "requests": self._request_count,
            "errors": self._error_count,
            "last_request": self._last_request_ts,
            "sources": {
                "finnhub": bool(self._finnhub_key),
                "alpaca": bool(self._alpaca_key),
                "yahoo": True,  # always available (no key required)
            },
        }

    # ── Technical Indicator Calculations ───────────────────────

    @staticmethod
    def _calc_sma(data: np.ndarray, period: int) -> float | None:
        """Simple Moving Average — mean of the last `period` values."""
        if len(data) < period:
            return None
        return float(np.mean(data[-period:]))

    @staticmethod
    def _calc_ema(data: np.ndarray, period: int) -> float | None:
        """Exponential Moving Average using the standard multiplier.

        EMA_t = close * k + EMA_{t-1} * (1 - k)  where k = 2 / (period + 1)
        Seeded with SMA of the first `period` values.
        """
        if len(data) < period:
            return None
        k = 2.0 / (period + 1)
        ema = float(np.mean(data[:period]))  # seed with SMA
        for i in range(period, len(data)):
            ema = float(data[i]) * k + ema * (1.0 - k)
        return ema

    @staticmethod
    def _calc_ema_series(data: np.ndarray, period: int) -> np.ndarray | None:
        """Return full EMA series (same length as data, NaN-padded at start)."""
        if len(data) < period:
            return None
        k = 2.0 / (period + 1)
        ema_series = np.full(len(data), np.nan)
        ema_series[period - 1] = np.mean(data[:period])
        for i in range(period, len(data)):
            ema_series[i] = data[i] * k + ema_series[i - 1] * (1.0 - k)
        return ema_series

    @staticmethod
    def _calc_rsi(closes: np.ndarray, period: int = 14) -> float | None:
        """Relative Strength Index.

        RSI = 100 - (100 / (1 + avg_gain / avg_loss))
        Uses Wilder's smoothing (exponential moving average of gains/losses).
        """
        if len(closes) < period + 1:
            return None

        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Wilder's smoothing: first average is SMA, then EMA with alpha = 1/period
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _calc_macd(
        self, closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[float | None, float | None, float | None]:
        """MACD (Moving Average Convergence Divergence).

        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(signal) of MACD Line
        Histogram = MACD Line - Signal Line
        """
        if len(closes) < slow + signal:
            return None, None, None

        ema_fast = self._calc_ema_series(closes, fast)
        ema_slow = self._calc_ema_series(closes, slow)
        if ema_fast is None or ema_slow is None:
            return None, None, None

        # MACD line starts where both EMAs are valid
        macd_line = ema_fast - ema_slow
        # Remove NaN values for signal calculation
        valid_start = slow - 1  # first index where both EMAs have values
        macd_valid = macd_line[valid_start:]

        if len(macd_valid) < signal:
            return float(macd_line[-1]) if not np.isnan(macd_line[-1]) else None, None, None

        # Signal line = EMA of MACD line
        signal_series = self._calc_ema_series(macd_valid, signal)
        if signal_series is None:
            return float(macd_line[-1]), None, None

        macd_val = float(macd_line[-1])
        signal_val = float(signal_series[-1]) if not np.isnan(signal_series[-1]) else None
        hist_val = macd_val - signal_val if signal_val is not None else None

        return macd_val, signal_val, hist_val

    @staticmethod
    def _calc_bollinger(
        closes: np.ndarray, period: int = 20, num_std: float = 2.0
    ) -> tuple[float | None, float | None, float | None]:
        """Bollinger Bands.

        Middle = SMA(period)
        Upper = Middle + num_std * StdDev(period)
        Lower = Middle - num_std * StdDev(period)
        """
        if len(closes) < period:
            return None, None, None
        window = closes[-period:]
        middle = float(np.mean(window))
        std = float(np.std(window, ddof=0))
        upper = middle + num_std * std
        lower = middle - num_std * std
        return upper, middle, lower

    @staticmethod
    def _calc_atr(
        highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
    ) -> float | None:
        """Average True Range.

        True Range = max(H-L, |H-prevC|, |L-prevC|)
        ATR = EMA of True Range over `period` (Wilder's smoothing).
        """
        if len(closes) < period + 1:
            return None

        # Calculate true range for each bar (starting from index 1)
        tr = np.zeros(len(closes) - 1)
        for i in range(len(tr)):
            h = highs[i + 1]
            l = lows[i + 1]
            prev_c = closes[i]
            tr[i] = max(h - l, abs(h - prev_c), abs(l - prev_c))

        if len(tr) < period:
            return None

        # Wilder's smoothing (same as RSI smoothing)
        atr = float(np.mean(tr[:period]))
        for i in range(period, len(tr)):
            atr = (atr * (period - 1) + tr[i]) / period
        return atr

    # ── Data Source: Yahoo Finance ─────────────────────────────

    async def _yahoo_ohlcv(
        self, symbol: str, interval: str, range_str: str
    ) -> list[dict]:
        """Fetch OHLCV candles from Yahoo Finance v8 API."""
        url = f"{_YAHOO_BASE}/{symbol}"
        params = {"interval": interval, "range": range_str}
        try:
            self._request_count += 1
            self._last_request_ts = time.time()
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )
                if resp.status_code >= 400:
                    self._error_count += 1
                    logger.warning("Yahoo Finance %s: HTTP %d", symbol, resp.status_code)
                    return []
                data = resp.json()
        except Exception as e:
            self._error_count += 1
            logger.warning("Yahoo Finance request failed for %s: %s", symbol, e)
            return []

        try:
            chart = data["chart"]["result"][0]
            timestamps = chart["timestamp"]
            ohlcv = chart["indicators"]["quote"][0]
            candles = []
            for i in range(len(timestamps)):
                o = ohlcv["open"][i]
                h = ohlcv["high"][i]
                l = ohlcv["low"][i]
                c = ohlcv["close"][i]
                v = ohlcv["volume"][i]
                # Skip candles with None values
                if any(x is None for x in (o, h, l, c)):
                    continue
                candles.append({
                    "timestamp": timestamps[i],
                    "open": round(float(o), 4),
                    "high": round(float(h), 4),
                    "low": round(float(l), 4),
                    "close": round(float(c), 4),
                    "volume": int(v) if v is not None else 0,
                })
            return candles
        except (KeyError, IndexError, TypeError) as e:
            self._error_count += 1
            logger.warning("Yahoo Finance parse error for %s: %s", symbol, e)
            return []

    async def _yahoo_quote(self, symbol: str) -> dict:
        """Get a quick quote from Yahoo Finance using the chart endpoint."""
        candles = await self._yahoo_ohlcv(symbol, "1d", "5d")
        if not candles:
            return {"error": "No Yahoo data"}
        latest = candles[-1]
        prev_close = candles[-2]["close"] if len(candles) >= 2 else latest["open"]
        change = latest["close"] - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {
            "symbol": symbol,
            "current_price": latest["close"],
            "change": round(change, 4),
            "change_percent": round(change_pct, 2),
            "high": latest["high"],
            "low": latest["low"],
            "open": latest["open"],
            "previous_close": prev_close,
            "volume": latest["volume"],
        }

    # ── Data Source: Finnhub ───────────────────────────────────

    async def _finnhub_quote(self, symbol: str) -> dict:
        """Get real-time quote from Finnhub."""
        try:
            self._request_count += 1
            self._last_request_ts = time.time()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_FINNHUB_BASE}/quote",
                    params={"symbol": symbol, "token": self._finnhub_key},
                )
                if resp.status_code >= 400:
                    self._error_count += 1
                    return {"error": f"Finnhub HTTP {resp.status_code}"}
                data = resp.json()
        except Exception as e:
            self._error_count += 1
            return {"error": f"Finnhub request failed: {e}"}

        # Finnhub returns c=0 for invalid symbols
        if not data.get("c"):
            return {"error": "No Finnhub data for symbol"}

        return {
            "symbol": symbol,
            "current_price": data.get("c"),
            "change": data.get("d"),
            "change_percent": data.get("dp"),
            "high": data.get("h"),
            "low": data.get("l"),
            "open": data.get("o"),
            "previous_close": data.get("pc"),
        }

    # ── Data Source: Alpaca ────────────────────────────────────

    async def _alpaca_quote(self, symbol: str) -> dict:
        """Get latest trade from Alpaca."""
        if not self._alpaca_key:
            return {"error": "No Alpaca API key"}
        try:
            self._request_count += 1
            self._last_request_ts = time.time()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
                    headers={
                        "APCA-API-KEY-ID": self._alpaca_key,
                        "APCA-API-SECRET-KEY": self._alpaca_secret,
                    },
                )
                if resp.status_code >= 400:
                    self._error_count += 1
                    return {"error": f"Alpaca HTTP {resp.status_code}"}
                data = resp.json()
        except Exception as e:
            self._error_count += 1
            return {"error": f"Alpaca request failed: {e}"}

        trade = data.get("trade", {})
        return {
            "symbol": symbol,
            "current_price": trade.get("p"),
            "size": trade.get("s"),
            "timestamp": trade.get("t"),
        }
