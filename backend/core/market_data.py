"""
Market Data Service — financial data fetching with caching.

Uses yfinance as the primary free data source. Provides:
- Price history (OHLCV)
- Financial metrics (P/E, P/B, margins, growth)
- Insider trades
- News/sentiment
- Company info
- Real-time quotes

All data is cached in-memory with TTL to avoid rate limiting.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

logger = logging.getLogger("root.market_data")

# In-memory cache with TTL + thread safety
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes for real-time, 3600 for historical
_CACHE_MAX_SIZE = 5000


def _cache_get(key: str, ttl: int = _CACHE_TTL) -> Any:
    with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if time.time() - ts < ttl:
                return val
    return None


def _cache_set(key: str, val: Any) -> None:
    with _cache_lock:
        # Evict oldest entries if cache is too large
        if len(_cache) > _CACHE_MAX_SIZE:
            oldest = sorted(_cache, key=lambda k: _cache[k][0])[:500]
            for k in oldest:
                del _cache[k]
        _cache[key] = (time.time(), val)


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class PriceBar:
    """Single OHLCV bar."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class Quote:
    """Real-time quote snapshot."""
    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class FinancialMetrics:
    """Key financial metrics for fundamental analysis."""
    symbol: str
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    gross_margin: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    avg_volume: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None


@dataclass(frozen=True)
class InsiderTrade:
    """Insider trading record."""
    symbol: str
    insider_name: str
    title: str
    transaction_type: str  # "Buy" | "Sell"
    shares: int
    price: float
    value: float
    date: str


@dataclass(frozen=True)
class NewsItem:
    """News article."""
    title: str
    source: str
    url: str
    published: str
    symbol: Optional[str] = None
    sentiment: Optional[str] = None  # "positive" | "negative" | "neutral"


# ── MarketDataService ────────────────────────────────────────

class MarketDataService:
    """Unified financial data provider."""

    def __init__(self) -> None:
        self._yf = None
        self._initialized = False

    def _ensure_yfinance(self):
        """Lazy-load yfinance."""
        if self._yf is None:
            try:
                import yfinance as yf
                self._yf = yf
                self._initialized = True
            except ImportError:
                logger.warning("yfinance not installed — market data unavailable. pip install yfinance")
                raise ImportError("yfinance required: pip install yfinance")

    def get_price_history(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> list[PriceBar]:
        """Fetch OHLCV price history."""
        cache_key = f"prices:{symbol}:{period}:{interval}"
        cached = _cache_get(cache_key, ttl=3600)
        if cached is not None:
            return cached

        self._ensure_yfinance()
        try:
            ticker = self._yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                return []

            bars = []
            for date_idx, row in df.iterrows():
                bars.append(PriceBar(
                    date=str(date_idx.date()) if hasattr(date_idx, 'date') else str(date_idx),
                    open=round(float(row.get("Open", 0)), 2),
                    high=round(float(row.get("High", 0)), 2),
                    low=round(float(row.get("Low", 0)), 2),
                    close=round(float(row.get("Close", 0)), 2),
                    volume=int(row.get("Volume", 0)),
                ))
            _cache_set(cache_key, bars)
            return bars
        except Exception as e:
            logger.error("Price fetch failed for %s: %s", symbol, e)
            return []

    def get_closes(self, symbol: str, period: str = "6mo") -> list[float]:
        """Get just closing prices as a flat list."""
        bars = self.get_price_history(symbol, period=period)
        return [b.close for b in bars]

    def get_returns(self, symbol: str, period: str = "6mo") -> list[float]:
        """Get daily returns as a flat list."""
        closes = self.get_closes(symbol, period=period)
        if len(closes) < 2:
            return []
        arr = np.array(closes, dtype=np.float64)
        prev = arr[:-1]
        prev[prev == 0] = np.nan  # Guard against zero prices
        returns = np.diff(arr) / prev
        return [r for r in returns.tolist() if not np.isnan(r)]

    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Fetch real-time quote."""
        cache_key = f"quote:{symbol}"
        cached = _cache_get(cache_key, ttl=60)
        if cached is not None:
            return cached

        self._ensure_yfinance()
        try:
            ticker = self._yf.Ticker(symbol)
            info = ticker.info
            if not info or "currentPrice" not in info and "regularMarketPrice" not in info:
                # Try fast_info
                fast = ticker.fast_info
                price = float(getattr(fast, "last_price", 0) or 0)
                prev_close = float(getattr(fast, "previous_close", price) or price)
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                q = Quote(
                    symbol=symbol.upper(),
                    price=round(price, 2),
                    change=round(change, 2),
                    change_pct=round(change_pct, 2),
                    volume=int(getattr(fast, "last_volume", 0) or 0),
                    market_cap=float(getattr(fast, "market_cap", 0) or 0) or None,
                )
                _cache_set(cache_key, q)
                return q

            price = float(info.get("currentPrice") or info.get("regularMarketPrice", 0))
            prev = float(info.get("previousClose") or info.get("regularMarketPreviousClose", price))
            change = price - prev
            change_pct = (change / prev * 100) if prev > 0 else 0

            q = Quote(
                symbol=symbol.upper(),
                price=round(price, 2),
                change=round(change, 2),
                change_pct=round(change_pct, 2),
                volume=int(info.get("volume") or info.get("regularMarketVolume", 0)),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
            )
            _cache_set(cache_key, q)
            return q
        except Exception as e:
            logger.error("Quote fetch failed for %s: %s", symbol, e)
            return None

    def get_financials(self, symbol: str) -> Optional[FinancialMetrics]:
        """Fetch key financial metrics."""
        cache_key = f"financials:{symbol}"
        cached = _cache_get(cache_key, ttl=3600)
        if cached is not None:
            return cached

        self._ensure_yfinance()
        try:
            ticker = self._yf.Ticker(symbol)
            info = ticker.info
            if not info:
                return None

            fm = FinancialMetrics(
                symbol=symbol.upper(),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                forward_pe=info.get("forwardPE"),
                pb_ratio=info.get("priceToBook"),
                ps_ratio=info.get("priceToSalesTrailing12Months"),
                peg_ratio=info.get("pegRatio"),
                ev_to_ebitda=info.get("enterpriseToEbitda"),
                profit_margin=info.get("profitMargins"),
                operating_margin=info.get("operatingMargins"),
                gross_margin=info.get("grossMargins"),
                roe=info.get("returnOnEquity"),
                roa=info.get("returnOnAssets"),
                debt_to_equity=info.get("debtToEquity"),
                current_ratio=info.get("currentRatio"),
                revenue_growth=info.get("revenueGrowth"),
                earnings_growth=info.get("earningsGrowth"),
                dividend_yield=info.get("dividendYield"),
                beta=info.get("beta"),
                fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
                fifty_two_week_low=info.get("fiftyTwoWeekLow"),
                avg_volume=info.get("averageVolume"),
                sector=info.get("sector"),
                industry=info.get("industry"),
            )
            _cache_set(cache_key, fm)
            return fm
        except Exception as e:
            logger.error("Financials fetch failed for %s: %s", symbol, e)
            return None

    def get_insider_trades(self, symbol: str) -> list[InsiderTrade]:
        """Fetch recent insider trades."""
        cache_key = f"insider:{symbol}"
        cached = _cache_get(cache_key, ttl=3600)
        if cached is not None:
            return cached

        self._ensure_yfinance()
        try:
            ticker = self._yf.Ticker(symbol)
            insider_df = ticker.insider_transactions
            if insider_df is None or insider_df.empty:
                return []

            trades = []
            for _, row in insider_df.head(20).iterrows():
                shares = int(row.get("Shares", 0) or 0)
                price_val = float(row.get("Value", 0) or 0)
                per_share = price_val / shares if shares > 0 else 0.0
                trades.append(InsiderTrade(
                    symbol=symbol.upper(),
                    insider_name=str(row.get("Insider", "Unknown")),
                    title=str(row.get("Position", "")),
                    transaction_type=str(row.get("Transaction", "Unknown")),
                    shares=abs(shares),
                    price=round(per_share, 2),
                    value=round(abs(price_val), 2),
                    date=str(row.get("Start Date", "")),
                ))
            _cache_set(cache_key, trades)
            return trades
        except Exception as e:
            logger.error("Insider fetch failed for %s: %s", symbol, e)
            return []

    def get_news(self, symbol: str) -> list[NewsItem]:
        """Fetch recent news for a symbol."""
        cache_key = f"news:{symbol}"
        cached = _cache_get(cache_key, ttl=600)
        if cached is not None:
            return cached

        self._ensure_yfinance()
        try:
            ticker = self._yf.Ticker(symbol)
            news_list = ticker.news or []
            items = []
            for article in news_list[:15]:
                content = article.get("content", {}) if isinstance(article, dict) else {}
                title = content.get("title") or article.get("title", "")
                provider = content.get("provider", {})
                source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)
                url = content.get("canonicalUrl", {}).get("url", "") if isinstance(content.get("canonicalUrl"), dict) else article.get("link", "")
                pub_date = content.get("pubDate", "") or article.get("providerPublishTime", "")
                items.append(NewsItem(
                    title=title,
                    source=source,
                    url=url,
                    published=str(pub_date),
                    symbol=symbol.upper(),
                ))
            _cache_set(cache_key, items)
            return items
        except Exception as e:
            logger.error("News fetch failed for %s: %s", symbol, e)
            return []

    def get_multi_quotes(self, symbols: list[str]) -> dict[str, Optional[Quote]]:
        """Fetch quotes for multiple symbols."""
        result = {}
        for sym in symbols:
            result[sym] = self.get_quote(sym)
        return result

    def get_sector_performance(self, symbols: list[str]) -> dict[str, dict]:
        """Group symbols by sector and compute sector-level metrics."""
        sectors: dict[str, list] = {}
        for sym in symbols:
            fm = self.get_financials(sym)
            if fm and fm.sector:
                sectors.setdefault(fm.sector, []).append(fm)

        result = {}
        for sector, companies in sectors.items():
            pe_ratios = [c.pe_ratio for c in companies if c.pe_ratio is not None]
            margins = [c.profit_margin for c in companies if c.profit_margin is not None]
            result[sector] = {
                "count": len(companies),
                "avg_pe": round(sum(pe_ratios) / len(pe_ratios), 2) if pe_ratios else None,
                "avg_margin": round(sum(margins) / len(margins), 4) if margins else None,
                "symbols": [c.symbol for c in companies],
            }
        return result

    def clear_cache(self) -> int:
        """Clear all cached data. Returns number of entries cleared."""
        count = len(_cache)
        _cache.clear()
        return count
