"""
Revenue Engine — 5-stream automated revenue system ($10k-$100k/month target).

Revenue streams:
1. Automation Agency ($3k-$30k) — build and sell automations
2. Micro SaaS Factory ($5k-$50k) — agents build SaaS tools
3. Content Network ($2k-$20k) — media ecosystem (ads, affiliates, sponsors)
4. Data Products ($5k-$30k) — datasets, APIs, intelligence reports
5. AI Consulting ($5k-$50k) — automation design, AI workflows

Financial survival system:
- Minimum budget: $400/month
- Emergency mode when revenue < cost
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from backend.config import DATA_DIR, SURVIVAL_BUDGET

REVENUE_DB = DATA_DIR / "revenue.db"

logger = logging.getLogger("root.revenue")


class RevenueStream(str, Enum):
    AUTOMATION_AGENCY = "automation_agency"
    MICRO_SAAS = "micro_saas"
    CONTENT_NETWORK = "content_network"
    DATA_PRODUCTS = "data_products"
    AI_CONSULTING = "ai_consulting"


class StreamStatus(str, Enum):
    IDEA = "idea"
    BUILDING = "building"
    LAUNCHED = "launched"
    EARNING = "earning"
    PAUSED = "paused"


STREAM_TARGETS: dict[RevenueStream, tuple[float, float]] = {
    RevenueStream.AUTOMATION_AGENCY: (3000.0, 30000.0),
    RevenueStream.MICRO_SAAS: (5000.0, 50000.0),
    RevenueStream.CONTENT_NETWORK: (2000.0, 20000.0),
    RevenueStream.DATA_PRODUCTS: (5000.0, 30000.0),
    RevenueStream.AI_CONSULTING: (5000.0, 50000.0),
}


@dataclass(frozen=True)
class RevenueProduct:
    """Immutable product within a revenue stream."""
    id: str
    name: str
    stream: RevenueStream
    status: StreamStatus
    description: str = ""
    monthly_revenue: float = 0.0
    monthly_cost: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    launched_at: Optional[str] = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinancialSnapshot:
    """Immutable point-in-time financial state."""
    total_revenue: float
    total_cost: float
    profit: float
    by_stream: dict[str, float]
    emergency_mode: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RevenueEngine:
    """Manages 5 revenue streams and financial survival system."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or REVENUE_DB)
        self._conn: Optional[sqlite3.Connection] = None
        self._interest_engine = None  # Set via main.py
        self._sandbox_gate = None  # Set via main.py
        self._notification_engine = None  # Set via main.py

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("RevenueEngine not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS revenue_products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                stream TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'idea',
                description TEXT DEFAULT '',
                monthly_revenue REAL DEFAULT 0.0,
                monthly_cost REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                launched_at TEXT,
                metrics TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS revenue_transactions (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES revenue_products(id)
            );

            CREATE INDEX IF NOT EXISTS idx_rp_stream ON revenue_products(stream);
            CREATE INDEX IF NOT EXISTS idx_rp_status ON revenue_products(status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_rp_name_stream ON revenue_products(name, stream);
            CREATE INDEX IF NOT EXISTS idx_rt_product ON revenue_transactions(product_id);
        """)

    # ── Product Management ─────────────────────────────────────

    def set_interest_engine(self, engine) -> None:
        self._interest_engine = engine

    def add_product(
        self,
        name: str,
        stream: str,
        description: str = "",
        monthly_cost: float = 0.0,
    ) -> RevenueProduct:
        """Add a new product to a revenue stream."""
        # Interest gate — block misaligned products before creation
        if self._interest_engine:
            allowed, reason = self._interest_engine.gate(
                subject=name,
                context=f"Revenue stream: {stream}. {description}",
            )
            if not allowed:
                logger.info("Product blocked by interest gate: %s — %s", name, reason)
                return RevenueProduct(
                    id="blocked", name=name,
                    stream=RevenueStream(stream),
                    status=StreamStatus.PAUSED,
                    description=f"[BLOCKED] {reason}",
                    monthly_cost=monthly_cost,
                )

        rv_stream = RevenueStream(stream)
        prod_id = f"prod_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT OR IGNORE INTO revenue_products
               (id, name, stream, status, description, monthly_revenue,
                monthly_cost, created_at)
               VALUES (?, ?, ?, 'idea', ?, 0.0, ?, ?)""",
            (prod_id, name, rv_stream.value, description, monthly_cost, now),
        )
        try:
            self.conn.commit()
        except Exception as exc:
            logger.error("Failed to commit add_product (%s): %s", name, exc)
        logger.info("Product added: %s [%s] — %s", name, rv_stream.value, prod_id)

        return RevenueProduct(
            id=prod_id, name=name, stream=rv_stream,
            status=StreamStatus.IDEA, description=description,
            monthly_cost=monthly_cost, created_at=now,
        )

    def update_status(self, product_id: str, status: str) -> bool:
        """Update product status."""
        new_status = StreamStatus(status)
        now = datetime.now(timezone.utc).isoformat()

        # Interest gate — check alignment before launching a product
        if new_status == StreamStatus.LAUNCHED and self._interest_engine:
            row = self.conn.execute(
                "SELECT name, description, stream FROM revenue_products WHERE id = ?",
                (product_id,),
            ).fetchone()
            if row:
                allowed, reason = self._interest_engine.gate(
                    subject=row["name"],
                    context=f"Launching product in {row['stream']} stream. {row['description']}",
                )
                if not allowed:
                    logger.info("Product launch blocked by interest gate: %s — %s", row["name"], reason)
                    return False

        if new_status == StreamStatus.LAUNCHED:
            cursor = self.conn.execute(
                "UPDATE revenue_products SET status = ?, launched_at = ? WHERE id = ?",
                (new_status.value, now, product_id),
            )
        else:
            cursor = self.conn.execute(
                "UPDATE revenue_products SET status = ? WHERE id = ?",
                (new_status.value, product_id),
            )
        try:
            self.conn.commit()
        except Exception as exc:
            logger.error("Failed to commit update_status (%s): %s", product_id, exc)
            return False
        return cursor.rowcount > 0

    def record_revenue(self, product_id: str, amount: float,
                        description: str = "") -> None:
        """Record a revenue transaction."""
        if self._sandbox_gate is not None:
            decision = self._sandbox_gate.check(
                system_id="revenue", action="record_revenue",
                description=f"Record ${amount:.2f} revenue for {product_id}",
                agent_id="revenue_engine", risk_level="medium",
            )
            if not decision.was_executed:
                logger.info("Sandbox blocked record_revenue for %s", product_id)
                return
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO revenue_transactions
               (id, product_id, amount, transaction_type, description, created_at)
               VALUES (?, ?, ?, 'revenue', ?, ?)""",
            (tx_id, product_id, amount, description, now),
        )
        self.conn.execute(
            "UPDATE revenue_products SET monthly_revenue = monthly_revenue + ? WHERE id = ?",
            (amount, product_id),
        )
        try:
            self.conn.commit()
        except Exception as exc:
            logger.error("Failed to commit record_revenue (%s, $%.2f): %s", product_id, amount, exc)
            return
        logger.info("Revenue recorded: $%.2f for %s", amount, product_id)

    def record_cost(self, product_id: str, amount: float,
                     description: str = "") -> None:
        """Record a cost transaction."""
        if self._sandbox_gate is not None:
            decision = self._sandbox_gate.check(
                system_id="revenue", action="record_cost",
                description=f"Record ${amount:.2f} cost for {product_id}",
                agent_id="revenue_engine", risk_level="medium",
            )
            if not decision.was_executed:
                logger.info("Sandbox blocked record_cost for %s", product_id)
                return
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO revenue_transactions
               (id, product_id, amount, transaction_type, description, created_at)
               VALUES (?, ?, ?, 'cost', ?, ?)""",
            (tx_id, product_id, abs(amount), description, now),
        )
        self.conn.execute(
            "UPDATE revenue_products SET monthly_cost = monthly_cost + ? WHERE id = ?",
            (abs(amount), product_id),
        )
        try:
            self.conn.commit()
        except Exception as exc:
            logger.error("Failed to commit record_cost (%s, $%.2f): %s", product_id, amount, exc)

    # ── Financial Overview ─────────────────────────────────────

    def get_financial_snapshot(self) -> FinancialSnapshot:
        """Get current financial state across all streams."""
        rows = self.conn.execute(
            """SELECT stream, SUM(monthly_revenue) as rev, SUM(monthly_cost) as cost
               FROM revenue_products WHERE status != 'paused'
               GROUP BY stream"""
        ).fetchall()

        by_stream: dict[str, float] = {}
        total_rev = 0.0
        total_cost = 0.0

        for row in rows:
            rev = row["rev"] or 0.0
            cost = row["cost"] or 0.0
            by_stream[row["stream"]] = rev - cost
            total_rev += rev
            total_cost += cost

        profit = total_rev - total_cost
        # Only trigger emergency mode when there are actual costs exceeding revenue.
        # A fresh install with $0 revenue and $0 cost is not an emergency — it's
        # just a system that hasn't started earning yet.  Require at least some
        # cost activity before declaring an emergency to avoid false positives.
        has_meaningful_activity = total_cost > 0 or total_rev > 0
        emergency = (
            has_meaningful_activity
            and total_rev < total_cost
            and profit < SURVIVAL_BUDGET
        )

        return FinancialSnapshot(
            total_revenue=total_rev,
            total_cost=total_cost,
            profit=profit,
            by_stream=by_stream,
            emergency_mode=emergency,
        )

    def get_products(self, stream: Optional[str] = None,
                      status: Optional[str] = None,
                      limit: int = 50) -> list[RevenueProduct]:
        """Get products with optional filters."""
        sql = "SELECT * FROM revenue_products WHERE 1=1"
        params: list[Any] = []

        if stream:
            sql += " AND stream = ?"
            params.append(stream)
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY monthly_revenue DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_product(r) for r in rows]

    def check_emergency_mode(self) -> bool:
        """Check if emergency mode should be activated."""
        snapshot = self.get_financial_snapshot()
        if snapshot.emergency_mode:
            logger.warning(
                "EMERGENCY MODE: Revenue ($%.0f) < Cost ($%.0f), profit: $%.0f",
                snapshot.total_revenue, snapshot.total_cost, snapshot.profit,
            )
        return snapshot.emergency_mode

    def auto_remediate(self) -> dict[str, Any]:
        """Automatically remediate financial emergencies.

        Actions taken:
        1. Pause all products with negative profit margin
        2. Identify top revenue generators for doubling down
        3. Flag products close to profitability for optimization
        Returns a summary of actions taken.
        """
        snapshot = self.get_financial_snapshot()
        actions: dict[str, Any] = {
            "emergency": snapshot.emergency_mode,
            "paused": [],
            "top_earners": [],
            "near_profitable": [],
        }

        if not snapshot.emergency_mode:
            return actions

        if self._sandbox_gate is not None:
            decision = self._sandbox_gate.check(
                system_id="revenue", action="auto_remediate",
                description="Emergency auto-remediation: pausing unprofitable products",
                agent_id="revenue_engine", risk_level="high",
            )
            if not decision.was_executed:
                logger.info("Sandbox blocked auto_remediate")
                actions["sandboxed"] = True
                return actions

        products = self.get_products(limit=100)

        for product in products:
            if product.status.value in ("paused", "idea"):
                continue

            profit = product.monthly_revenue - product.monthly_cost

            # Pause products losing money
            if profit < -20:
                self.update_status(product.id, "paused")
                actions["paused"].append({
                    "id": product.id, "name": product.name,
                    "profit": round(profit, 2),
                })
                logger.info(
                    "Auto-remediation: paused %s (profit: $%.0f)",
                    product.name, profit,
                )

            # Track top earners
            elif profit > 100:
                actions["top_earners"].append({
                    "id": product.id, "name": product.name,
                    "profit": round(profit, 2),
                })

            # Track near-profitable for optimization
            elif -20 <= profit <= 0 and product.monthly_revenue > 0:
                actions["near_profitable"].append({
                    "id": product.id, "name": product.name,
                    "gap": round(abs(profit), 2),
                })

        logger.info(
            "Auto-remediation: paused %d products, %d top earners, %d near-profitable",
            len(actions["paused"]), len(actions["top_earners"]),
            len(actions["near_profitable"]),
        )
        return actions

    def stats(self) -> dict[str, Any]:
        """Revenue engine statistics."""
        snapshot = self.get_financial_snapshot()
        product_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM revenue_products"
        ).fetchone()
        stream_counts = self.conn.execute(
            "SELECT stream, COUNT(*) as cnt, SUM(monthly_revenue) as rev FROM revenue_products GROUP BY stream"
        ).fetchall()

        return {
            "total_products": product_count["c"] if product_count else 0,
            "total_revenue": snapshot.total_revenue,
            "total_cost": snapshot.total_cost,
            "profit": snapshot.profit,
            "emergency_mode": snapshot.emergency_mode,
            "survival_budget": SURVIVAL_BUDGET,
            "streams": {
                r["stream"]: {"products": r["cnt"], "revenue": r["rev"] or 0}
                for r in stream_counts
            },
            "targets": {
                s.value: {"min": t[0], "max": t[1]}
                for s, t in STREAM_TARGETS.items()
            },
        }

    @staticmethod
    def _row_to_product(row: sqlite3.Row) -> RevenueProduct:
        import json
        try:
            metrics = json.loads(row["metrics"]) if row["metrics"] else {}
        except json.JSONDecodeError:
            metrics = {}
        return RevenueProduct(
            id=row["id"], name=row["name"],
            stream=RevenueStream(row["stream"]),
            status=StreamStatus(row["status"]),
            description=row["description"] or "",
            monthly_revenue=row["monthly_revenue"] or 0.0,
            monthly_cost=row["monthly_cost"] or 0.0,
            created_at=row["created_at"],
            launched_at=row["launched_at"],
            metrics=metrics,
        )
