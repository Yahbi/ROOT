"""Tests for backend.routes.backtesting — backtesting API."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.backtesting import router


@dataclass
class FakeBacktestResult:
    """Mirrors the structure expected by asdict() in the route."""
    id: str = "bt-001"
    strategy_name: str = "momentum"
    initial_capital: float = 100_000.0
    final_value: float = 112_000.0
    total_return: float = 0.12
    sharpe_ratio: float = 1.5
    max_drawdown: float = -0.05
    trades: int = 10
    win_rate: float = 0.7
    signals: list = field(default_factory=list)


@pytest.fixture
def mock_backtester():
    """Create a mock backtester with controllable returns."""
    bt = MagicMock()
    bt.backtest.return_value = FakeBacktestResult()
    bt.get_results.return_value = [
        FakeBacktestResult(id="bt-001"),
        FakeBacktestResult(id="bt-002", strategy_name="mean_reversion"),
    ]
    bt.get_result.return_value = FakeBacktestResult(id="bt-001")
    bt.monte_carlo.return_value = {
        "median_return": 0.11,
        "p5_return": -0.03,
        "p95_return": 0.25,
        "simulations": 1000,
    }
    return bt


@pytest.fixture
def client(mock_backtester):
    """FastAPI test client with mocked backtester."""
    app = FastAPI()
    app.include_router(router)
    app.state.backtester = mock_backtester
    return TestClient(app)


@pytest.fixture
def client_no_backtester():
    """FastAPI test client without backtester (503 case)."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _valid_signals():
    """Return a minimal valid signals list."""
    return [
        {
            "date": "2025-01-15",
            "symbol": "AAPL",
            "action": "buy",
            "price": 150.0,
            "quantity": 10,
        },
        {
            "date": "2025-02-15",
            "symbol": "AAPL",
            "action": "sell",
            "price": 165.0,
            "quantity": 10,
        },
    ]


class TestRunBacktest:
    def test_valid_backtest(self, client):
        resp = client.post(
            "/api/backtesting/run",
            json={
                "strategy_name": "momentum",
                "signals": _valid_signals(),
                "initial_capital": 100_000.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "result" in data
        assert data["result"]["strategy_name"] == "momentum"

    def test_default_initial_capital(self, client, mock_backtester):
        resp = client.post(
            "/api/backtesting/run",
            json={
                "strategy_name": "test",
                "signals": _valid_signals(),
            },
        )
        assert resp.status_code == 200
        call_kwargs = mock_backtester.backtest.call_args
        assert call_kwargs.kwargs.get("initial_capital") == 100_000.0 or call_kwargs[1].get("initial_capital") == 100_000.0

    def test_missing_strategy_name(self, client):
        resp = client.post(
            "/api/backtesting/run",
            json={"signals": _valid_signals()},
        )
        assert resp.status_code == 422

    def test_empty_signals(self, client):
        resp = client.post(
            "/api/backtesting/run",
            json={"strategy_name": "test", "signals": []},
        )
        assert resp.status_code == 422

    def test_invalid_action(self, client):
        resp = client.post(
            "/api/backtesting/run",
            json={
                "strategy_name": "test",
                "signals": [
                    {
                        "date": "2025-01-15",
                        "symbol": "AAPL",
                        "action": "hold",  # invalid: must be buy or sell
                        "price": 150.0,
                        "quantity": 10,
                    }
                ],
            },
        )
        assert resp.status_code == 422

    def test_negative_price(self, client):
        resp = client.post(
            "/api/backtesting/run",
            json={
                "strategy_name": "test",
                "signals": [
                    {
                        "date": "2025-01-15",
                        "symbol": "AAPL",
                        "action": "buy",
                        "price": -10.0,
                        "quantity": 10,
                    }
                ],
            },
        )
        assert resp.status_code == 422

    def test_zero_quantity(self, client):
        resp = client.post(
            "/api/backtesting/run",
            json={
                "strategy_name": "test",
                "signals": [
                    {
                        "date": "2025-01-15",
                        "symbol": "AAPL",
                        "action": "buy",
                        "price": 150.0,
                        "quantity": 0,
                    }
                ],
            },
        )
        assert resp.status_code == 422

    def test_backtester_value_error(self, client, mock_backtester):
        mock_backtester.backtest.side_effect = ValueError("Bad strategy")
        resp = client.post(
            "/api/backtesting/run",
            json={"strategy_name": "bad", "signals": _valid_signals()},
        )
        assert resp.status_code == 400

    def test_backtester_generic_error(self, client, mock_backtester):
        mock_backtester.backtest.side_effect = RuntimeError("Crash")
        resp = client.post(
            "/api/backtesting/run",
            json={"strategy_name": "crash", "signals": _valid_signals()},
        )
        assert resp.status_code == 500

    def test_no_backtester_returns_503(self, client_no_backtester):
        resp = client_no_backtester.post(
            "/api/backtesting/run",
            json={"strategy_name": "test", "signals": _valid_signals()},
        )
        assert resp.status_code == 503


class TestListResults:
    def test_list_results(self, client):
        resp = client.get("/api/backtesting/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_list_with_limit(self, client, mock_backtester):
        resp = client.get("/api/backtesting/results?limit=5")
        assert resp.status_code == 200
        mock_backtester.get_results.assert_called_with(limit=5)

    def test_list_invalid_limit(self, client):
        resp = client.get("/api/backtesting/results?limit=0")
        assert resp.status_code == 422

    def test_list_no_backtester(self, client_no_backtester):
        resp = client_no_backtester.get("/api/backtesting/results")
        assert resp.status_code == 503


class TestGetResult:
    def test_get_existing(self, client):
        resp = client.get("/api/backtesting/results/bt-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["id"] == "bt-001"

    def test_get_not_found(self, client, mock_backtester):
        mock_backtester.get_result.return_value = None
        resp = client.get("/api/backtesting/results/nonexistent")
        assert resp.status_code == 404

    def test_get_no_backtester(self, client_no_backtester):
        resp = client_no_backtester.get("/api/backtesting/results/bt-001")
        assert resp.status_code == 503


class TestMonteCarlo:
    def test_monte_carlo_default_simulations(self, client):
        resp = client.post("/api/backtesting/monte-carlo/bt-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "monte_carlo" in data
        assert "source" in data

    def test_monte_carlo_custom_simulations(self, client, mock_backtester):
        resp = client.post(
            "/api/backtesting/monte-carlo/bt-001",
            json={"simulations": 500},
        )
        assert resp.status_code == 200
        mock_backtester.monte_carlo.assert_called_once()
        call_kwargs = mock_backtester.monte_carlo.call_args
        assert call_kwargs.kwargs.get("simulations") == 500 or call_kwargs[1].get("simulations") == 500

    def test_monte_carlo_result_not_found(self, client, mock_backtester):
        mock_backtester.get_result.return_value = None
        resp = client.post("/api/backtesting/monte-carlo/nonexistent")
        assert resp.status_code == 404

    def test_monte_carlo_value_error(self, client, mock_backtester):
        mock_backtester.monte_carlo.side_effect = ValueError("No trades")
        resp = client.post("/api/backtesting/monte-carlo/bt-001")
        assert resp.status_code == 400

    def test_monte_carlo_generic_error(self, client, mock_backtester):
        mock_backtester.monte_carlo.side_effect = RuntimeError("Crash")
        resp = client.post("/api/backtesting/monte-carlo/bt-001")
        assert resp.status_code == 500

    def test_monte_carlo_no_backtester(self, client_no_backtester):
        resp = client_no_backtester.post("/api/backtesting/monte-carlo/bt-001")
        assert resp.status_code == 503
