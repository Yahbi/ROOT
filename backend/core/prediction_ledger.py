"""
Prediction Ledger — Tracks predictions from MiRo, Swarm, and Directive Engine.

The missing feedback loop: predictions are recorded with confidence and deadline,
then resolved against actual market outcomes. Calibration tables track how well
each source's confidence maps to reality, enabling ROOT to learn which signals
to trust.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.prediction_ledger")

PREDICTION_DB = ROOT_DIR / "data" / "predictions.db"

VALID_DIRECTIONS = frozenset({"long", "short", "hold"})
VALID_SOURCES = frozenset({"miro", "swarm", "directive", "manual"})
CONFIDENCE_BUCKETS = (0.5, 0.6, 0.7, 0.8, 0.9)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bucket_for(confidence: float) -> float:
    """Map a confidence score to the nearest calibration bucket."""
    return min(CONFIDENCE_BUCKETS, key=lambda b: abs(b - confidence))


@dataclass(frozen=True)
class Prediction:
    """Immutable prediction record."""

    id: str
    source: str
    symbol: str
    direction: str
    confidence: float
    target_price: Optional[float]
    deadline: str
    reasoning: str
    actual_direction: Optional[str]
    actual_price: Optional[float]
    resolved_at: Optional[str]
    hit: Optional[int]
    created_at: str


@dataclass(frozen=True)
class CalibrationBucket:
    """Immutable calibration record for a source + confidence bucket."""

    source: str
    confidence_bucket: float
    total_predictions: int
    correct_predictions: int
    calibration_score: float
    updated_at: str


class PredictionLedger:
    """Records predictions and resolves them against actuals.

    Maintains per-source calibration tables so ROOT can learn which
    prediction sources to trust at which confidence levels.
    """

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        """Initialize the prediction ledger database."""
        PREDICTION_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(PREDICTION_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        logger.info("PredictionLedger started (db=%s)", PREDICTION_DB)

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("PredictionLedger not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                confidence REAL NOT NULL,
                target_price REAL,
                deadline TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                actual_direction TEXT,
                actual_price REAL,
                resolved_at TEXT,
                hit INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS calibration (
                source TEXT NOT NULL,
                confidence_bucket REAL NOT NULL,
                total_predictions INTEGER NOT NULL DEFAULT 0,
                correct_predictions INTEGER NOT NULL DEFAULT 0,
                calibration_score REAL NOT NULL DEFAULT 0.0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source, confidence_bucket)
            );

            CREATE INDEX IF NOT EXISTS idx_predictions_source
                ON predictions(source);
            CREATE INDEX IF NOT EXISTS idx_predictions_deadline
                ON predictions(deadline);
            CREATE INDEX IF NOT EXISTS idx_predictions_resolved
                ON predictions(resolved_at);
        """)

    # ── Recording ──────────────────────────────────────────────

    def record_prediction(
        self,
        source: str,
        symbol: str,
        direction: str,
        confidence: float,
        reasoning: str,
        deadline_hours: int = 24,
        target_price: Optional[float] = None,
    ) -> str:
        """Store a new prediction. Returns prediction ID."""
        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source: {source}. Must be one of {VALID_SOURCES}")
        if direction not in VALID_DIRECTIONS:
            raise ValueError(f"Invalid direction: {direction}. Must be one of {VALID_DIRECTIONS}")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {confidence}")

        prediction_id = f"pred_{uuid.uuid4().hex[:12]}"
        deadline = (datetime.now(timezone.utc) + timedelta(hours=deadline_hours)).isoformat()

        self.conn.execute(
            """INSERT INTO predictions
               (id, source, symbol, direction, confidence, target_price,
                deadline, reasoning, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                prediction_id,
                source,
                symbol.upper(),
                direction,
                confidence,
                target_price,
                deadline,
                reasoning[:1000],
                _now_iso(),
            ),
        )
        self.conn.commit()
        logger.info(
            "Recorded prediction %s: %s %s %s (conf=%.2f)",
            prediction_id, source, symbol, direction, confidence,
        )
        return prediction_id

    # ── Resolution ─────────────────────────────────────────────

    def resolve_prediction(
        self,
        prediction_id: str,
        actual_direction: str,
        actual_price: float,
    ) -> bool:
        """Resolve a prediction as hit or miss. Returns whether it was a hit."""
        row = self.conn.execute(
            "SELECT * FROM predictions WHERE id = ?", (prediction_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Prediction not found: {prediction_id}")
        if row["resolved_at"] is not None:
            raise ValueError(f"Prediction already resolved: {prediction_id}")

        hit = 1 if actual_direction == row["direction"] else 0
        now = _now_iso()

        self.conn.execute(
            """UPDATE predictions
               SET actual_direction = ?, actual_price = ?, resolved_at = ?, hit = ?
               WHERE id = ?""",
            (actual_direction, actual_price, now, hit, prediction_id),
        )
        self.conn.commit()

        self._update_calibration(row["source"], row["confidence"], hit)

        logger.info(
            "Resolved %s: %s (predicted=%s, actual=%s)",
            prediction_id, "HIT" if hit else "MISS", row["direction"], actual_direction,
        )
        return bool(hit)

    def auto_resolve_expired(self, plugins: Optional[dict[str, Any]] = None) -> int:
        """Resolve predictions past their deadline. Returns count resolved."""
        now = _now_iso()
        expired = self.conn.execute(
            "SELECT * FROM predictions WHERE resolved_at IS NULL AND deadline < ?",
            (now,),
        ).fetchall()

        resolved_count = 0
        for pred in expired:
            price = self._fetch_price(pred["symbol"], plugins)
            if price is not None:
                # Determine actual direction from price vs target
                actual_dir = self._infer_direction(pred, price)
                self.resolve_prediction(pred["id"], actual_dir, price)
                resolved_count += 1
            else:
                # Mark as expired unresolved
                self.conn.execute(
                    """UPDATE predictions
                       SET actual_direction = 'expired_unresolved', resolved_at = ?
                       WHERE id = ?""",
                    (now, pred["id"]),
                )
                self.conn.commit()
                resolved_count += 1

        return resolved_count

    @staticmethod
    def _fetch_price(symbol: str, plugins: Optional[dict[str, Any]]) -> Optional[float]:
        """Attempt to fetch current price via Alpaca plugin."""
        if not plugins:
            return None
        alpaca = plugins.get("alpaca_market_data")
        if not alpaca or not hasattr(alpaca, "get_latest_price"):
            return None
        try:
            return alpaca.get_latest_price(symbol)
        except Exception:
            logger.warning("Failed to fetch price for %s", symbol)
            return None

    @staticmethod
    def _infer_direction(pred: sqlite3.Row, current_price: float) -> str:
        """Infer actual direction from price movement."""
        target = pred["target_price"]
        if target is None:
            return "hold"
        if current_price > target:
            return "long"
        if current_price < target:
            return "short"
        return "hold"

    # ── Calibration ────────────────────────────────────────────

    def _update_calibration(self, source: str, confidence: float, hit: int) -> None:
        """Update calibration table for the source and confidence bucket."""
        bucket = _bucket_for(confidence)
        now = _now_iso()

        row = self.conn.execute(
            "SELECT * FROM calibration WHERE source = ? AND confidence_bucket = ?",
            (source, bucket),
        ).fetchone()

        if row:
            total = row["total_predictions"] + 1
            correct = row["correct_predictions"] + hit
            score = correct / total if total > 0 else 0.0
            self.conn.execute(
                """UPDATE calibration
                   SET total_predictions = ?, correct_predictions = ?,
                       calibration_score = ?, updated_at = ?
                   WHERE source = ? AND confidence_bucket = ?""",
                (total, correct, score, now, source, bucket),
            )
        else:
            score = float(hit)
            self.conn.execute(
                """INSERT INTO calibration
                   (source, confidence_bucket, total_predictions, correct_predictions,
                    calibration_score, updated_at)
                   VALUES (?, ?, 1, ?, ?, ?)""",
                (source, bucket, hit, score, now),
            )
        self.conn.commit()

    def get_calibration(self, source: Optional[str] = None) -> list[CalibrationBucket]:
        """Return calibration stats, optionally filtered by source."""
        if source:
            rows = self.conn.execute(
                "SELECT * FROM calibration WHERE source = ? ORDER BY confidence_bucket",
                (source,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM calibration ORDER BY source, confidence_bucket",
            ).fetchall()

        return [
            CalibrationBucket(
                source=r["source"],
                confidence_bucket=r["confidence_bucket"],
                total_predictions=r["total_predictions"],
                correct_predictions=r["correct_predictions"],
                calibration_score=r["calibration_score"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    # ── Queries ────────────────────────────────────────────────

    def get_accuracy(self, source: str, lookback_days: int = 30) -> float:
        """Return hit rate for a source over the lookback period."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        row = self.conn.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits
               FROM predictions
               WHERE source = ? AND resolved_at IS NOT NULL
                     AND hit IS NOT NULL AND created_at >= ?""",
            (source, cutoff),
        ).fetchone()

        if not row or row["total"] == 0:
            return 0.0
        return round((row["hits"] or 0) / row["total"], 4)

    def get_pending(self) -> list[Prediction]:
        """Return predictions awaiting resolution."""
        rows = self.conn.execute(
            "SELECT * FROM predictions WHERE resolved_at IS NULL ORDER BY deadline ASC",
        ).fetchall()
        return [self._row_to_prediction(r) for r in rows]

    def get_history(
        self, source: Optional[str] = None, limit: int = 50,
    ) -> list[Prediction]:
        """Return recent predictions with outcomes."""
        if source:
            rows = self.conn.execute(
                """SELECT * FROM predictions WHERE source = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (source, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM predictions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_prediction(r) for r in rows]

    @staticmethod
    def _row_to_prediction(row: sqlite3.Row) -> Prediction:
        return Prediction(
            id=row["id"],
            source=row["source"],
            symbol=row["symbol"],
            direction=row["direction"],
            confidence=row["confidence"],
            target_price=row["target_price"],
            deadline=row["deadline"],
            reasoning=row["reasoning"],
            actual_direction=row["actual_direction"],
            actual_price=row["actual_price"],
            resolved_at=row["resolved_at"],
            hit=row["hit"],
            created_at=row["created_at"],
        )

    # ── Stats ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Summary statistics for the prediction ledger."""
        total = self.conn.execute("SELECT COUNT(*) as c FROM predictions").fetchone()
        pending = self.conn.execute(
            "SELECT COUNT(*) as c FROM predictions WHERE resolved_at IS NULL",
        ).fetchone()
        hits = self.conn.execute(
            "SELECT COUNT(*) as c FROM predictions WHERE hit = 1",
        ).fetchone()
        misses = self.conn.execute(
            "SELECT COUNT(*) as c FROM predictions WHERE hit = 0",
        ).fetchone()

        total_count = total["c"] if total else 0
        resolved_count = (hits["c"] if hits else 0) + (misses["c"] if misses else 0)
        hit_rate = round(hits["c"] / resolved_count, 4) if resolved_count > 0 else 0.0

        # Per-source breakdown
        source_rows = self.conn.execute(
            """SELECT source, COUNT(*) as total,
                      SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
                      SUM(CASE WHEN hit = 0 THEN 1 ELSE 0 END) as misses
               FROM predictions WHERE hit IS NOT NULL
               GROUP BY source""",
        ).fetchall()

        by_source = {
            r["source"]: {
                "total": r["total"],
                "hits": r["hits"] or 0,
                "misses": r["misses"] or 0,
                "hit_rate": round((r["hits"] or 0) / r["total"], 4) if r["total"] > 0 else 0.0,
            }
            for r in source_rows
        }

        return {
            "total_predictions": total_count,
            "pending": pending["c"] if pending else 0,
            "resolved": resolved_count,
            "hits": hits["c"] if hits else 0,
            "misses": misses["c"] if misses else 0,
            "hit_rate": hit_rate,
            "by_source": by_source,
        }
