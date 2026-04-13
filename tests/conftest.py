"""Shared test fixtures for ROOT."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def tmp_db(tmp_path: Path):
    """Provide a temporary SQLite database path."""
    return tmp_path / "test.db"


@pytest.fixture
def memory_engine(tmp_db):
    """Provide a started MemoryEngine with a temp database."""
    from backend.core.memory_engine import MemoryEngine

    engine = MemoryEngine(db_path=tmp_db)
    engine.start()
    yield engine
    engine.stop()


@pytest.fixture
def mock_llm():
    """Provide a mock LLM service.

    Uses MagicMock as the base so attribute access defaults to sync mocks
    (matching production where chat_started/chat_finished are sync). Async
    methods are explicitly opted in via AsyncMock so `await llm.complete(...)`
    works as expected.
    """
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Mock LLM response")
    llm.complete_with_tools = AsyncMock(return_value=("Mock response", []))
    llm.provider = "mock"
    return llm


@pytest.fixture
def mock_plugins():
    """Provide a mock plugin engine."""
    plugins = MagicMock()
    plugins.list_tools.return_value = []
    plugins.stats.return_value = {"total_plugins": 0, "total_tools": 0}

    result = MagicMock()
    result.success = True
    result.output = {"result": "mock output"}
    result.error = None
    result.duration_ms = 10
    plugins.invoke = AsyncMock(return_value=result)
    return plugins
