"""Extended tests for Prediction Ledger — calibration, edge cases, source breakdowns."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.prediction_ledger import PredictionLedger


@pytest.fixture
def ledger(tmp_path):
    with patch("backend.core.prediction_ledger.PREDICTION_DB", tmp_path / "predictions.db"):
        engine = PredictionLedger()
        engine.start()
        yield engine
        engine.stop()


# ── Valid Prediction Sources ──────────────────────────────────────────


class TestValidSources:
    def test_miro_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="Bullish breakout",
        )
        assert pid.startswith("pred_")

    def test_swarm_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="swarm", symbol="TSLA", direction="short",
            confidence=0.65, reasoning="Overvalued",
        )
        assert pid.startswith("pred_")

    def test_directive_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="directive", symbol="NVDA", direction="long",
            confidence=0.9, reasoning="AI tailwind",
        )
        assert pid.startswith("pred_")


# ── Confidence Validation ─────────────────────────────────────────────


class TestConfidenceValidation:
    def test_zero_confidence_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.0, reasoning="Very uncertain",
        )
        assert pid.startswith("pred_")

    def test_one_confidence_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=1.0, reasoning="Certain",
        )
        assert pid.startswith("pred_")

    def test_above_one_invalid(self, ledger: PredictionLedger):
        with pytest.raises(ValueError, match="Confidence must be"):
            ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=1.1, reasoning="test",
            )

    def test_negative_invalid(self, ledger: PredictionLedger):
        with pytest.raises(ValueError, match="Confidence must be"):
            ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=-0.1, reasoning="test",
            )


# ── Direction Validation ──────────────────────────────────────────────


class TestDirectionValidation:
    def test_long_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.7, reasoning="test",
        )
        assert pid

    def test_short_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="short",
            confidence=0.7, reasoning="test",
        )
        assert pid

    def test_hold_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="hold",
            confidence=0.5, reasoning="unclear sideways market",
        )
        assert pid


# ── Resolution ────────────────────────────────────────────────────────


class TestResolutionDetails:
    def test_hit_counted_correctly(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.8, reasoning="test",
        )
        is_hit = ledger.resolve_prediction(pid, actual_direction="long", actual_price=180.0)
        assert is_hit is True

    def test_miss_counted_correctly(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="swarm", symbol="BTC", direction="long",
            confidence=0.75, reasoning="test",
        )
        is_hit = ledger.resolve_prediction(pid, actual_direction="short", actual_price=30000.0)
        assert is_hit is False

    def test_neutral_resolved_correctly(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="directive", symbol="ETH", direction="neutral",
            confidence=0.5, reasoning="unclear market",
        )
        is_hit = ledger.resolve_prediction(pid, actual_direction="neutral", actual_price=2000.0)
        assert is_hit is True

    def test_resolve_updates_pending_count(self, ledger: PredictionLedger):
        pid1 = ledger.record_prediction(
            source="miro", symbol="A", direction="long", confidence=0.8, reasoning="test",
        )
        ledger.record_prediction(
            source="miro", symbol="B", direction="short", confidence=0.7, reasoning="test",
        )
        ledger.resolve_prediction(pid1, "long", 100.0)
        stats = ledger.stats()
        assert stats["pending"] == 1
        assert stats["resolved"] == 1


# ── Calibration Buckets ───────────────────────────────────────────────


class TestCalibrationBuckets:
    def test_confidence_bucket_rounding(self, ledger: PredictionLedger):
        """0.55 should round to 0.6 bucket."""
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="long",
            confidence=0.55, reasoning="test",
        )
        ledger.resolve_prediction(pid, "long", 180.0)
        cal = ledger.get_calibration(source="miro")
        assert len(cal) == 1
        assert cal[0].confidence_bucket in (0.5, 0.6)

    def test_multiple_buckets(self, ledger: PredictionLedger):
        """Different confidence levels should go into different buckets."""
        for conf in (0.3, 0.7, 0.9):
            pid = ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=conf, reasoning="test",
            )
            ledger.resolve_prediction(pid, "long", 180.0)
        cal = ledger.get_calibration(source="miro")
        assert len(cal) >= 2  # At least 2 distinct buckets

    def test_calibration_score_range(self, ledger: PredictionLedger):
        """Calibration score should always be between 0 and 1."""
        for i in range(5):
            pid = ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=0.8, reasoning=f"test {i}",
            )
            actual = "long" if i % 2 == 0 else "short"
            ledger.resolve_prediction(pid, actual, 180.0)
        cal = ledger.get_calibration(source="miro")
        for bucket in cal:
            assert 0.0 <= bucket.calibration_score <= 1.0


# ── Accuracy Per Source ───────────────────────────────────────────────


class TestAccuracyPerSource:
    def test_perfect_accuracy(self, ledger: PredictionLedger):
        for i in range(4):
            pid = ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=0.8, reasoning=f"test {i}",
            )
            ledger.resolve_prediction(pid, "long", 180.0)
        assert ledger.get_accuracy("miro") == pytest.approx(1.0, abs=0.01)

    def test_zero_accuracy(self, ledger: PredictionLedger):
        for i in range(3):
            pid = ledger.record_prediction(
                source="swarm", symbol="TSLA", direction="long",
                confidence=0.7, reasoning=f"test {i}",
            )
            ledger.resolve_prediction(pid, "short", 250.0)
        assert ledger.get_accuracy("swarm") == pytest.approx(0.0, abs=0.01)

    def test_partial_accuracy(self, ledger: PredictionLedger):
        # 2 hits, 2 misses
        for i in range(4):
            pid = ledger.record_prediction(
                source="directive", symbol="NVDA", direction="long",
                confidence=0.85, reasoning=f"test {i}",
            )
            actual = "long" if i < 2 else "short"
            ledger.resolve_prediction(pid, actual, 900.0)
        assert ledger.get_accuracy("directive") == pytest.approx(0.5, abs=0.01)


# ── Stats By Source ───────────────────────────────────────────────────


class TestStatsBySource:
    def test_multiple_sources_tracked(self, ledger: PredictionLedger):
        for source in ("miro", "swarm", "directive"):
            pid = ledger.record_prediction(
                source=source, symbol="AAPL", direction="long",
                confidence=0.8, reasoning="test",
            )
            ledger.resolve_prediction(pid, "long", 180.0)
        stats = ledger.stats()
        assert "miro" in stats["by_source"]
        assert "swarm" in stats["by_source"]
        assert "directive" in stats["by_source"]

    def test_source_hit_rate_in_stats(self, ledger: PredictionLedger):
        for i in range(3):
            pid = ledger.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=0.8, reasoning=f"test {i}",
            )
            actual = "long" if i < 2 else "short"
            ledger.resolve_prediction(pid, actual, 180.0)
        stats = ledger.stats()
        miro_stats = stats["by_source"]["miro"]
        assert miro_stats["hit_rate"] == pytest.approx(2 / 3, abs=0.01)


# ── Persistence ───────────────────────────────────────────────────────


class TestPersistence:
    def test_predictions_persist_across_restart(self, tmp_path):
        db_path = tmp_path / "predictions.db"
        with patch("backend.core.prediction_ledger.PREDICTION_DB", db_path):
            l1 = PredictionLedger()
            l1.start()
            pid = l1.record_prediction(
                source="miro", symbol="AAPL", direction="long",
                confidence=0.8, reasoning="Persisted",
            )
            l1.stop()

        with patch("backend.core.prediction_ledger.PREDICTION_DB", db_path):
            l2 = PredictionLedger()
            l2.start()
            pending = l2.get_pending()
            assert any(p.id == pid for p in pending)
            l2.stop()
