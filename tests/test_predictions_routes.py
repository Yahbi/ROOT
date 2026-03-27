"""Tests for backend.routes.predictions — prediction ledger API."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.predictions import router


def _make_prediction(**overrides):
    """Create a mock prediction object with sensible defaults."""
    defaults = {
        "id": "pred-1",
        "source": "miro",
        "symbol": "AAPL",
        "direction": "long",
        "confidence": 0.85,
        "target_price": 200.0,
        "deadline": "2025-12-31",
        "hit": None,
        "resolved_at": None,
        "created_at": "2025-01-01T00:00:00",
        "reasoning": "Strong momentum",
        "actual_direction": None,
        "actual_price": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_calibration_bucket(**overrides):
    """Create a mock calibration bucket."""
    defaults = {
        "source": "miro",
        "confidence_bucket": "0.8-0.9",
        "total_predictions": 10,
        "correct_predictions": 8,
        "calibration_score": 0.8,
        "updated_at": "2025-01-01T00:00:00",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def mock_ledger():
    """Create a mock prediction ledger."""
    ledger = MagicMock()
    ledger.get_history.return_value = [
        _make_prediction(id="p-1"),
        _make_prediction(id="p-2", source="swarm", confidence=0.7),
    ]
    ledger.get_pending.return_value = [
        _make_prediction(id="p-1"),
    ]
    ledger.get_calibration.return_value = [
        _make_calibration_bucket(),
    ]
    ledger.stats.return_value = {
        "total_predictions": 50,
        "pending": 5,
        "resolved": 45,
        "accuracy": 0.78,
    }
    ledger.record_prediction.return_value = "new-pred-id"
    ledger.resolve_prediction.return_value = True
    return ledger


@pytest.fixture
def client(mock_ledger):
    """FastAPI test client with mocked prediction ledger."""
    app = FastAPI()
    app.include_router(router)
    app.state.prediction_ledger = mock_ledger
    return TestClient(app)


@pytest.fixture
def client_no_ledger():
    """FastAPI test client without prediction ledger (503 case)."""
    app = FastAPI()
    app.include_router(router)
    # Do not set app.state.prediction_ledger
    return TestClient(app)


class TestListPredictions:
    def test_list_all(self, client):
        resp = client.get("/api/predictions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["predictions"]) == 2

    def test_list_pending(self, client, mock_ledger):
        resp = client.get("/api/predictions?status=pending")
        assert resp.status_code == 200
        mock_ledger.get_pending.assert_called_once()

    def test_filter_by_source(self, client, mock_ledger):
        resp = client.get("/api/predictions?source=miro")
        assert resp.status_code == 200
        mock_ledger.get_history.assert_called_with(source="miro", limit=50)

    def test_limit_param(self, client, mock_ledger):
        resp = client.get("/api/predictions?limit=10")
        assert resp.status_code == 200
        mock_ledger.get_history.assert_called_with(source=None, limit=10)

    def test_no_ledger_returns_503(self, client_no_ledger):
        resp = client_no_ledger.get("/api/predictions")
        assert resp.status_code == 503


class TestCalibration:
    def test_calibration_scores(self, client):
        resp = client.get("/api/predictions/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["calibration"]) == 1
        assert data["calibration"][0]["source"] == "miro"

    def test_calibration_by_source(self, client, mock_ledger):
        resp = client.get("/api/predictions/calibration?source=swarm")
        assert resp.status_code == 200
        mock_ledger.get_calibration.assert_called_with(source="swarm")

    def test_calibration_no_ledger(self, client_no_ledger):
        resp = client_no_ledger.get("/api/predictions/calibration")
        assert resp.status_code == 503


class TestPredictionStats:
    def test_stats(self, client):
        resp = client.get("/api/predictions/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_predictions"] == 50

    def test_stats_no_ledger(self, client_no_ledger):
        resp = client_no_ledger.get("/api/predictions/stats")
        assert resp.status_code == 503


class TestGetSinglePrediction:
    def test_get_existing(self, client):
        resp = client.get("/api/predictions/p-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "p-1"
        assert data["source"] == "miro"

    def test_get_nonexistent(self, client, mock_ledger):
        mock_ledger.get_history.return_value = []
        resp = client.get("/api/predictions/nonexistent")
        assert resp.status_code == 404

    def test_get_no_ledger(self, client_no_ledger):
        resp = client_no_ledger.get("/api/predictions/some-id")
        assert resp.status_code == 503


class TestRecordPrediction:
    def test_record_valid(self, client, mock_ledger):
        resp = client.post(
            "/api/predictions",
            json={
                "source": "miro",
                "prediction": "AAPL will rise 10%",
                "confidence": 0.9,
                "category": "tech",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "new-pred-id"
        assert data["source"] == "miro"
        assert data["confidence"] == 0.9

    def test_record_with_deadline(self, client, mock_ledger):
        resp = client.post(
            "/api/predictions",
            json={
                "source": "swarm",
                "prediction": "BTC above 100k",
                "confidence": 0.75,
                "deadline": "48",
            },
        )
        assert resp.status_code == 200
        mock_ledger.record_prediction.assert_called_once()
        call_kwargs = mock_ledger.record_prediction.call_args
        assert call_kwargs.kwargs.get("deadline_hours") == 48 or call_kwargs[1].get("deadline_hours") == 48

    def test_record_invalid_confidence(self, client):
        resp = client.post(
            "/api/predictions",
            json={
                "source": "miro",
                "prediction": "test",
                "confidence": 1.5,  # > 1.0
            },
        )
        assert resp.status_code == 422

    def test_record_missing_fields(self, client):
        resp = client.post("/api/predictions", json={})
        assert resp.status_code == 422

    def test_record_value_error(self, client, mock_ledger):
        mock_ledger.record_prediction.side_effect = ValueError("Invalid input")
        resp = client.post(
            "/api/predictions",
            json={
                "source": "test",
                "prediction": "will fail",
                "confidence": 0.5,
            },
        )
        assert resp.status_code == 400

    def test_record_no_ledger(self, client_no_ledger):
        resp = client_no_ledger.post(
            "/api/predictions",
            json={
                "source": "test",
                "prediction": "anything",
                "confidence": 0.5,
            },
        )
        assert resp.status_code == 503


class TestResolvePrediction:
    def test_resolve_accurate(self, client, mock_ledger):
        resp = client.post(
            "/api/predictions/p-1/resolve",
            json={
                "actual_outcome": "AAPL rose 12%",
                "accurate": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prediction_id"] == "p-1"
        assert data["accurate"] is True
        assert data["hit"] is True

    def test_resolve_inaccurate(self, client, mock_ledger):
        mock_ledger.resolve_prediction.return_value = False
        resp = client.post(
            "/api/predictions/p-1/resolve",
            json={
                "actual_outcome": "AAPL dropped",
                "accurate": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["accurate"] is False

    def test_resolve_not_found(self, client, mock_ledger):
        mock_ledger.resolve_prediction.side_effect = ValueError("Not found")
        resp = client.post(
            "/api/predictions/bad-id/resolve",
            json={
                "actual_outcome": "whatever",
                "accurate": True,
            },
        )
        assert resp.status_code == 404

    def test_resolve_no_ledger(self, client_no_ledger):
        resp = client_no_ledger.post(
            "/api/predictions/any/resolve",
            json={
                "actual_outcome": "test",
                "accurate": True,
            },
        )
        assert resp.status_code == 503
