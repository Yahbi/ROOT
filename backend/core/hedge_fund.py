"""AI Hedge Fund Engine — autonomous investment management (scan → analyze → decide → execute → monitor → learn)."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import ROOT_DIR, HEDGE_FUND_MAX_POSITION_PCT, HEDGE_FUND_MAX_PORTFOLIO_RISK_PCT, HEDGE_FUND_MAX_DAILY_LOSS_PCT

logger = logging.getLogger("root.hedge_fund")

HEDGE_FUND_DB = ROOT_DIR / "data" / "hedge_fund.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data models ──────────────────────────────────────────────

@dataclass(frozen=True)
class Signal:
    """Immutable trading signal from any source."""
    id: str
    symbol: str
    direction: str  # "long" | "short" | "hold"
    confidence: float  # 0.0 - 1.0
    source: str  # "miro", "swarm", "researcher", "proactive"
    reasoning: str
    timeframe: str = "swing"  # "scalp", "day", "swing", "position"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class Position:
    """Immutable tracked position."""
    id: str
    symbol: str
    direction: str
    quantity: float
    entry_price: float
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str = "open"  # "open", "closed", "stopped_out"
    signal_id: Optional[str] = None
    opened_at: str = field(default_factory=_now_iso)
    closed_at: Optional[str] = None


@dataclass(frozen=True)
class StrategyPerformance:
    """Immutable strategy track record."""
    strategy_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_return_pct: float
    total_pnl: float
    sharpe_ratio: float
    max_drawdown_pct: float
    weight: float = 1.0  # Adaptive weight based on performance


# ── Risk Controls ────────────────────────────────────────────

RISK_LIMITS = {
    "max_position_pct": HEDGE_FUND_MAX_POSITION_PCT,
    "max_portfolio_risk_pct": HEDGE_FUND_MAX_PORTFOLIO_RISK_PCT,
    "max_daily_loss_pct": HEDGE_FUND_MAX_DAILY_LOSS_PCT,
    "max_open_positions": 10,       # Max 10 concurrent positions
    "min_signal_confidence": 0.65,  # Only trade signals above 65% confidence
    "required_confirmations": 2,    # Need 2+ sources to agree
    "cooldown_after_loss_min": 30,  # Wait 30min after a losing trade
}


class HedgeFundEngine:

    def __init__(
        self,
        memory=None,
        collab=None,
        bus=None,
        approval=None,
        llm=None,
        learning=None,
        plugins=None,
    ) -> None:
        self._memory = memory
        self._collab = collab
        self._bus = bus
        self._approval = approval
        self._llm = llm
        self._learning = learning
        self._plugins = plugins
        self._interest_engine = None  # Set via main.py
        self._notification_engine = None  # Set via main.py
        self._sandbox_gate = None  # Set via main.py
        self._market_data = None  # Set via main.py — MarketDataService
        self._trading_consensus = None  # Set via main.py — TradingConsensus
        self._trading_autonomy = None  # Set via main.py — TradingAutonomy
        self._investor_panel = None  # Set via main.py — InvestorPanel
        self._conn: Optional[sqlite3.Connection] = None
        self._running = False
        self._daily_pnl = 0.0
        self._signals: list[Signal] = []

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        """Initialize the hedge fund database."""
        HEDGE_FUND_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(HEDGE_FUND_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        self._migrate_tables()
        self._load_daily_pnl()
        logger.info("HedgeFundEngine started (db=%s)", HEDGE_FUND_DB)

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("HedgeFundEngine not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,
                reasoning TEXT,
                timeframe TEXT DEFAULT 'swing',
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                acted_on INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                pnl REAL DEFAULT 0,
                pnl_pct REAL DEFAULT 0,
                stop_loss REAL,
                take_profit REAL,
                status TEXT DEFAULT 'open',
                signal_id TEXT,
                strategy TEXT DEFAULT 'general',
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            );

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_value REAL NOT NULL,
                cash REAL NOT NULL,
                positions_value REAL NOT NULL,
                daily_pnl REAL DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                open_positions INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS strategy_weights (
                strategy TEXT PRIMARY KEY,
                weight REAL NOT NULL DEFAULT 1.0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
            CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        """)

    def _migrate_tables(self) -> None:
        try:
            self.conn.execute("ALTER TABLE trades ADD COLUMN current_price REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            self.conn.execute("ALTER TABLE trades ADD COLUMN pnl REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            self.conn.execute("ALTER TABLE trades ADD COLUMN pnl_pct REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

    def _load_daily_pnl(self) -> None:
        row = self.conn.execute(
            "SELECT daily_pnl, created_at FROM portfolio_snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row and row["created_at"][:10] == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            self._daily_pnl = row["daily_pnl"]
        else:
            self._daily_pnl = 0.0

    def _update_trade_price(self, trade_id: str, current_price: float, pnl: float, pnl_pct: float) -> None:
        self.conn.execute(
            "UPDATE trades SET current_price = ?, pnl = ?, pnl_pct = ? WHERE id = ?",
            (current_price, pnl, pnl_pct, trade_id),
        )
        try:
            self.conn.commit()
        except Exception as exc:
            logger.error("Failed to commit _update_trade_price (%s): %s", trade_id, exc)
            raise

    # ── Signal Generation ──────────────────────────────────────

    @staticmethod
    def _fetch_live_prices() -> str:
        """Fetch live prices for major symbols via Yahoo Finance (no API key)."""
        import urllib.request, csv, io
        symbols = [
            "SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN",
            "GOOGL", "META", "AMD", "SMCI", "SOXL", "SOXS",
            "BTC-USD", "ETH-USD", "SOL-USD",
        ]
        lines = []
        for sym in symbols:
            try:
                url = (
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                    f"?interval=1d&range=5d"
                )
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = __import__("json").load(resp)
                result = data.get("chart", {}).get("result", [])
                if not result:
                    continue
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("chartPreviousClose", price)
                chg = ((price - prev) / prev * 100) if prev else 0
                lines.append(f"{sym}: ${price:.2f} ({chg:+.1f}% today)")
            except Exception as exc:
                logger.warning("Failed to fetch price for %s: %s", sym, exc)
        return "\n".join(lines) if lines else "Price data unavailable"

    @staticmethod
    def _fetch_news_headlines() -> str:
        """Fetch recent financial news headlines via free RSS feeds (no API key)."""
        import urllib.request
        import xml.etree.ElementTree as ET

        feeds = [
            # Yahoo Finance top stories
            ("https://finance.yahoo.com/news/rssindex", "Yahoo Finance"),
            # Google News — Business
            ("https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en", "Google News"),
            # MarketWatch top stories
            ("https://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch"),
            # CNBC economy
            ("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "CNBC"),
        ]

        headlines: list[str] = []
        for feed_url, source in feeds:
            try:
                req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    tree = ET.parse(resp)
                root_el = tree.getroot()
                # RSS 2.0: channel/item/title  |  Atom: entry/title
                items = root_el.findall(".//item") or root_el.findall(".//{http://www.w3.org/2005/Atom}entry")
                for item in items[:8]:  # Top 8 per feed
                    title_el = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
                    if title_el is not None and title_el.text:
                        headlines.append(f"[{source}] {title_el.text.strip()}")
            except Exception as exc:
                logger.warning("Failed to fetch news feed from %s: %s", source, exc)

        return "\n".join(headlines[:30]) if headlines else "No news available"

    async def scan_markets(self) -> list[Signal]:
        signals: list[Signal] = []

        if not self._collab or not self._llm:
            return signals

        # Fetch live prices + news headlines in parallel
        import asyncio as _aio
        price_task = _aio.to_thread(self._fetch_live_prices)
        news_task = _aio.to_thread(self._fetch_news_headlines)
        live_prices, news_headlines = await _aio.gather(price_task, news_task)

        if self._notification_engine:
            await self._notification_engine.audit_external_action(
                action="Market Data Fetch",
                target="Yahoo Finance + RSS Feeds",
                source="hedge_fund",
                level="low",
                details="Fetched live prices for watchlist symbols + financial news headlines",
            )

        price_context = f"Current live market prices:\n{live_prices}\n\n"
        news_context = f"Latest financial news headlines:\n{news_headlines}\n\n" if news_headlines != "No news available" else ""
        full_context = price_context + news_context

        subtasks = [
            {"agent_id": "miro", "task": (
                full_context +
                "Based on these LIVE prices and news, run a market prediction scan. "
                "Consider BOTH long AND short opportunities — actively look for overextended "
                "rallies to short. For each symbol: direction (long/short), confidence (0-100%), "
                "1-sentence reasoning. Include at least 2 short ideas if any symbol looks "
                "overbought, overvalued, or faces negative news catalysts.")},
            {"agent_id": "swarm", "task": (
                full_context +
                "Based on these LIVE prices and news, identify the best trading setups right now "
                "(momentum, mean reversion, breakout, AND short setups). Include both long AND "
                "short ideas. For each: symbol, direction, entry price, stop loss, target price, "
                "confidence %. Specifically look for short opportunities in overbought tech stocks "
                "or indices near resistance. Be aggressive — we want actionable trades.")},
            {"agent_id": "researcher", "task": (
                full_context +
                "Analyze the news headlines and price action together. For each symbol with "
                "significant news: what's the catalyst, is it priced in or not, direction for "
                "next 1-5 days (long or short), confidence. Also identify any macro risks "
                "(Fed, geopolitical, earnings) that suggest broad market shorts (SPY, QQQ). "
                "Be explicit about short opportunities — we are looking for both sides.")},
        ]

        try:
            # Use orchestrator directly — each agent gets a different task
            from backend.core.orchestrator import Orchestrator
            orch = getattr(self._collab, "_orchestrator", None)
            if orch:
                orch_result = await orch.execute_parallel(subtasks)
                for task in orch_result.tasks:
                    if task.result:
                        parsed = await self._parse_signals_llm(task.result, task.agent_id)
                        signals.extend(parsed)
            else:
                # Fallback: delegate sequentially
                for st in subtasks:
                    wf = await self._collab.delegate(
                        from_agent="hedge_fund",
                        to_agent=st["agent_id"],
                        task=st["task"],
                    )
                    if wf.final_result:
                        parsed = await self._parse_signals_llm(wf.final_result, st["agent_id"])
                        signals.extend(parsed)
        except Exception as e:
            logger.error("Market scan failed: %s", e)

        # Store signals
        for sig in signals:
            self._store_signal(sig)

        self._signals = signals
        logger.info("Market scan: %d signals generated", len(signals))

        # Publish to bus
        if self._bus:
            msg = self._bus.create_message(
                topic="system.hedge_fund",
                sender="hedge_fund",
                payload={
                    "type": "scan_complete",
                    "signal_count": len(signals),
                    "symbols": list(set(s.symbol for s in signals)),
                },
            )
            await self._bus.publish(msg)

        return signals

    async def _parse_signals_llm(self, text: str, source: str) -> list[Signal]:
        """LLM-based signal extraction — returns structured signals from free text."""
        if not self._llm:
            return self._parse_signals_heuristic(text, source)

        import json as _json

        prompt = (
            "Extract trading signals from this market analysis. "
            "Return a JSON array of objects with keys: symbol, direction (long/short), "
            "confidence (0.0-1.0), reasoning (1 sentence). "
            "Only include actionable signals with clear direction. "
            "If no clear signals, return []. Respond ONLY with JSON.\n\n"
            f"Analysis from {source}:\n{text[:2000]}"
        )
        try:
            response = await self._llm.complete(
                system="You extract trading signals from text. Return only valid JSON arrays.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                max_tokens=500,
            )
            # Strip markdown fences if present
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            parsed = _json.loads(raw)
            if not isinstance(parsed, list):
                return self._parse_signals_heuristic(text, source)

            signals: list[Signal] = []
            for item in parsed[:5]:  # Max 5 signals per parse
                symbol = str(item.get("symbol", "")).upper().replace("-USD", "")
                direction = str(item.get("direction", "")).lower()
                if symbol and direction in ("long", "short"):
                    signals.append(Signal(
                        id=f"sig_{uuid.uuid4().hex[:8]}",
                        symbol=symbol,
                        direction=direction,
                        confidence=min(0.95, max(0.3, float(item.get("confidence", 0.6)))),
                        source=source,
                        reasoning=str(item.get("reasoning", ""))[:300],
                    ))
            return signals if signals else self._parse_signals_heuristic(text, source)
        except Exception as exc:
            logger.warning("LLM signal parsing failed, using heuristic: %s", exc)
            return self._parse_signals_heuristic(text, source)

    def _parse_signals_heuristic(self, text: str, source: str) -> list[Signal]:
        signals: list[Signal] = []
        symbols = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "TSLA", "MSFT", "AMZN",
                    "GOOGL", "NVDA", "META", "AMD", "SMCI", "SOXL", "SOXS",
                    "TQQQ", "SQQQ", "SPXU", "UPRO",
                    "BTC", "ETH", "SOL", "BTC-USD", "ETH-USD", "SOL-USD"]
        text_upper = text.upper()
        long_kw = ("buy", "long", "bullish", "upside", "rally", "breakout", "support")
        short_kw = ("sell", "short", "bearish", "downside", "drop", "breakdown", "resistance")
        for symbol in symbols:
            if symbol not in text_upper:
                continue
            idx = text_upper.index(symbol)
            ctx = text[max(0, idx - 100):idx + 200].lower()
            ls = sum(1 for w in long_kw if w in ctx)
            ss = sum(1 for w in short_kw if w in ctx)
            if ls == ss:
                continue
            direction = "long" if ls > ss else "short"
            signals.append(Signal(
                id=f"sig_{uuid.uuid4().hex[:8]}", symbol=symbol.replace("-USD", ""),
                direction=direction, confidence=min(0.9, 0.5 + max(ls, ss) * 0.1),
                source=source, reasoning=ctx.strip()[:300],
            ))
        return signals

    def _store_signal(self, signal: Signal) -> None:
        """Persist signal to database."""
        self.conn.execute(
            """INSERT OR IGNORE INTO signals
               (id, symbol, direction, confidence, source, reasoning,
                timeframe, entry_price, stop_loss, take_profit, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.id, signal.symbol, signal.direction, signal.confidence,
                signal.source, signal.reasoning, signal.timeframe,
                signal.entry_price, signal.stop_loss, signal.take_profit,
                signal.created_at,
            ),
        )
        try:
            self.conn.commit()
        except Exception as exc:
            logger.error("Failed to commit _store_signal (%s %s): %s", signal.symbol, signal.id, exc)
            raise

    # ── Risk Check ─────────────────────────────────────────────

    def set_interest_engine(self, engine) -> None:
        self._interest_engine = engine

    def check_risk(self, signal: Signal, portfolio_value: float) -> tuple[bool, str]:
        """Check if a signal passes risk controls. Returns (ok, reason)."""
        # Interest alignment check — block strongly misaligned trades,
        # penalize misaligned, boost aligned
        if self._interest_engine:
            allowed, reason = self._interest_engine.gate(
                subject=f"Trade {signal.direction} {signal.symbol}",
                context=signal.reasoning,
            )
            if not allowed:
                return False, f"Interest gate: {reason}"

        if signal.confidence < RISK_LIMITS["min_signal_confidence"]:
            return False, f"Confidence {signal.confidence:.0%} < minimum {RISK_LIMITS['min_signal_confidence']:.0%}"

        # Check open positions limit
        open_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM trades WHERE status = 'open'"
        ).fetchone()["c"]
        if open_count >= RISK_LIMITS["max_open_positions"]:
            return False, f"Max open positions reached ({open_count})"

        # Check daily loss limit
        if self._daily_pnl < -(portfolio_value * RISK_LIMITS["max_daily_loss_pct"]):
            return False, f"Daily loss limit hit (${self._daily_pnl:,.2f})"

        # Check for existing position in same symbol
        existing = self.conn.execute(
            "SELECT COUNT(*) as c FROM trades WHERE symbol = ? AND status = 'open'",
            (signal.symbol,),
        ).fetchone()["c"]
        if existing > 0:
            return False, f"Already have open position in {signal.symbol}"

        # Check for signal confirmation (multiple sources agree)
        confirmations = sum(
            1 for s in self._signals
            if s.symbol == signal.symbol
            and s.direction == signal.direction
            and s.id != signal.id
        )
        if confirmations < RISK_LIMITS["required_confirmations"] - 1:
            return False, f"Need {RISK_LIMITS['required_confirmations']} confirmations, have {confirmations + 1}"

        return True, "Risk check passed"

    # ── Trade Execution ────────────────────────────────────────

    async def execute_signal(self, signal: Signal, portfolio_value: float = 100000) -> Optional[dict]:
        ok, reason = self.check_risk(signal, portfolio_value)
        if not ok:
            logger.info("Signal %s blocked: %s", signal.id, reason)
            return {"status": "blocked", "reason": reason}

        # ── Sandbox gate check ──────────────────────────────────
        if self._sandbox_gate is not None:
            decision = self._sandbox_gate.check(
                system_id="trading",
                action=f"execute_trade:{signal.symbol}",
                description=f"{signal.direction.upper()} {signal.symbol} @ {signal.confidence:.0%} — {signal.reasoning[:100]}",
                context={"symbol": signal.symbol, "direction": signal.direction, "confidence": signal.confidence},
                agent_id="hedge_fund",
                risk_level="critical",
            )
            if not decision.was_executed:
                logger.info("Trade sandboxed: %s %s (signal %s)", signal.direction, signal.symbol, signal.id)
                self._store_signal(signal)
                return {
                    "status": "sandboxed",
                    "signal_id": signal.id,
                    "symbol": signal.symbol,
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "message": "Trade simulated in sandbox mode — not sent to Alpaca",
                }

        if self._approval:
            approval = await self._approval.request_approval(
                agent_id="hedge_fund",
                action="execute_trade",
                description=f"{signal.direction.upper()} {signal.symbol} @ {signal.confidence:.0%} confidence — {signal.reasoning[:100]}",
                context={"symbol": signal.symbol, "direction": signal.direction, "involves_money": True},
                reason=f"Signal detected: {signal.direction} {signal.symbol} with {signal.confidence:.0%} confidence",
                benefit=f"Potential profit from {signal.direction} position on {signal.symbol}",
                risk_analysis=f"Position capped at {RISK_LIMITS['max_position_pct']:.0%} portfolio. Daily loss limit: {RISK_LIMITS['max_daily_loss_pct']:.0%}. Signal confidence: {signal.confidence:.0%}",
            )
            if hasattr(approval, 'status'):
                if approval.status.value == "rejected":
                    return {"status": "rejected", "reason": "Yohan rejected the trade"}
                if approval.status.value == "pending":
                    return {
                        "status": "pending_approval",
                        "approval_id": approval.id,
                        "signal_id": signal.id,
                        "symbol": signal.symbol,
                        "direction": signal.direction,
                        "message": "Trade awaiting Yohan's approval — will NOT execute until approved",
                    }

        position_value = portfolio_value * RISK_LIMITS["max_position_pct"]
        entry_price = signal.entry_price or 0.0
        if self._plugins and not entry_price:
            try:
                quote = await self._plugins.invoke("alpaca_market_data", {"symbols": signal.symbol})
                if quote.success and isinstance(quote.output, dict):
                    quotes = quote.output.get("quotes", {})
                    sym_quote = quotes.get(signal.symbol, {})
                    ask = sym_quote.get("ask", 0) or 0
                    bid = sym_quote.get("bid", 0) or 0
                    entry_price = (ask + bid) / 2 if (ask and bid) else ask or bid
            except Exception as price_err:
                logger.warning("Price fetch failed for %s: %s", signal.symbol, price_err)

        qty = max(1, int(position_value / entry_price)) if entry_price > 0 else 1

        # Notify BEFORE trade execution
        if self._notification_engine:
            await self._notification_engine.audit_external_action(
                action=f"TRADE: {signal.direction.upper()} {signal.symbol}",
                target="Alpaca Paper Trading API",
                source="hedge_fund",
                level="critical",
                details=f"Qty: {qty}, Entry: ${entry_price:.2f}, Confidence: {signal.confidence:.0%}\nReasoning: {signal.reasoning[:200]}",
            )

        if self._plugins:
            try:
                result = await self._plugins.invoke("alpaca_place_order", {
                    "symbol": signal.symbol,
                    "qty": qty,
                    "side": "buy" if signal.direction == "long" else "sell",
                    "type": "market",
                    "time_in_force": "day",
                })

                if result.success:
                    filled_price = entry_price
                    if isinstance(result.output, dict):
                        filled_price = float(result.output.get("filled_avg_price", 0) or 0) or entry_price

                    trade_id = f"trade_{uuid.uuid4().hex[:8]}"
                    self.conn.execute(
                        """INSERT INTO trades
                           (id, symbol, direction, quantity, entry_price, stop_loss,
                            take_profit, status, signal_id, strategy, opened_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, 'ai_hedge_fund', ?)""",
                        (
                            trade_id, signal.symbol, signal.direction, qty,
                            filled_price, signal.stop_loss,
                            signal.take_profit, signal.id, _now_iso(),
                        ),
                    )
                    self.conn.execute(
                        "UPDATE signals SET acted_on = 1 WHERE id = ?",
                        (signal.id,),
                    )
                    try:
                        self.conn.commit()
                    except Exception as exc:
                        logger.error("Failed to commit execute_signal (%s): %s", signal.symbol, exc)
                        raise
                    if self._memory:
                        from backend.models.memory import MemoryEntry, MemoryType
                        self._memory.store(MemoryEntry(
                            content=f"Hedge fund trade: {signal.direction} {signal.symbol} "
                                    f"(confidence: {signal.confidence:.0%}, source: {signal.source})",
                            memory_type=MemoryType.OBSERVATION,
                            tags=["hedge_fund", "trade", signal.symbol, signal.direction],
                            source="hedge_fund",
                            confidence=0.9,
                        ))

                    logger.info("Trade executed: %s %s x%d @ $%.2f (signal: %s)",
                                signal.direction, signal.symbol, qty, filled_price, signal.id)
                    return {"status": "executed", "trade_id": trade_id, "qty": qty,
                            "entry_price": filled_price, "result": result.output}
                else:
                    return {"status": "error", "error": result.error}
            except Exception as e:
                logger.error("Trade execution failed: %s", e)
                return {"status": "error", "error": str(e)}

        return {"status": "no_plugin", "reason": "Alpaca plugin not available"}

    # ── Portfolio Monitoring ───────────────────────────────────

    async def get_portfolio(self) -> dict[str, Any]:
        portfolio: dict[str, Any] = {
            "total_value": 0,
            "cash": 0,
            "positions": [],
            "open_trades": 0,
            "daily_pnl": self._daily_pnl,
        }

        if self._plugins:
            try:
                account = await self._plugins.invoke("alpaca_account", {})
                if account.success and isinstance(account.output, dict):
                    portfolio["total_value"] = float(account.output.get("portfolio_value", 0))
                    portfolio["cash"] = float(account.output.get("cash", 0))

                positions = await self._plugins.invoke("alpaca_positions", {})
                if positions.success and isinstance(positions.output, dict):
                    pos_list = positions.output.get("positions", [])
                    portfolio["positions"] = pos_list
                    portfolio["open_trades"] = len(pos_list)
            except Exception as e:
                logger.error("Portfolio fetch failed: %s", e)

        # Add local trade history
        local_trades = self.conn.execute(
            "SELECT * FROM trades WHERE status = 'open' ORDER BY opened_at DESC"
        ).fetchall()
        portfolio["local_open_trades"] = len(local_trades)

        return portfolio

    async def snapshot_portfolio(self) -> None:
        portfolio = await self.get_portfolio()
        self.conn.execute(
            """INSERT INTO portfolio_snapshots
               (total_value, cash, positions_value, daily_pnl, open_positions, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                portfolio.get("total_value", 0),
                portfolio.get("cash", 0),
                portfolio.get("total_value", 0) - portfolio.get("cash", 0),
                self._daily_pnl,
                portfolio.get("open_trades", 0),
                _now_iso(),
            ),
        )
        try:
            self.conn.commit()
        except Exception as exc:
            logger.error("Failed to commit snapshot_portfolio: %s", exc)
            raise

    # ── Strategy Learning ──────────────────────────────────────

    def record_trade_outcome(self, trade_id: str, exit_price: float) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()
        if not row:
            return None

        entry = row["entry_price"]
        pnl = (exit_price - entry) if row["direction"] == "long" else (entry - exit_price)
        pnl_pct = (pnl / entry * 100) if entry > 0 else 0

        self.conn.execute(
            """UPDATE trades SET exit_price = ?, pnl = ?, pnl_pct = ?,
               status = 'closed', closed_at = ? WHERE id = ?""",
            (exit_price, pnl * row["quantity"], pnl_pct, _now_iso(), trade_id),
        )

        # Update strategy weight
        strategy = row["strategy"] or "general"
        is_win = pnl > 0
        existing = self.conn.execute(
            "SELECT * FROM strategy_weights WHERE strategy = ?", (strategy,)
        ).fetchone()

        if existing:
            wins = existing["wins"] + (1 if is_win else 0)
            losses = existing["losses"] + (0 if is_win else 1)
            total_pnl = existing["total_pnl"] + pnl
            weight = (wins + 1) / (wins + losses + 2)  # Bayesian
            self.conn.execute(
                """UPDATE strategy_weights SET weight = ?, wins = ?, losses = ?,
                   total_pnl = ?, updated_at = ? WHERE strategy = ?""",
                (weight, wins, losses, total_pnl, _now_iso(), strategy),
            )
        else:
            self.conn.execute(
                """INSERT INTO strategy_weights (strategy, weight, wins, losses, total_pnl, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (strategy, 0.67 if is_win else 0.33, 1 if is_win else 0,
                 0 if is_win else 1, pnl, _now_iso()),
            )

        try:
            self.conn.commit()
        except Exception as exc:
            logger.error("Failed to commit record_trade_outcome (%s): %s", trade_id, exc)
            raise
        self._daily_pnl += pnl

        # Learn from outcome
        if self._learning:
            self._learning.record_agent_outcome(
                agent_id="hedge_fund",
                task_description=f"Trade {row['symbol']} {row['direction']}",
                status="success" if is_win else "failed",
                result_quality=min(1.0, 0.5 + pnl_pct / 20),
                task_category="trading",
            )

        return {
            "trade_id": trade_id,
            "symbol": row["symbol"],
            "direction": row["direction"],
            "pnl": round(pnl * row["quantity"], 2),
            "pnl_pct": round(pnl_pct, 2),
            "status": "win" if is_win else "loss",
        }

    # ── Position Monitoring ─────────────────────────────────────

    async def monitor_positions(self) -> dict[str, int]:
        """Check all open positions for stop-loss / take-profit hits."""
        trades = self.conn.execute("SELECT * FROM trades WHERE status = 'open'").fetchall()
        summary = {"checked": 0, "stopped_out": 0, "take_profit_hit": 0, "still_open": 0}
        if not trades:
            return summary

        for trade in trades:
            summary["checked"] += 1
            current_price = 0.0
            if self._plugins:
                try:
                    quote = await self._plugins.invoke("alpaca_market_data", {"symbols": trade["symbol"]})
                    if quote.success and isinstance(quote.output, dict):
                        sq = quote.output.get("quotes", {}).get(trade["symbol"], {})
                        ask = sq.get("ask", 0) or 0
                        bid = sq.get("bid", 0) or 0
                        current_price = (ask + bid) / 2 if (ask and bid) else ask or bid
                except Exception as e:
                    logger.warning("Price fetch failed for %s: %s", trade["symbol"], e)

            if not current_price:
                summary["still_open"] += 1
                continue

            entry = trade["entry_price"]
            direction = trade["direction"]
            pnl = (current_price - entry) if direction == "long" else (entry - current_price)
            pnl_pct = (pnl / entry * 100) if entry > 0 else 0.0
            self._update_trade_price(trade["id"], current_price, pnl * trade["quantity"], pnl_pct)

            stop = trade["stop_loss"]
            tp = trade["take_profit"]
            hit_stop = stop and ((direction == "long" and current_price <= stop) or
                                 (direction == "short" and current_price >= stop))
            hit_tp = tp and ((direction == "long" and current_price >= tp) or
                             (direction == "short" and current_price <= tp))

            if hit_stop:
                self.record_trade_outcome(trade["id"], current_price)
                logger.info("Position stopped out: %s @ %.2f", trade["symbol"], current_price)
                summary["stopped_out"] += 1
            elif hit_tp:
                self.record_trade_outcome(trade["id"], current_price)
                logger.info("Take profit hit: %s @ %.2f", trade["symbol"], current_price)
                summary["take_profit_hit"] += 1
            else:
                summary["still_open"] += 1

        if self._bus:
            msg = self._bus.create_message(
                topic="system.hedge_fund",
                sender="hedge_fund",
                payload={"type": "position_monitor", **summary},
            )
            await self._bus.publish(msg)
        return summary

    def get_open_positions_summary(self) -> list[dict[str, Any]]:
        """Return formatted summary of all open positions with current P&L."""
        rows = self.conn.execute(
            "SELECT id, symbol, direction, quantity, entry_price, current_price, "
            "pnl, pnl_pct, stop_loss, take_profit, opened_at "
            "FROM trades WHERE status = 'open' ORDER BY opened_at DESC"
        ).fetchall()
        return [
            {**dict(r), "pnl_display": f"${r['pnl']:.2f} ({r['pnl_pct']:+.1f}%)"}
            for r in rows
        ]

    # ── Autonomous Run ─────────────────────────────────────────

    async def run_cycle(self) -> dict[str, Any]:
        """Run one full hedge fund cycle: scan → analyze → decide → execute."""
        results: dict[str, Any] = {
            "signals_generated": 0,
            "signals_passed_risk": 0,
            "trades_executed": 0,
            "trades_blocked": 0,
        }

        # 1. Scan markets
        signals = await self.scan_markets()
        results["signals_generated"] = len(signals)

        # 2. Get portfolio state
        portfolio = await self.get_portfolio()
        portfolio_value = portfolio.get("total_value", 100000)

        # 3. Filter through risk controls and execute
        import json as _json
        for signal in sorted(signals, key=lambda s: s.confidence, reverse=True):
            symbol = signal.symbol
            direction = signal.direction
            confidence = signal.confidence
            signal_context = ""

            # Get technical analysis from market data service
            if hasattr(self, '_market_data') and self._market_data:
                try:
                    analysis = await self._market_data.get_full_analysis(symbol)
                    signal_context = f"Technical Analysis for {symbol}: {_json.dumps(analysis.get('indicators', {}), default=str)[:500]}"
                except Exception as e:
                    logger.warning("Market data service unavailable: %s", e)

            # For HIGH confidence signals, consult trading consensus
            if hasattr(self, '_trading_consensus') and self._trading_consensus and confidence > 0.7:
                try:
                    consensus = await self._trading_consensus.analyze_ticker(symbol, signal_context)
                    confidence = (confidence + consensus.confidence) / 2
                except Exception as e:
                    logger.warning("Trading consensus unavailable: %s", e)

            # Consult investor panel for high-confidence signals
            if hasattr(self, '_investor_panel') and self._investor_panel and confidence > 0.75:
                try:
                    opinions = await self._investor_panel.consult_panel(
                        symbol=symbol,
                        data={"signal": direction, "confidence": confidence, "context": signal_context[:500] if signal_context else ""},
                        investors=["warren_buffett", "cathie_wood", "ray_dalio", "michael_burry"],
                    )
                    if opinions:
                        bullish = sum(1 for o in opinions if o.signal == "bullish")
                        bearish = sum(1 for o in opinions if o.signal == "bearish")
                        # Adjust confidence based on investor consensus
                        investor_consensus = bullish / max(len(opinions), 1)
                        confidence = (confidence * 0.6) + (investor_consensus * 0.4)
                        logger.info("Investor panel: %d/%d bullish, adjusted confidence=%.2f",
                                   bullish, len(opinions), confidence)
                except Exception as e:
                    logger.debug("Investor panel unavailable: %s", e)

            # Check trading autonomy before execution
            if hasattr(self, '_trading_autonomy') and self._trading_autonomy:
                try:
                    position_value = portfolio_value * RISK_LIMITS["max_position_pct"]
                    decision = self._trading_autonomy.classify_trade_risk(
                        symbol=symbol, direction=direction, confidence=confidence,
                        dollar_amount=position_value, portfolio_value=portfolio_value,
                    )
                    # decision.risk_level determines approval path
                except Exception as e:
                    logger.warning("Trading autonomy unavailable: %s", e)

            # Rebuild signal with potentially updated confidence
            if confidence != signal.confidence:
                signal = Signal(
                    id=signal.id, symbol=signal.symbol, direction=signal.direction,
                    confidence=confidence, source=signal.source, reasoning=signal.reasoning,
                    timeframe=signal.timeframe, entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss, take_profit=signal.take_profit,
                    created_at=signal.created_at,
                )

            ok, reason = self.check_risk(signal, portfolio_value)
            if ok:
                results["signals_passed_risk"] += 1
                trade_result = await self.execute_signal(signal, portfolio_value)
                if trade_result and trade_result.get("status") == "executed":
                    results["trades_executed"] += 1
                else:
                    results["trades_blocked"] += 1
            else:
                results["trades_blocked"] += 1

        # 4. Snapshot portfolio
        await self.snapshot_portfolio()

        logger.info(
            "Hedge fund cycle: %d signals, %d passed risk, %d executed",
            results["signals_generated"], results["signals_passed_risk"],
            results["trades_executed"],
        )
        return results

    # ── Status & Stats ─────────────────────────────────────────

    def get_signals(self, limit: int = 50) -> list[dict]:
        """Get recent signals."""
        rows = self.conn.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_trades(self, status: str = "all", limit: int = 50) -> list[dict]:
        """Get trades, optionally filtered by status."""
        if status == "all":
            rows = self.conn.execute(
                "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM trades WHERE status = ? ORDER BY opened_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_performance(self) -> dict[str, Any]:
        """Get overall hedge fund performance."""
        trades = self.conn.execute(
            "SELECT * FROM trades WHERE status = 'closed'"
        ).fetchall()
        if not trades:
            return {"total_trades": 0, "win_rate": 0, "total_pnl": 0}

        wins = sum(1 for t in trades if t["pnl"] > 0)
        total_pnl = sum(t["pnl"] for t in trades)

        snapshots = self.conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY created_at DESC LIMIT 30"
        ).fetchall()

        return {
            "total_trades": len(trades),
            "open_trades": self.conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE status = 'open'"
            ).fetchone()["c"],
            "winning_trades": wins,
            "losing_trades": len(trades) - wins,
            "win_rate": round(wins / len(trades) * 100, 1) if trades else 0,
            "total_pnl": round(total_pnl, 2),
            "daily_pnl": round(self._daily_pnl, 2),
            "total_signals": self.conn.execute(
                "SELECT COUNT(*) as c FROM signals"
            ).fetchone()["c"],
            "signals_acted_on": self.conn.execute(
                "SELECT COUNT(*) as c FROM signals WHERE acted_on = 1"
            ).fetchone()["c"],
            "portfolio_snapshots": len(snapshots),
        }

    def get_strategy_weights(self) -> list[dict]:
        """Get learned strategy weights."""
        rows = self.conn.execute(
            "SELECT * FROM strategy_weights ORDER BY weight DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        return self.get_performance()
