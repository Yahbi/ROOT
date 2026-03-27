"""API route tests for /api/sandbox/* endpoints.

Uses FastAPI TestClient with mocked app.state.sandbox_gate and app.state.approval.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.sandbox_gate import SandboxGate, SystemMode
from backend.routes.sandbox import router


def _make_app(tmp_path: Path) -> tuple[FastAPI, SandboxGate]:
    """Create a FastAPI app with sandbox routes and a real SandboxGate."""
    # Real state store with SQLite
    db_path = tmp_path / "sandbox_route_test.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    store = MagicMock()
    store.conn = conn
    store.get.return_value = None

    gate = SandboxGate(state_store=store)

    app = FastAPI()
    app.include_router(router)
    app.state.sandbox_gate = gate

    # Mock approval chain
    approval = MagicMock()
    approval.get_pending.return_value = []
    app.state.approval = approval

    return app, gate


# ── GET /api/sandbox/status ─────────────────────────────────────


class TestSandboxStatusRoute:
    def test_get_status_returns_structure(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/sandbox/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "global_mode" in data
        assert "system_modes" in data
        assert data["global_mode"] == "sandbox"

    def test_status_shows_all_systems(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/sandbox/status")
        data = resp.json()
        systems = data["system_modes"]
        # All 8 systems from SystemId enum
        expected = {
            "trading", "notifications", "code_deploy", "revenue",
            "agents_external", "proactive", "plugins", "file_system",
        }
        assert set(systems.keys()) == expected


# ── PATCH /api/sandbox/mode ─────────────────────────────────────


class TestSetGlobalMode:
    def test_set_sandbox_mode(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.patch("/api/sandbox/mode", json={"mode": "sandbox"})
        assert resp.status_code == 200
        assert resp.json()["global_mode"] == "sandbox"

    def test_set_live_mode(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.patch("/api/sandbox/mode", json={"mode": "live"})
        assert resp.status_code == 200
        assert resp.json()["global_mode"] == "live"

    def test_invalid_mode_returns_400(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.patch("/api/sandbox/mode", json={"mode": "yolo"})
        assert resp.status_code == 400
        assert "Invalid mode" in resp.json()["detail"]


# ── PATCH /api/sandbox/system/{id} ─────────────────────────────


class TestSetSystemMode:
    def test_set_system_override(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.patch(
            "/api/sandbox/system/trading", json={"mode": "live"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["system_id"] == "trading"
        assert data["mode"] == "live"

    def test_invalid_system_mode_returns_400(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.patch(
            "/api/sandbox/system/trading", json={"mode": "invalid"}
        )
        assert resp.status_code == 400


# ── POST /api/sandbox/go-live ──────────────────────────────────


class TestGoLive:
    def test_go_live_without_confirm_returns_400(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.post("/api/sandbox/go-live", json={"confirm": False})
        assert resp.status_code == 400
        assert "confirm=true" in resp.json()["detail"]

    def test_go_live_with_confirm_switches_to_live(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.post("/api/sandbox/go-live", json={"confirm": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["global_mode"] == "live"
        assert "LIVE" in data["message"]

        # Verify status reflects the change
        status = client.get("/api/sandbox/status").json()
        assert status["global_mode"] == "live"


# ── GET /api/sandbox/blocked-intents ────────────────────────────


class TestBlockedIntents:
    def test_blocked_intents_returns_list(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        # Generate a blocked intent
        gate.check(system_id="trading", action="execute_trade", description="test")

        resp = client.get("/api/sandbox/blocked-intents")
        assert resp.status_code == 200
        data = resp.json()
        assert "blocked_intents" in data
        assert data["count"] >= 1
        assert data["blocked_intents"][0]["action"] == "execute_trade"

    def test_blocked_intents_limit(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/sandbox/blocked-intents?limit=5")
        assert resp.status_code == 200

    def test_blocked_intents_invalid_limit(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/sandbox/blocked-intents?limit=0")
        assert resp.status_code == 400


# ── GET /api/sandbox/categories ─────────────────────────────────


class TestCategories:
    def test_categories_returns_all_six(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/sandbox/categories")
        assert resp.status_code == 200
        data = resp.json()
        cats = data["categories"]
        assert len(cats) == 6
        for name, policy in cats.items():
            assert "requires_approval" in policy
            assert "notification_level" in policy
            assert "auto_execute_delay_seconds" in policy


# ── GET /api/sandbox/pending-approvals ──────────────────────────


class TestPendingApprovals:
    def test_pending_approvals_empty(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/sandbox/pending-approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending"] == []
        assert data["count"] == 0

    def test_pending_approvals_with_items(self, tmp_path):
        app, gate = _make_app(tmp_path)

        # Mock a pending approval
        mock_request = MagicMock()
        mock_request.id = "req_123"
        mock_request.agent_id = "hedge_fund"
        mock_request.action = "execute_trade"
        mock_request.description = "BUY AAPL"
        mock_request.risk_level = MagicMock()
        mock_request.risk_level.value = "critical"
        mock_request.created_at = "2026-03-26T00:00:00Z"
        app.state.approval.get_pending.return_value = [mock_request]

        client = TestClient(app)
        resp = client.get("/api/sandbox/pending-approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["pending"][0]["id"] == "req_123"


# ── POST /api/sandbox/approve/{id} & reject/{id} ───────────────


class TestApproveReject:
    def test_approve_request(self, tmp_path):
        app, gate = _make_app(tmp_path)
        app.state.approval.approve.return_value = MagicMock()
        client = TestClient(app)

        resp = client.post("/api/sandbox/approve/req_123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        app.state.approval.approve.assert_called_once_with("req_123", resolver="yohan")

    def test_reject_request(self, tmp_path):
        app, gate = _make_app(tmp_path)
        app.state.approval.reject.return_value = MagicMock()
        client = TestClient(app)

        resp = client.post("/api/sandbox/reject/req_456")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        app.state.approval.reject.assert_called_once_with("req_456", resolver="yohan")

    def test_approve_nonexistent_returns_404(self, tmp_path):
        app, gate = _make_app(tmp_path)
        app.state.approval.approve.side_effect = Exception("Not found")
        client = TestClient(app)

        resp = client.post("/api/sandbox/approve/nonexistent")
        assert resp.status_code == 404

    def test_reject_nonexistent_returns_404(self, tmp_path):
        app, gate = _make_app(tmp_path)
        app.state.approval.reject.side_effect = Exception("Not found")
        client = TestClient(app)

        resp = client.post("/api/sandbox/reject/nonexistent")
        assert resp.status_code == 404

    def test_approve_without_approval_chain_returns_503(self, tmp_path):
        app, gate = _make_app(tmp_path)
        app.state.approval = None
        client = TestClient(app)

        resp = client.post("/api/sandbox/approve/req_123")
        assert resp.status_code == 503


# ── GET /api/sandbox/decisions ──────────────────────────────────


class TestDecisions:
    def test_get_decisions(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        # Generate some decisions
        gate.check(system_id="trading", action="test_action")
        gate.check(system_id="revenue", action="record_revenue")

        resp = client.get("/api/sandbox/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    def test_get_decisions_filtered_by_system(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        gate.check(system_id="trading", action="trade")
        gate.check(system_id="revenue", action="revenue")

        resp = client.get("/api/sandbox/decisions?system_id=trading")
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["system_id"] == "trading" for d in data["decisions"])

    def test_get_decisions_stats(self, tmp_path):
        app, gate = _make_app(tmp_path)
        client = TestClient(app)

        gate.check(system_id="trading", action="test")

        resp = client.get("/api/sandbox/decisions/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_decisions" in data
        assert "sandboxed" in data
        assert data["total_decisions"] >= 1
