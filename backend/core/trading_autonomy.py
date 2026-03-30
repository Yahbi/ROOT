"""
Trading Autonomy — graduated trust system for trading decisions.

Three tiers based on portfolio risk and calibrated confidence:
1. AUTO_APPROVE: Low-risk trades execute without human intervention
2. NOTIFY_PROCEED: Medium-risk trades execute and notify Yohan
3. MANUAL_APPROVE: High-risk trades wait for Yohan's explicit approval

Confidence scores are calibrated against the prediction ledger's
historical accuracy so ROOT doesn't blindly trust overconfident signals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("root.trading_autonomy")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Enums & Data ──────────────────────────────────────────────


class TradeRiskLevel(str, Enum):
    AUTO_APPROVE = "auto_approve"
    NOTIFY_PROCEED = "notify_proceed"
    MANUAL_APPROVE = "manual_approve"


@dataclass(frozen=True)
class TradeDecision:
    """Immutable record of a classified trade decision."""

    symbol: str
    risk_level: TradeRiskLevel
    calibrated_confidence: float
    raw_confidence: float
    dollar_amount: float
    portfolio_pct: float
    reasoning: str


# ── Default thresholds ────────────────────────────────────────

_DEFAULT_THRESHOLDS = {
    "auto_approve_pct": 0.01,          # < 1% portfolio
    "auto_approve_dollar": 100.0,      # < $100
    "auto_approve_confidence": 0.80,   # confidence > 0.8
    "notify_pct_low": 0.01,            # 1% portfolio
    "notify_pct_high": 0.03,           # 3% portfolio
    "notify_dollar_low": 100.0,        # $100
    "notify_dollar_high": 500.0,       # $500
    "notify_confidence": 0.65,         # confidence > 0.65
}


# ── Main class ────────────────────────────────────────────────


class TradingAutonomy:
    """Graduated trust system for autonomous trading decisions.

    Reads thresholds from adaptive_config if available, falling back
    to sane defaults.  Calibrates raw confidence scores against the
    prediction ledger's historical accuracy per source.
    """

    def __init__(
        self,
        adaptive_config=None,
        prediction_ledger=None,
    ) -> None:
        self._adaptive_config = adaptive_config
        self._prediction_ledger = prediction_ledger
        self._decisions: list[TradeDecision] = []
        self._counts = {
            TradeRiskLevel.AUTO_APPROVE: 0,
            TradeRiskLevel.NOTIFY_PROCEED: 0,
            TradeRiskLevel.MANUAL_APPROVE: 0,
        }
        logger.info("TradingAutonomy initialised")

    # ── Helpers ───────────────────────────────────────────────

    def _threshold(self, key: str) -> float:
        """Read threshold from adaptive_config, fall back to default."""
        default = _DEFAULT_THRESHOLDS[key]
        if self._adaptive_config is None:
            return default
        try:
            return float(self._adaptive_config.get(f"trading_autonomy_{key}", default))
        except (TypeError, ValueError):
            return default

    # ── Public API ────────────────────────────────────────────

    def classify_trade_risk(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        dollar_amount: float,
        portfolio_value: float,
    ) -> TradeRiskLevel:
        """Classify a trade into a risk tier.

        Returns:
            TradeRiskLevel indicating required approval level.
        """
        if portfolio_value <= 0:
            logger.warning("Portfolio value <= 0; forcing MANUAL_APPROVE for %s", symbol)
            return TradeRiskLevel.MANUAL_APPROVE

        pct = dollar_amount / portfolio_value

        auto_pct = self._threshold("auto_approve_pct")
        auto_dollar = self._threshold("auto_approve_dollar")
        auto_conf = self._threshold("auto_approve_confidence")

        notify_pct_high = self._threshold("notify_pct_high")
        notify_dollar_high = self._threshold("notify_dollar_high")
        notify_conf = self._threshold("notify_confidence")

        # ── MANUAL_APPROVE: large position, high dollar, or low confidence ──
        if pct > notify_pct_high or dollar_amount > notify_dollar_high or confidence < notify_conf:
            level = TradeRiskLevel.MANUAL_APPROVE
        # ── AUTO_APPROVE: small position AND small dollar AND high confidence ──
        elif pct < auto_pct and dollar_amount < auto_dollar and confidence > auto_conf:
            level = TradeRiskLevel.AUTO_APPROVE
        # ── NOTIFY_PROCEED: everything in between ──
        else:
            level = TradeRiskLevel.NOTIFY_PROCEED

        self._counts[level] += 1
        logger.info(
            "Trade classified: %s %s $%.2f (%.1f%% portfolio, conf=%.2f) → %s",
            direction, symbol, dollar_amount, pct * 100, confidence, level.value,
        )
        return level

    def get_calibrated_confidence(self, raw_confidence: float, source: str) -> float:
        """Adjust confidence based on prediction ledger calibration for *source*.

        If no calibration data is available, returns the raw confidence
        clamped to [0, 1].
        """
        clamped = max(0.0, min(1.0, raw_confidence))

        if self._prediction_ledger is None:
            return clamped

        try:
            buckets = self._prediction_ledger.get_calibration(source=source)
        except Exception:
            logger.debug("Could not fetch calibration for source=%s", source)
            return clamped

        if not buckets:
            return clamped

        # Find the closest calibration bucket and adjust.
        # calibration_score is the historical hit rate at that confidence level.
        closest = min(buckets, key=lambda b: abs(b.confidence_bucket - clamped))

        if closest.total_predictions < 5:
            # Not enough data — blend toward raw confidence.
            return clamped

        # Weighted blend: 60% calibration, 40% raw (so ledger evidence dominates).
        calibrated = 0.6 * closest.calibration_score + 0.4 * clamped
        calibrated = max(0.0, min(1.0, calibrated))

        logger.debug(
            "Calibrated confidence for %s: raw=%.3f → calibrated=%.3f "
            "(bucket=%.1f, hit_rate=%.3f, n=%d)",
            source, raw_confidence, calibrated,
            closest.confidence_bucket, closest.calibration_score,
            closest.total_predictions,
        )
        return calibrated

    def make_decision(
        self,
        symbol: str,
        direction: str,
        raw_confidence: float,
        source: str,
        dollar_amount: float,
        portfolio_value: float,
        reasoning: str = "",
    ) -> TradeDecision:
        """Full pipeline: calibrate confidence, classify risk, return decision."""
        calibrated = self.get_calibrated_confidence(raw_confidence, source)
        risk_level = self.classify_trade_risk(
            symbol, direction, calibrated, dollar_amount, portfolio_value,
        )
        pct = dollar_amount / portfolio_value if portfolio_value > 0 else 1.0

        decision = TradeDecision(
            symbol=symbol,
            risk_level=risk_level,
            calibrated_confidence=calibrated,
            raw_confidence=raw_confidence,
            dollar_amount=dollar_amount,
            portfolio_pct=pct,
            reasoning=reasoning,
        )
        self._decisions.append(decision)
        return decision

    def stats(self) -> dict[str, Any]:
        """Return runtime statistics."""
        return {
            "total_decisions": len(self._decisions),
            "auto_approve_count": self._counts[TradeRiskLevel.AUTO_APPROVE],
            "notify_proceed_count": self._counts[TradeRiskLevel.NOTIFY_PROCEED],
            "manual_approve_count": self._counts[TradeRiskLevel.MANUAL_APPROVE],
            "has_adaptive_config": self._adaptive_config is not None,
            "has_prediction_ledger": self._prediction_ledger is not None,
        }
