"""Tests for backend.routes.notifications — notification center API."""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.notifications import router


@pytest.fixture
def mock_notifications():
    """Create a mock notification engine with controllable state."""
    engine = MagicMock()

    # Mutable notification objects stored in _history deque
    notif1 = SimpleNamespace(id="n-1", read=False)
    notif2 = SimpleNamespace(id="n-2", read=True)
    notif3 = SimpleNamespace(id="n-3", read=False)
    engine._history = deque([notif1, notif2, notif3])

    engine.get_history.return_value = [
        {"id": "n-1", "level": "high", "read": False, "message": "Alert 1"},
        {"id": "n-2", "level": "low", "read": True, "message": "Info 2"},
        {"id": "n-3", "level": "high", "read": False, "message": "Alert 3"},
    ]
    engine.stats.return_value = {
        "total_notifications": 3,
        "engine": "notification",
    }
    return engine


@pytest.fixture
def client(mock_notifications):
    """FastAPI test client with mocked notification engine."""
    app = FastAPI()
    app.include_router(router)
    app.state.notifications = mock_notifications
    return TestClient(app)


class TestGetNotifications:
    def test_returns_all_notifications(self, client):
        resp = client.get("/api/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["notifications"]) == 3

    def test_unread_count(self, client):
        resp = client.get("/api/notifications")
        data = resp.json()
        assert data["unread"] == 2  # n-1 and n-3 are unread

    def test_filter_by_level(self, client):
        resp = client.get("/api/notifications?level=high")
        data = resp.json()
        assert data["total"] == 2
        for n in data["notifications"]:
            assert n["level"] == "high"

    def test_filter_by_level_no_match(self, client):
        resp = client.get("/api/notifications?level=critical")
        data = resp.json()
        assert data["total"] == 0

    def test_limit_parameter(self, client):
        resp = client.get("/api/notifications?limit=2")
        assert resp.status_code == 200

    def test_limit_validation_min(self, client):
        resp = client.get("/api/notifications?limit=0")
        assert resp.status_code == 422

    def test_limit_validation_max(self, client):
        resp = client.get("/api/notifications?limit=201")
        assert resp.status_code == 422


class TestMarkRead:
    def test_mark_existing_as_read(self, client, mock_notifications):
        resp = client.post("/api/notifications/read/n-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify the notification object was mutated
        notif = next(n for n in mock_notifications._history if n.id == "n-1")
        assert notif.read is True

    def test_mark_nonexistent_returns_error(self, client):
        resp = client.post("/api/notifications/read/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()


class TestMarkAllRead:
    def test_mark_all_as_read(self, client, mock_notifications):
        resp = client.post("/api/notifications/read-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["marked"] == 2  # n-1 and n-3 were unread

        # All should be read now
        for notif in mock_notifications._history:
            assert notif.read is True

    def test_mark_all_when_all_read(self, client, mock_notifications):
        # Set all to read first
        for notif in mock_notifications._history:
            notif.read = True
        resp = client.post("/api/notifications/read-all")
        data = resp.json()
        assert data["marked"] == 0


class TestNotificationStats:
    def test_stats_endpoint(self, client):
        resp = client.get("/api/notifications/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_notifications" in data
        assert "unread" in data
        assert data["unread"] == 2
