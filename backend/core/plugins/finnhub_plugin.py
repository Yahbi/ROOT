"""Finnhub market intelligence plugin builder."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.core.plugin_engine import Plugin, PluginTool

logger = logging.getLogger("root.plugins")

_FINNHUB_BASE = "https://finnhub.io/api/v1"


def register_finnhub_plugins(engine, state_store=None) -> None:
    """Register Finnhub market intelligence plugin."""
    api_key = os.getenv("FINNHUB_API_KEY", "")

    if not api_key:
        logger.info("Finnhub Intelligence plugin: SKIPPED (no FINNHUB_API_KEY)")
        return

    # ── Helper ─────────────────────────────────────────────────

    async def _finnhub_get(path: str, params: dict[str, Any] | None = None) -> dict:
        """Make authenticated GET request to Finnhub API."""
        params = params or {}
        params["token"] = api_key
        url = f"{_FINNHUB_BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    return {"error": "Finnhub rate limit exceeded — try again shortly"}
                if resp.status_code == 403:
                    return {"error": "Finnhub API key invalid or insufficient permissions"}
                if resp.status_code >= 400:
                    return {"error": f"Finnhub {resp.status_code}: {resp.text[:300]}"}
                data = resp.json()
                if isinstance(data, dict) and data.get("error"):
                    return {"error": data["error"]}
                return data if isinstance(data, dict) else {"data": data}
        except httpx.TimeoutException:
            return {"error": "Finnhub request timed out"}
        except Exception as e:
            return {"error": f"Finnhub request failed: {str(e)}"}

    # ── Tool 1: Real-time Quote ────────────────────────────────

    async def finnhub_quote(args: dict) -> dict:
        """Get real-time stock quote."""
        symbol = args.get("symbol", "").upper().strip()
        if not symbol:
            return {"error": "symbol is required"}
        data = await _finnhub_get("/quote", {"symbol": symbol})
        if "error" in data:
            return data
        return {
            "symbol": symbol,
            "current_price": data.get("c"),
            "change": data.get("d"),
            "change_percent": data.get("dp"),
            "high": data.get("h"),
            "low": data.get("l"),
            "open": data.get("o"),
            "previous_close": data.get("pc"),
            "timestamp": data.get("t"),
        }

    # ── Tool 2: Company Profile ────────────────────────────────

    async def finnhub_company_profile(args: dict) -> dict:
        """Get company profile."""
        symbol = args.get("symbol", "").upper().strip()
        if not symbol:
            return {"error": "symbol is required"}
        data = await _finnhub_get("/stock/profile2", {"symbol": symbol})
        if "error" in data:
            return data
        return {
            "symbol": symbol,
            "name": data.get("name"),
            "country": data.get("country"),
            "currency": data.get("currency"),
            "exchange": data.get("exchange"),
            "sector": data.get("finnhubIndustry"),
            "ipo_date": data.get("ipo"),
            "market_cap": data.get("marketCapitalization"),
            "shares_outstanding": data.get("shareOutstanding"),
            "logo": data.get("logo"),
            "url": data.get("weburl"),
            "phone": data.get("phone"),
        }

    # ── Tool 3: Key Financial Metrics ──────────────────────────

    async def finnhub_financials(args: dict) -> dict:
        """Get key financial metrics."""
        symbol = args.get("symbol", "").upper().strip()
        if not symbol:
            return {"error": "symbol is required"}
        data = await _finnhub_get("/stock/metric", {"symbol": symbol, "metric": "all"})
        if "error" in data:
            return data
        metric = data.get("metric", {})
        return {
            "symbol": symbol,
            "pe_ratio": metric.get("peNormalizedAnnual"),
            "pe_ttm": metric.get("peTTM"),
            "pb_ratio": metric.get("pbAnnual"),
            "ps_ratio": metric.get("psAnnual"),
            "roe": metric.get("roeTTM"),
            "roa": metric.get("roaTTM"),
            "debt_equity": metric.get("totalDebt/totalEquityAnnual"),
            "current_ratio": metric.get("currentRatioAnnual"),
            "gross_margin": metric.get("grossMarginTTM"),
            "operating_margin": metric.get("operatingMarginTTM"),
            "net_margin": metric.get("netProfitMarginTTM"),
            "dividend_yield": metric.get("dividendYieldIndicatedAnnual"),
            "eps_ttm": metric.get("epsTTM"),
            "revenue_growth_3y": metric.get("revenueGrowth3Y"),
            "eps_growth_3y": metric.get("epsGrowth3Y"),
            "beta": metric.get("beta"),
            "52w_high": metric.get("52WeekHigh"),
            "52w_low": metric.get("52WeekLow"),
            "52w_high_date": metric.get("52WeekHighDate"),
            "52w_low_date": metric.get("52WeekLowDate"),
            "10d_avg_volume": metric.get("10DayAverageTradingVolume"),
        }

    # ── Tool 4: Earnings History ───────────────────────────────

    async def finnhub_earnings(args: dict) -> dict:
        """Get earnings history with surprises."""
        symbol = args.get("symbol", "").upper().strip()
        limit = int(args.get("limit", 4))
        if not symbol:
            return {"error": "symbol is required"}
        data = await _finnhub_get("/stock/earnings", {"symbol": symbol})
        if "error" in data:
            return data
        results = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(results, list):
            return {"symbol": symbol, "earnings": []}
        earnings = []
        for e in results[:limit]:
            earnings.append({
                "period": e.get("period"),
                "actual": e.get("actual"),
                "estimate": e.get("estimate"),
                "surprise": e.get("surprise"),
                "surprise_percent": e.get("surprisePercent"),
            })
        return {"symbol": symbol, "earnings": earnings}

    # ── Tool 5: Analyst Recommendations ────────────────────────

    async def finnhub_recommendations(args: dict) -> dict:
        """Get analyst recommendation trends."""
        symbol = args.get("symbol", "").upper().strip()
        if not symbol:
            return {"error": "symbol is required"}
        data = await _finnhub_get("/stock/recommendation", {"symbol": symbol})
        if "error" in data:
            return data
        results = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(results, list):
            return {"symbol": symbol, "recommendations": []}
        recs = []
        for r in results[:6]:
            recs.append({
                "period": r.get("period"),
                "strong_buy": r.get("strongBuy"),
                "buy": r.get("buy"),
                "hold": r.get("hold"),
                "sell": r.get("sell"),
                "strong_sell": r.get("strongSell"),
            })
        return {"symbol": symbol, "recommendations": recs}

    # ── Tool 6: News Sentiment ─────────────────────────────────

    async def finnhub_news_sentiment(args: dict) -> dict:
        """Get company news with sentiment scores."""
        symbol = args.get("symbol", "").upper().strip()
        if not symbol:
            return {"error": "symbol is required"}
        # Get company news (last 7 days)
        now = datetime.now(timezone.utc)
        to_date = now.strftime("%Y-%m-%d")
        from datetime import timedelta
        from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        data = await _finnhub_get("/company-news", {
            "symbol": symbol,
            "from": from_date,
            "to": to_date,
        })
        if isinstance(data, dict) and "error" in data:
            return data
        results = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(results, list):
            return {"symbol": symbol, "news": []}
        news = []
        for article in results[:10]:
            news.append({
                "headline": article.get("headline"),
                "source": article.get("source"),
                "url": article.get("url"),
                "summary": article.get("summary", "")[:200],
                "datetime": article.get("datetime"),
                "category": article.get("category"),
            })
        # Also fetch sentiment aggregate
        sentiment_data = await _finnhub_get("/news-sentiment", {"symbol": symbol})
        sentiment = {}
        if isinstance(sentiment_data, dict) and "error" not in sentiment_data:
            s = sentiment_data.get("sentiment", {})
            sentiment = {
                "articles_in_last_week": sentiment_data.get("buzz", {}).get("articlesInLastWeek"),
                "weekly_average": sentiment_data.get("buzz", {}).get("weeklyAverage"),
                "buzz_score": sentiment_data.get("buzz", {}).get("buzz"),
                "bullish_percent": s.get("bullishPercent"),
                "bearish_percent": s.get("bearishPercent"),
                "sector_avg_bullish": sentiment_data.get("sectorAverageBullishPercent"),
                "company_news_score": sentiment_data.get("companyNewsScore"),
            }
        return {"symbol": symbol, "news": news, "sentiment": sentiment}

    # ── Tool 7: Technical Indicators ───────────────────────────

    async def finnhub_technical_indicators(args: dict) -> dict:
        """Get technical indicators (RSI, MACD, SMA, EMA)."""
        symbol = args.get("symbol", "").upper().strip()
        resolution = args.get("resolution", "D")  # D=daily, W=weekly, M=monthly
        if not symbol:
            return {"error": "symbol is required"}
        import time
        now_ts = int(time.time())
        from_ts = now_ts - (365 * 24 * 3600)  # 1 year back

        indicators = {}
        # Fetch multiple indicators in sequence (Finnhub rate limits)
        indicator_configs = [
            ("rsi", {"timeperiod": 14}),
            ("macd", {"fastperiod": 12, "slowperiod": 26, "signalperiod": 9}),
            ("sma", {"timeperiod": 50}),
            ("ema", {"timeperiod": 20}),
        ]
        for ind_name, ind_params in indicator_configs:
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "from": from_ts,
                "to": now_ts,
                "indicator": ind_name,
                **ind_params,
            }
            data = await _finnhub_get("/indicator", params)
            if isinstance(data, dict) and "error" not in data:
                # Extract last few values for each indicator
                if ind_name == "macd":
                    macd_vals = data.get("macd", [])
                    signal_vals = data.get("macdSignal", [])
                    hist_vals = data.get("macdHist", [])
                    indicators["macd"] = {
                        "macd": macd_vals[-1] if macd_vals else None,
                        "signal": signal_vals[-1] if signal_vals else None,
                        "histogram": hist_vals[-1] if hist_vals else None,
                    }
                elif ind_name == "rsi":
                    rsi_vals = data.get("rsi", [])
                    indicators["rsi"] = rsi_vals[-1] if rsi_vals else None
                elif ind_name in ("sma", "ema"):
                    vals = data.get(ind_name, [])
                    indicators[f"{ind_name}_{ind_params['timeperiod']}"] = (
                        vals[-1] if vals else None
                    )
            else:
                indicators[ind_name] = data.get("error", "unavailable") if isinstance(data, dict) else "unavailable"

        return {"symbol": symbol, "resolution": resolution, "indicators": indicators}

    # ── Tool 8: Earnings Calendar ──────────────────────────────

    async def finnhub_earnings_calendar(args: dict) -> dict:
        """Get upcoming earnings dates."""
        symbol = args.get("symbol", "").upper().strip()
        now = datetime.now(timezone.utc)
        from_date = now.strftime("%Y-%m-%d")
        from datetime import timedelta
        to_date = (now + timedelta(days=90)).strftime("%Y-%m-%d")
        params = {"from": from_date, "to": to_date}
        if symbol:
            params["symbol"] = symbol
        data = await _finnhub_get("/calendar/earnings", params)
        if "error" in data:
            return data
        results = data.get("earningsCalendar", [])
        calendar = []
        for e in results[:20]:
            calendar.append({
                "symbol": e.get("symbol"),
                "date": e.get("date"),
                "hour": e.get("hour"),  # bmo=before, amc=after, dmh=during
                "eps_estimate": e.get("epsEstimate"),
                "eps_actual": e.get("epsActual"),
                "revenue_estimate": e.get("revenueEstimate"),
                "revenue_actual": e.get("revenueActual"),
                "quarter": e.get("quarter"),
                "year": e.get("year"),
            })
        return {"symbol": symbol or "all", "upcoming_earnings": calendar}

    # ── Tool 9: Analyst Price Targets ──────────────────────────

    async def finnhub_price_target(args: dict) -> dict:
        """Get analyst price targets."""
        symbol = args.get("symbol", "").upper().strip()
        if not symbol:
            return {"error": "symbol is required"}
        data = await _finnhub_get("/stock/price-target", {"symbol": symbol})
        if "error" in data:
            return data
        return {
            "symbol": symbol,
            "target_high": data.get("targetHigh"),
            "target_low": data.get("targetLow"),
            "target_mean": data.get("targetMean"),
            "target_median": data.get("targetMedian"),
            "last_updated": data.get("lastUpdated"),
        }

    # ── Tool 10: Insider Transactions ──────────────────────────

    async def finnhub_insider_trades(args: dict) -> dict:
        """Get recent insider transactions."""
        symbol = args.get("symbol", "").upper().strip()
        if not symbol:
            return {"error": "symbol is required"}
        data = await _finnhub_get("/stock/insider-transactions", {"symbol": symbol})
        if "error" in data:
            return data
        results = data.get("data", [])
        trades = []
        for t in results[:15]:
            trades.append({
                "name": t.get("name"),
                "share": t.get("share"),
                "change": t.get("change"),
                "transaction_date": t.get("transactionDate"),
                "transaction_type": t.get("transactionCode"),
                "transaction_price": t.get("transactionPrice"),
                "filing_date": t.get("filingDate"),
            })
        return {"symbol": symbol, "insider_trades": trades}

    # ── Register all tools as a single plugin ──────────────────

    engine.register(Plugin(
        id="finnhub",
        name="Finnhub Intelligence",
        description="Finnhub market data: quotes, fundamentals, earnings, news sentiment, technicals, insider trades",
        version="1.0.0",
        category="financial",
        tags=["finnhub", "market", "stocks", "fundamentals", "earnings", "sentiment", "financial"],
        tools=[
            PluginTool(
                name="finnhub_quote",
                description="Get real-time stock quote (price, change, high, low, volume)",
                handler=finnhub_quote,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL, MSFT)"},
                    },
                    "required": ["symbol"],
                },
            ),
            PluginTool(
                name="finnhub_company_profile",
                description="Get company profile (name, sector, market cap, exchange, IPO date)",
                handler=finnhub_company_profile,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["symbol"],
                },
            ),
            PluginTool(
                name="finnhub_financials",
                description="Get key financial metrics (P/E, ROE, debt/equity, margins, EPS, beta)",
                handler=finnhub_financials,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["symbol"],
                },
            ),
            PluginTool(
                name="finnhub_earnings",
                description="Get earnings history with actual vs estimate surprises",
                handler=finnhub_earnings,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                        "limit": {"type": "integer", "description": "Number of quarters (default 4)", "default": 4},
                    },
                    "required": ["symbol"],
                },
            ),
            PluginTool(
                name="finnhub_recommendations",
                description="Get analyst recommendation trends (strong buy/buy/hold/sell/strong sell counts)",
                handler=finnhub_recommendations,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["symbol"],
                },
            ),
            PluginTool(
                name="finnhub_news_sentiment",
                description="Get company news with sentiment scores (bullish/bearish percent, buzz)",
                handler=finnhub_news_sentiment,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["symbol"],
                },
            ),
            PluginTool(
                name="finnhub_technical_indicators",
                description="Get technical indicators (RSI, MACD, SMA, EMA) from Finnhub",
                handler=finnhub_technical_indicators,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                        "resolution": {
                            "type": "string",
                            "description": "Candle resolution: 1, 5, 15, 30, 60, D, W, M (default D)",
                            "default": "D",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            PluginTool(
                name="finnhub_earnings_calendar",
                description="Get upcoming earnings dates (next 90 days). Optionally filter by symbol.",
                handler=finnhub_earnings_calendar,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol (optional, omit for broad calendar)"},
                    },
                },
            ),
            PluginTool(
                name="finnhub_price_target",
                description="Get analyst price targets (high, low, mean, median)",
                handler=finnhub_price_target,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["symbol"],
                },
            ),
            PluginTool(
                name="finnhub_insider_trades",
                description="Get recent insider transactions (buys, sells, grants)",
                handler=finnhub_insider_trades,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["symbol"],
                },
            ),
        ],
    ))

    logger.info("Finnhub Intelligence plugin: registered (10 tools)")
