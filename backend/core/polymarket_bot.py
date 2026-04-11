"""
Polymarket Trading Bot — fast prediction market trading with two strategies.

Strategy 1: SCALPING — detect odds momentum shifts, buy/sell for quick flips.
Strategy 2: EDGE HUNTING — find mispriced markets using LLM analysis + data.

Tracks all market data, positions, P&L in SQLite for analysis and learning.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("root.polymarket_bot")

GAMMA_BASE = "https://gamma-api.polymarket.com"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "polymarket.db")

# Risk limits
MAX_POSITION_USDC = 50.0       # Max USDC per single position
MAX_TOTAL_EXPOSURE = 500.0     # Max total USDC across all positions
MAX_POSITIONS = 20             # Max concurrent positions
MIN_LIQUIDITY = 5000.0         # Skip markets with < $5k liquidity
MIN_VOLUME_24H = 1000.0        # Skip markets with < $1k 24h volume
SCALP_PROFIT_TARGET = 0.03     # 3 cent profit target for scalps
SCALP_STOP_LOSS = 0.05         # 5 cent stop loss for scalps
EDGE_MIN_CONFIDENCE = 0.65     # Min LLM confidence to trade edge


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MarketSnapshot:
    """Point-in-time snapshot of a Polymarket market."""
    condition_id: str
    question: str
    yes_price: float
    no_price: float
    volume_24h: float
    liquidity: float
    spread: float
    token_ids: list[str]
    timestamp: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class BotSignal:
    """Trading signal from the bot."""
    id: str
    market_id: str
    question: str
    side: str          # BUY or SELL
    outcome: str       # YES or NO
    token_id: str
    price: float
    size: float
    strategy: str      # scalp or edge
    confidence: float
    reasoning: str
    timestamp: str = field(default_factory=_now_iso)


class PolymarketBot:
    """Autonomous Polymarket trading bot with scalping + edge hunting."""

    def __init__(
        self,
        plugins=None,
        llm=None,
        bus=None,
        approval=None,
        memory=None,
        experience=None,
        learning=None,
    ) -> None:
        self._plugins = plugins
        self._llm = llm
        self._bus = bus
        self._approval = approval
        self._memory = memory
        self._experience = experience
        self._learning = learning
        self._sandbox_gate = None  # Set via main.py
        self._notification_engine = None  # Set via main.py
        self._db_path = os.path.abspath(DB_PATH)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database for market data and positions."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT NOT NULL,
                question TEXT,
                yes_price REAL,
                no_price REAL,
                volume_24h REAL,
                liquidity REAL,
                spread REAL,
                token_ids TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                condition_id TEXT NOT NULL,
                question TEXT,
                token_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                size REAL NOT NULL,
                current_price REAL,
                pnl REAL DEFAULT 0,
                strategy TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                order_id TEXT,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                close_price REAL,
                close_reason TEXT
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                size REAL NOT NULL,
                order_id TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                question TEXT,
                side TEXT,
                outcome TEXT,
                token_id TEXT,
                price REAL,
                size REAL,
                strategy TEXT,
                confidence REAL,
                reasoning TEXT,
                executed INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_cid ON market_snapshots(condition_id);
            CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
            CREATE INDEX IF NOT EXISTS idx_price_history_token ON price_history(token_id, timestamp);
        """)
        conn.close()
        logger.info("Polymarket bot DB initialized at %s", self._db_path)

    @property
    def conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db_path)
        c.execute("PRAGMA journal_mode=WAL")
        c.row_factory = sqlite3.Row
        return c

    # ── Market Data Collection ─────────────────────────────────

    async def scan_markets(self, limit: int = 30) -> list[MarketSnapshot]:
        """Fetch top markets by volume and store snapshots."""
        if self._notification_engine:
            await self._notification_engine.audit_external_action(
                action="Polymarket Market Scan",
                target="Gamma API (gamma-api.polymarket.com)",
                source="polymarket_bot",
                level="low",
                details=f"Scanning top {limit} active prediction markets by volume",
            )

        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(f"{GAMMA_BASE}/markets", params={
                "active": "true",
                "closed": "false",
                "limit": limit,
            })
            if resp.status_code >= 400:
                logger.error("Gamma API error %d: %s", resp.status_code, resp.text[:200])
                return []
            data = resp.json()

        if not isinstance(data, list):
            return []

        # Sort by 24h volume descending (API doesn't support order param)
        data.sort(key=lambda m: float(m.get("volume24hr", 0) or 0), reverse=True)

        snapshots = []
        conn = self.conn
        try:
            for m in data:
                prices = m.get("outcomePrices", "")
                if isinstance(prices, str):
                    try:
                        prices = json.loads(prices)
                    except Exception:
                        prices = []

                token_ids = m.get("clobTokenIds", [])
                if isinstance(token_ids, str):
                    try:
                        token_ids = json.loads(token_ids)
                    except Exception:
                        token_ids = []

                snap = MarketSnapshot(
                    condition_id=m.get("conditionId", ""),
                    question=m.get("question", "")[:200],
                    yes_price=float(prices[0]) if prices else 0,
                    no_price=float(prices[1]) if len(prices) > 1 else 0,
                    volume_24h=float(m.get("volume24hr", 0) or 0),
                    liquidity=float(m.get("liquidity", 0) or 0),
                    spread=abs(float(prices[0]) - float(prices[1])) if len(prices) >= 2 else 0,
                    token_ids=token_ids,
                )
                snapshots.append(snap)

                # Store snapshot
                conn.execute(
                    """INSERT INTO market_snapshots
                       (condition_id, question, yes_price, no_price, volume_24h,
                        liquidity, spread, token_ids, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (snap.condition_id, snap.question, snap.yes_price,
                     snap.no_price, snap.volume_24h, snap.liquidity,
                     snap.spread, json.dumps(snap.token_ids), snap.timestamp),
                )

                # Store price history for each token
                for i, tid in enumerate(token_ids):
                    price = float(prices[i]) if i < len(prices) else 0
                    conn.execute(
                        "INSERT INTO price_history (token_id, price, timestamp) VALUES (?, ?, ?)",
                        (tid, price, snap.timestamp),
                    )

            conn.commit()
        finally:
            conn.close()

        logger.info("Scanned %d markets, stored snapshots", len(snapshots))
        return snapshots

    # ── Strategy 1: Scalping ───────────────────────────────────

    async def find_scalp_opportunities(
        self, snapshots: list[MarketSnapshot],
    ) -> list[BotSignal]:
        """Find scalp opportunities from price momentum."""
        signals = []
        conn = self.conn

        try:
            for snap in snapshots:
                if snap.liquidity < MIN_LIQUIDITY or snap.volume_24h < MIN_VOLUME_24H:
                    continue
                if not snap.token_ids or len(snap.token_ids) < 2:
                    continue

                # Get price history for momentum detection
                rows = conn.execute(
                    """SELECT price, timestamp FROM price_history
                       WHERE token_id = ? ORDER BY timestamp DESC LIMIT 10""",
                    (snap.token_ids[0],),
                ).fetchall()

                if len(rows) < 3:
                    continue  # Need history for momentum

                prices = [r["price"] for r in rows]
                current = prices[0]
                prev = prices[1]
                prev2 = prices[2]

                # Detect momentum: 2+ consecutive moves in same direction
                delta1 = current - prev
                delta2 = prev - prev2

                # Upward momentum on YES → buy YES
                if delta1 > 0.01 and delta2 > 0.005 and current < 0.85:
                    size = min(MAX_POSITION_USDC / current, 100)
                    signals.append(BotSignal(
                        id=f"scalp_{uuid.uuid4().hex[:8]}",
                        market_id=snap.condition_id,
                        question=snap.question,
                        side="BUY",
                        outcome="YES",
                        token_id=snap.token_ids[0],
                        price=current,
                        size=round(size, 2),
                        strategy="scalp",
                        confidence=min(0.5 + abs(delta1) * 5, 0.85),
                        reasoning=f"Upward momentum: +{delta1:.3f} then +{delta2:.3f}. "
                                  f"Vol=${snap.volume_24h:.0f}, Liq=${snap.liquidity:.0f}",
                    ))

                # Downward momentum on YES → buy NO (contrarian)
                elif delta1 < -0.01 and delta2 < -0.005 and current > 0.15:
                    no_price = 1 - current
                    size = min(MAX_POSITION_USDC / no_price, 100) if no_price > 0 else 0
                    if size > 0 and len(snap.token_ids) > 1:
                        signals.append(BotSignal(
                            id=f"scalp_{uuid.uuid4().hex[:8]}",
                            market_id=snap.condition_id,
                            question=snap.question,
                            side="BUY",
                            outcome="NO",
                            token_id=snap.token_ids[1],
                            price=no_price,
                            size=round(size, 2),
                            strategy="scalp",
                            confidence=min(0.5 + abs(delta1) * 5, 0.85),
                            reasoning=f"Downward momentum: {delta1:.3f} then {delta2:.3f}. "
                                      f"Buying NO at ${no_price:.2f}",
                        ))

                # Wide spread opportunity — buy at bid, sell at ask
                if snap.spread > 0.04 and snap.liquidity > 10000:
                    signals.append(BotSignal(
                        id=f"scalp_{uuid.uuid4().hex[:8]}",
                        market_id=snap.condition_id,
                        question=snap.question,
                        side="BUY",
                        outcome="YES",
                        token_id=snap.token_ids[0],
                        price=snap.yes_price - snap.spread / 2,
                        size=round(min(MAX_POSITION_USDC / snap.yes_price, 50), 2),
                        strategy="scalp",
                        confidence=0.55,
                        reasoning=f"Wide spread: {snap.spread:.3f}. Placing bid below mid.",
                    ))
        finally:
            conn.close()

        logger.info("Found %d scalp signals", len(signals))
        return signals

    # ── Strategy 2: Edge Hunting ───────────────────────────────

    async def find_edge_opportunities(
        self, snapshots: list[MarketSnapshot],
    ) -> list[BotSignal]:
        """Use LLM to find mispriced markets."""
        if not self._llm:
            return []

        # Filter to interesting markets (mid-range prices = most edge potential)
        candidates = [
            s for s in snapshots
            if s.liquidity >= MIN_LIQUIDITY
            and s.volume_24h >= MIN_VOLUME_24H
            and 0.15 < s.yes_price < 0.85
            and s.token_ids
        ][:10]  # Analyze top 10 to save LLM calls

        if not candidates:
            return []

        market_text = "\n".join(
            f"{i+1}. \"{c.question}\" — YES: ${c.yes_price:.2f}, NO: ${c.no_price:.2f}, "
            f"Vol24h: ${c.volume_24h:,.0f}, Liq: ${c.liquidity:,.0f}"
            for i, c in enumerate(candidates)
        )

        now = datetime.now(timezone.utc)
        prompt = (
            f"Today is {now.strftime('%A, %B %d, %Y')} UTC.\n\n"
            f"Analyze these prediction markets for mispricing. "
            f"Output ONLY valid JSON — an array of opportunities.\n\n"
            f"Markets:\n{market_text}\n\n"
            f"For each mispriced market, output:\n"
            f'{{"market_index": 1, "outcome": "YES", "fair_price": 0.65, '
            f'"current_price": 0.50, "edge": 0.15, "confidence": 0.7, '
            f'"reasoning": "why this is mispriced"}}\n\n'
            f"Only include markets where edge > 0.05 and confidence > 0.6.\n"
            f"Output [] if no clear edge. Raw JSON only, no markdown."
        )

        try:
            response = await self._llm.complete(
                system="You are a prediction market analyst. Find mispriced markets. "
                       "Be conservative — only flag clear mispricings with solid reasoning.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="default",
                temperature=0.3,
                max_tokens=1500,
            )

            # Parse LLM response
            text = response.strip()
            if "```" in text:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                text = text[start:end].strip()

            opportunities = json.loads(text)
            if not isinstance(opportunities, list):
                opportunities = [opportunities] if isinstance(opportunities, dict) else []

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Edge hunting LLM parse failed: %s", e)
            return []
        except Exception as e:
            logger.error("Edge hunting LLM error: %s", e)
            return []

        signals = []
        for opp in opportunities:
            idx = opp.get("market_index", 0) - 1
            if idx < 0 or idx >= len(candidates):
                continue

            market = candidates[idx]
            confidence = float(opp.get("confidence", 0))
            edge = float(opp.get("edge", 0))

            if confidence < EDGE_MIN_CONFIDENCE or edge < 0.05:
                continue

            outcome = opp.get("outcome", "YES").upper()
            token_idx = 0 if outcome == "YES" else 1
            if token_idx >= len(market.token_ids):
                continue

            current = market.yes_price if outcome == "YES" else market.no_price
            size = min(MAX_POSITION_USDC / current, 100) if current > 0 else 0

            signals.append(BotSignal(
                id=f"edge_{uuid.uuid4().hex[:8]}",
                market_id=market.condition_id,
                question=market.question,
                side="BUY",
                outcome=outcome,
                token_id=market.token_ids[token_idx],
                price=current,
                size=round(size, 2),
                strategy="edge",
                confidence=confidence,
                reasoning=opp.get("reasoning", "LLM-detected edge")[:300],
            ))

        logger.info("Found %d edge signals", len(signals))
        return signals

    # ── Signal Execution ───────────────────────────────────────

    async def execute_signal(self, signal: BotSignal) -> dict[str, Any]:
        """Execute a trading signal via plugin."""
        if not self._plugins:
            return {"error": "No plugins configured"}

        # ── Sandbox gate check ──────────────────────────────────
        if self._sandbox_gate is not None:
            decision = self._sandbox_gate.check(
                system_id="trading",
                action=f"polymarket_trade:{signal.market_id}",
                description=f"{signal.strategy}: {signal.side} {signal.outcome} @ ${signal.price:.4f} — {signal.question[:80]}",
                context={"strategy": signal.strategy, "confidence": signal.confidence, "size": signal.size},
                agent_id="polymarket_bot",
                risk_level="critical",
            )
            if not decision.was_executed:
                return {
                    "status": "sandboxed",
                    "signal_id": signal.id,
                    "message": f"Trade simulated in sandbox — not sent to Polymarket",
                }

        # ── Approval chain check ────────────────────────────────
        if self._approval:
            approval = await self._approval.request_approval(
                agent_id="polymarket_bot",
                action="execute_trade",
                description=f"Polymarket {signal.strategy}: {signal.side} {signal.outcome} {signal.size} shares @ ${signal.price:.4f} — {signal.question[:80]}",
                context={"involves_money": True, "strategy": signal.strategy, "market_id": signal.market_id},
                reason=f"Signal: {signal.strategy} on '{signal.question[:60]}' with {signal.confidence:.0%} confidence",
                benefit=f"Potential profit from {signal.side} {signal.outcome} position ({signal.reasoning[:100]})",
                risk_analysis=f"Size: {signal.size} shares @ ${signal.price:.4f} = ${signal.price * signal.size:.2f} exposure",
            )
            if hasattr(approval, 'status'):
                if approval.status.value == "rejected":
                    return {"status": "rejected", "reason": "Yohan rejected the trade"}
                if approval.status.value == "pending":
                    return {
                        "status": "pending_approval",
                        "approval_id": approval.id,
                        "signal_id": signal.id,
                        "message": "Trade awaiting Yohan's approval — will NOT execute until approved",
                    }

        # Check position limits
        conn = self.conn
        try:
            open_count = conn.execute(
                "SELECT COUNT(*) as c FROM positions WHERE status = 'open'"
            ).fetchone()["c"]
            total_exposure = conn.execute(
                "SELECT COALESCE(SUM(entry_price * size), 0) as total FROM positions WHERE status = 'open'"
            ).fetchone()["total"]
        finally:
            conn.close()

        if open_count >= MAX_POSITIONS:
            return {"error": f"Max positions reached ({MAX_POSITIONS})"}
        if total_exposure + (signal.price * signal.size) > MAX_TOTAL_EXPOSURE:
            return {"error": f"Would exceed max exposure (${MAX_TOTAL_EXPOSURE})"}

        # Store signal
        conn = self.conn
        try:
            conn.execute(
                """INSERT OR IGNORE INTO signals
                   (id, market_id, question, side, outcome, token_id,
                    price, size, strategy, confidence, reasoning, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (signal.id, signal.market_id, signal.question, signal.side,
                 signal.outcome, signal.token_id, signal.price, signal.size,
                 signal.strategy, signal.confidence, signal.reasoning, signal.timestamp),
            )
            conn.commit()
        finally:
            conn.close()

        # Notify BEFORE trade execution
        if self._notification_engine:
            await self._notification_engine.audit_external_action(
                action=f"TRADE: Polymarket {signal.strategy} {signal.side} {signal.outcome}",
                target="Polymarket CLOB API",
                source="polymarket_bot",
                level="critical",
                details=f"Market: {signal.question[:80]}\nSize: {signal.size} @ ${signal.price:.4f} = ${signal.price * signal.size:.2f}\nConfidence: {signal.confidence:.0%}",
            )

        # Place order
        if signal.strategy == "scalp":
            # Limit order for scalps (better fills)
            result = await self._plugins.invoke("polymarket_place_order", {
                "token_id": signal.token_id,
                "price": signal.price,
                "size": signal.size,
                "side": signal.side,
            })
        else:
            # Market order for edge trades (get in fast)
            result = await self._plugins.invoke("polymarket_market_order", {
                "token_id": signal.token_id,
                "amount": signal.price * signal.size,
                "side": signal.side,
            })

        if not result.success or (isinstance(result.output, dict) and "error" in result.output):
            error = result.error or result.output.get("error", "unknown")
            logger.warning("Order failed for %s: %s", signal.question[:50], error)
            return {"error": error}

        # Record position
        pos_id = f"pos_{uuid.uuid4().hex[:8]}"
        order_id = ""
        if isinstance(result.output, dict):
            order_id = result.output.get("order_id", "")

        conn = self.conn
        try:
            conn.execute(
                """INSERT INTO positions
                   (id, condition_id, question, token_id, outcome, side,
                    entry_price, size, strategy, status, order_id, opened_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
                (pos_id, signal.market_id, signal.question, signal.token_id,
                 signal.outcome, signal.side, signal.price, signal.size,
                 signal.strategy, order_id, _now_iso()),
            )
            conn.execute(
                """INSERT INTO trades (position_id, side, price, size, order_id, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (pos_id, signal.side, signal.price, signal.size, order_id, _now_iso()),
            )
            conn.execute(
                "UPDATE signals SET executed = 1 WHERE id = ?", (signal.id,),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Executed %s: %s %s %s @ $%.2f x %.0f (conf=%.0f%%)",
            signal.strategy, signal.side, signal.outcome, signal.question[:40],
            signal.price, signal.size, signal.confidence * 100,
        )

        return {
            "status": "executed",
            "position_id": pos_id,
            "order_id": order_id,
            "strategy": signal.strategy,
            "question": signal.question,
            "outcome": signal.outcome,
            "price": signal.price,
            "size": signal.size,
        }

    # ── Position Monitoring ────────────────────────────────────

    async def monitor_positions(self) -> dict[str, int]:
        """Check open positions for profit targets and stop losses."""
        conn = self.conn
        summary = {"checked": 0, "closed_profit": 0, "closed_loss": 0, "still_open": 0}

        try:
            positions = conn.execute(
                "SELECT * FROM positions WHERE status = 'open'"
            ).fetchall()
        finally:
            conn.close()

        for pos in positions:
            summary["checked"] += 1

            # Get current price
            if not self._plugins:
                summary["still_open"] += 1
                continue

            result = await self._plugins.invoke("polymarket_price", {
                "token_id": pos["token_id"],
            })

            if not result.success or not isinstance(result.output, dict):
                summary["still_open"] += 1
                continue

            current = result.output.get("midpoint", 0)
            if not current:
                summary["still_open"] += 1
                continue

            entry = pos["entry_price"]
            pnl = (current - entry) * pos["size"]
            pnl_pct = (current - entry) / entry if entry > 0 else 0

            # Update current price
            conn = self.conn
            try:
                conn.execute(
                    "UPDATE positions SET current_price = ?, pnl = ? WHERE id = ?",
                    (current, pnl, pos["id"]),
                )
                conn.commit()
            finally:
                conn.close()

            # Store price point
            conn = self.conn
            try:
                conn.execute(
                    "INSERT INTO price_history (token_id, price, timestamp) VALUES (?, ?, ?)",
                    (pos["token_id"], current, _now_iso()),
                )
                conn.commit()
            finally:
                conn.close()

            strategy = pos["strategy"]
            should_close = False
            close_reason = ""

            if strategy == "scalp":
                if pnl_pct >= SCALP_PROFIT_TARGET:
                    should_close = True
                    close_reason = f"profit_target ({pnl_pct:.1%})"
                elif pnl_pct <= -SCALP_STOP_LOSS:
                    should_close = True
                    close_reason = f"stop_loss ({pnl_pct:.1%})"
            else:  # edge
                if pnl_pct >= 0.10:  # 10% profit target for edge
                    should_close = True
                    close_reason = f"edge_profit ({pnl_pct:.1%})"
                elif pnl_pct <= -0.08:  # 8% stop for edge
                    should_close = True
                    close_reason = f"edge_stop ({pnl_pct:.1%})"

            if should_close:
                await self._close_position(pos["id"], current, close_reason)
                if pnl > 0:
                    summary["closed_profit"] += 1
                else:
                    summary["closed_loss"] += 1
            else:
                summary["still_open"] += 1

        logger.info(
            "Position monitor: %d checked, %d profit, %d loss, %d open",
            summary["checked"], summary["closed_profit"],
            summary["closed_loss"], summary["still_open"],
        )
        return summary

    async def _close_position(
        self, position_id: str, close_price: float, reason: str,
    ) -> None:
        """Close a position by selling."""
        conn = self.conn
        try:
            pos = conn.execute(
                "SELECT * FROM positions WHERE id = ?", (position_id,),
            ).fetchone()
        finally:
            conn.close()

        if not pos:
            return

        # Sell shares
        if self._plugins:
            await self._plugins.invoke("polymarket_market_order", {
                "token_id": pos["token_id"],
                "amount": pos["size"],
                "side": "SELL",
            })

        pnl = (close_price - pos["entry_price"]) * pos["size"]

        conn = self.conn
        try:
            conn.execute(
                """UPDATE positions
                   SET status = 'closed', close_price = ?, close_reason = ?,
                       closed_at = ?, pnl = ?, current_price = ?
                   WHERE id = ?""",
                (close_price, reason, _now_iso(), pnl, close_price, position_id),
            )
            conn.execute(
                "INSERT INTO trades (position_id, side, price, size, timestamp) VALUES (?, 'SELL', ?, ?, ?)",
                (position_id, close_price, pos["size"], _now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Closed position %s: %s @ $%.2f → $%.2f, P&L: $%.2f (%s)",
            position_id, pos["question"][:40], pos["entry_price"],
            close_price, pnl, reason,
        )

        # Record experience
        if self._experience:
            try:
                exp_type = "success" if pnl > 0 else "failure"
                self._experience.record_experience(
                    experience_type=exp_type,
                    domain="polymarket",
                    title=f"{pos['strategy']} trade: {pos['question'][:60]}",
                    description=(
                        f"Strategy: {pos['strategy']}, Outcome: {pos['outcome']}, "
                        f"Entry: ${pos['entry_price']:.2f}, Exit: ${close_price:.2f}, "
                        f"P&L: ${pnl:.2f}, Reason: {reason}"
                    ),
                    context={
                        "strategy": pos["strategy"],
                        "pnl": pnl,
                        "entry": pos["entry_price"],
                        "exit": close_price,
                    },
                )
            except Exception as e:
                logger.warning("Experience recording failed: %s", e)

    # ── Full Trading Cycle ─────────────────────────────────────

    async def run_cycle(self) -> dict[str, Any]:
        """Run one full trading cycle: scan → analyze → trade → monitor."""
        results: dict[str, Any] = {
            "markets_scanned": 0,
            "scalp_signals": 0,
            "edge_signals": 0,
            "trades_executed": 0,
            "trades_failed": 0,
            "positions_monitored": {},
        }

        # 1. Scan markets
        snapshots = await self.scan_markets(limit=30)
        results["markets_scanned"] = len(snapshots)

        if not snapshots:
            return results

        # 2. Find scalp opportunities
        scalp_signals = await self.find_scalp_opportunities(snapshots)
        results["scalp_signals"] = len(scalp_signals)

        # 3. Find edge opportunities (LLM-powered)
        edge_signals = await self.find_edge_opportunities(snapshots)
        results["edge_signals"] = len(edge_signals)

        # 4. Execute best signals (sorted by confidence)
        all_signals = sorted(
            scalp_signals + edge_signals,
            key=lambda s: s.confidence,
            reverse=True,
        )[:5]  # Max 5 new trades per cycle

        for signal in all_signals:
            try:
                trade_result = await self.execute_signal(signal)
                if trade_result.get("status") == "executed":
                    results["trades_executed"] += 1
                else:
                    results["trades_failed"] += 1
            except Exception as e:
                logger.error("Trade execution error: %s", e)
                results["trades_failed"] += 1

        # 5. Monitor existing positions
        results["positions_monitored"] = await self.monitor_positions()

        logger.info(
            "Polymarket cycle: %d markets, %d scalp, %d edge signals, %d executed",
            results["markets_scanned"], results["scalp_signals"],
            results["edge_signals"], results["trades_executed"],
        )
        return results

    # ── Stats & Reporting ──────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Get bot statistics."""
        conn = self.conn
        try:
            open_positions = conn.execute(
                "SELECT COUNT(*) as c FROM positions WHERE status = 'open'"
            ).fetchone()["c"]
            closed_positions = conn.execute(
                "SELECT COUNT(*) as c FROM positions WHERE status = 'closed'"
            ).fetchone()["c"]
            total_pnl = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) as total FROM positions WHERE status = 'closed'"
            ).fetchone()["total"]
            win_count = conn.execute(
                "SELECT COUNT(*) as c FROM positions WHERE status = 'closed' AND pnl > 0"
            ).fetchone()["c"]
            total_signals = conn.execute(
                "SELECT COUNT(*) as c FROM signals"
            ).fetchone()["c"]
            snapshots = conn.execute(
                "SELECT COUNT(*) as c FROM market_snapshots"
            ).fetchone()["c"]

            win_rate = (win_count / closed_positions * 100) if closed_positions > 0 else 0

            # Recent trades
            recent = conn.execute(
                """SELECT question, strategy, outcome, entry_price, close_price, pnl, close_reason
                   FROM positions WHERE status = 'closed'
                   ORDER BY closed_at DESC LIMIT 5"""
            ).fetchall()

            return {
                "open_positions": open_positions,
                "closed_positions": closed_positions,
                "total_pnl": round(total_pnl, 2),
                "win_rate": round(win_rate, 1),
                "win_count": win_count,
                "loss_count": closed_positions - win_count,
                "total_signals": total_signals,
                "market_snapshots": snapshots,
                "recent_trades": [
                    {
                        "question": r["question"][:60],
                        "strategy": r["strategy"],
                        "outcome": r["outcome"],
                        "entry": r["entry_price"],
                        "exit": r["close_price"],
                        "pnl": round(r["pnl"], 2) if r["pnl"] else 0,
                        "reason": r["close_reason"],
                    }
                    for r in recent
                ],
            }
        finally:
            conn.close()

    def get_open_positions(self) -> list[dict]:
        """Get all open positions with current P&L."""
        conn = self.conn
        try:
            rows = conn.execute(
                "SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at DESC"
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "question": r["question"][:80],
                    "outcome": r["outcome"],
                    "strategy": r["strategy"],
                    "entry_price": r["entry_price"],
                    "current_price": r["current_price"],
                    "size": r["size"],
                    "pnl": round(r["pnl"], 2) if r["pnl"] else 0,
                    "opened_at": r["opened_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_market_history(self, condition_id: str, limit: int = 50) -> list[dict]:
        """Get price history for a market."""
        conn = self.conn
        try:
            rows = conn.execute(
                """SELECT yes_price, no_price, volume_24h, liquidity, timestamp
                   FROM market_snapshots WHERE condition_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (condition_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
