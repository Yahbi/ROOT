"""Tests for the Prediction Ledger — prediction tracking and calibration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.prediction_ledger import PredictionLedger


@pytest.fixture
def ledger(tmp_path):
    """Provide a started PredictionLedger with a temp database."""
    with patch("backend.core.prediction_ledger.PREDICTION_DB", tmp_path / "predictions.db"):
        engine = PredictionLedger()
        engine.start()
        yield engine
        engine.stop()


class TestRecordPrediction:
    def test_record_returns_id(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="Bullish technicals",
        )
        assert pid.startswith("pred_")

    def test_record_increments_stats(self, ledger: PredictionLedger):
        ledger.record_prediction(
            source="swarm", symbol="TSLA", direction="short",
            confidence=0.7, reasoning="Overvalued",
        )
        stats = ledger.stats()
        assert stats["total_predictions"] == 1
        assert stats["pending"] == 1

    def test_record_with_target_price(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="directive", symbol="NVDA", direction="long",
            confidence=0.9, reasoning="AI boom", target_price=950.0,
        )
        history = ledger.get_history()
        match = [p for p in history if p.id == pid]
        assert len(match) == 1
        assert match[0].target_price == 950.0

    def test_invalid_source_raises(self, ledger: PredictionLedger):
        with pytest.raises(ValueError, match="Invalid source"):
            ledger.record_prediction(
                source="unknown", symbol="AAPL", direction="long",
                confidence=0.5, reasoning="test",
            )

    def test_invalid_direction_raises(self, ledger: PredictionLedger):
        with pytest.raises(ValueError, match="Invalid direction"):
            ledger.record_prediction(
                source="miro", symbol="AAPL", direction="up",
                confidence=0.5, reasoning="test",
            )

    def test_invalid_confidence_raises(self, ledger: PredictionLedger):
        with pytest.raises(ValueError, match="Confidence must be"):
            ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=1.5, reasoning="test",
            )


class TestResolvePrediction:
    def test_resolve_hit(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="Bullish",
        )
        result = ledger.resolve_prediction(pid, actual_direction="long", actual_price=180.0)
        assert result is True

    def test_resolve_miss(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="swarm", symbol="TSLA", direction="short",
            confidence=0.7, reasoning="Bearish",
        )
        result = ledger.resolve_prediction(pid, actual_direction="long", actual_price=250.0)
        assert result is False

    def test_resolve_updates_stats(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="Bullish",
        )
        ledger.resolve_prediction(pid, actual_direction="long", actual_price=180.0)
        stats = ledger.stats()
        assert stats["resolved"] == 1
        assert stats["hits"] == 1
        assert stats["pending"] == 0

    def test_resolve_nonexistent_raises(self, ledger: PredictionLedger):
        with pytest.raises(ValueError, match="not found"):
            ledger.resolve_prediction("pred_nonexistent", "long", 100.0)

    def test_resolve_already_resolved_raises(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="test",
        )
        ledger.resolve_prediction(pid, "long", 180.0)
        with pytest.raises(ValueError, match="already resolved"):
            ledger.resolve_prediction(pid, "short", 170.0)


class TestCalibration:
    def test_calibration_after_hit(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.85, reasoning="test",
        )
        ledger.resolve_prediction(pid, "long", 180.0)
        cal = ledger.get_calibration(source="miro")
        assert len(cal) == 1
        assert cal[0].confidence_bucket == 0.8  # 0.85 is equidistant, rounds to 0.8
        assert cal[0].correct_predictions == 1
        assert cal[0].calibration_score == 1.0

    def test_calibration_after_miss(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="swarm", symbol="TSLA", direction="short",
            confidence=0.65, reasoning="test",
        )
        ledger.resolve_prediction(pid, "long", 250.0)
        cal = ledger.get_calibration(source="swarm")
        assert len(cal) == 1
        assert cal[0].confidence_bucket == 0.7  # 0.65 rounds to 0.7
        assert cal[0].correct_predictions == 0
        assert cal[0].calibration_score == 0.0

    def test_calibration_accumulates(self, ledger: PredictionLedger):
        # 2 hits, 1 miss at same bucket
        for direction in ("long", "long", "short"):
            pid = ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=0.75, reasoning="test",
            )
            ledger.resolve_prediction(pid, direction, 180.0)

        cal = ledger.get_calibration(source="miro")
        assert len(cal) == 1
        assert cal[0].total_predictions == 3
        assert cal[0].correct_predictions == 2
        assert abs(cal[0].calibration_score - 2 / 3) < 0.01

    def test_get_calibration_all_sources(self, ledger: PredictionLedger):
        for source in ("miro", "swarm"):
            pid = ledger.record_prediction(
                source=source, symbol="AAPL", direction="long",
                confidence=0.8, reasoning="test",
            )
            ledger.resolve_prediction(pid, "long", 180.0)
        cal = ledger.get_calibration()
        assert len(cal) == 2


class TestGetAccuracy:
    def test_accuracy_no_data(self, ledger: PredictionLedger):
        assert ledger.get_accuracy("miro") == 0.0

    def test_accuracy_with_hits_and_misses(self, ledger: PredictionLedger):
        # 3 hits, 1 miss
        for i in range(4):
            pid = ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=0.8, reasoning=f"test {i}",
            )
            actual = "long" if i < 3 else "short"
            ledger.resolve_prediction(pid, actual, 180.0)

        accuracy = ledger.get_accuracy("miro")
        assert accuracy == 0.75


class TestGetPendingAndHistory:
    def test_get_pending(self, ledger: PredictionLedger):
        ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="test",
        )
        pid2 = ledger.record_prediction(
            source="swarm", symbol="TSLA", direction="short",
            confidence=0.7, reasoning="test",
        )
        ledger.resolve_prediction(pid2, "short", 200.0)

        pending = ledger.get_pending()
        assert len(pending) == 1
        assert pending[0].source == "miro"

    def test_get_history_all(self, ledger: PredictionLedger):
        for i in range(3):
            ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=0.8, reasoning=f"test {i}",
            )
        history = ledger.get_history()
        assert len(history) == 3

    def test_get_history_filtered(self, ledger: PredictionLedger):
        ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="test",
        )
        ledger.record_prediction(
            source="swarm", symbol="TSLA", direction="short",
            confidence=0.7, reasoning="test",
        )
        history = ledger.get_history(source="swarm")
        assert len(history) == 1
        assert history[0].source == "swarm"

    def test_get_history_limit(self, ledger: PredictionLedger):
        for i in range(10):
            ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=0.8, reasoning=f"test {i}",
            )
        history = ledger.get_history(limit=3)
        assert len(history) == 3


class TestStats:
    def test_empty_stats(self, ledger: PredictionLedger):
        stats = ledger.stats()
        assert stats["total_predictions"] == 0
        assert stats["pending"] == 0
        assert stats["resolved"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["by_source"] == {}

    def test_stats_with_data(self, ledger: PredictionLedger):
        # 2 miro predictions: 1 hit, 1 miss
        pid1 = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="test",
        )
        pid2 = ledger.record_prediction(
            source="miro", symbol="TSLA", direction="short",
            confidence=0.6, reasoning="test",
        )
        ledger.record_prediction(
            source="swarm", symbol="NVDA", direction="long",
            confidence=0.9, reasoning="test (pending)",
        )
        ledger.resolve_prediction(pid1, "long", 180.0)
        ledger.resolve_prediction(pid2, "long", 250.0)

        stats = ledger.stats()
        assert stats["total_predictions"] == 3
        assert stats["pending"] == 1
        assert stats["resolved"] == 2
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert "miro" in stats["by_source"]
        assert stats["by_source"]["miro"]["hit_rate"] == 0.5
