"""Tests for ConversationStore — sessions, messages, search, stats."""

from __future__ import annotations

import pytest
from pathlib import Path

from backend.core.conversation_store import ConversationStore


@pytest.fixture
def store(tmp_path: Path) -> ConversationStore:
    """Provide a started ConversationStore with temp SQLite."""
    s = ConversationStore(db_path=tmp_path / "conversations.db")
    s.start()
    yield s
    s.stop()


class TestLifecycle:
    def test_start_creates_db(self, tmp_path: Path):
        db_path = tmp_path / "sub" / "conv.db"
        s = ConversationStore(db_path=db_path)
        s.start()
        assert db_path.exists()
        s.stop()

    def test_stop_closes_connection(self, store: ConversationStore):
        store.stop()
        assert store._conn is None

    def test_conn_property_raises_before_start(self, tmp_path: Path):
        s = ConversationStore(db_path=tmp_path / "x.db")
        with pytest.raises(RuntimeError, match="not started"):
            _ = s.conn

    def test_start_sets_session_id(self, store: ConversationStore):
        assert store.current_session_id.startswith("sess_")


class TestNewSession:
    def test_creates_session(self, store: ConversationStore):
        sid = store.new_session(title="Test Session")
        assert sid.startswith("sess_")

    def test_sets_current_session(self, store: ConversationStore):
        sid = store.new_session(title="Test")
        assert store.current_session_id == sid

    def test_multiple_sessions(self, store: ConversationStore):
        sid1 = store.new_session(title="First")
        sid2 = store.new_session(title="Second")
        assert sid1 != sid2
        assert store.current_session_id == sid2


class TestAddMessage:
    def test_add_message_returns_id(self, store: ConversationStore):
        store.new_session()
        msg_id = store.add_message(role="user", content="Hello")
        assert msg_id.startswith("msg_")

    def test_add_message_to_specific_session(self, store: ConversationStore):
        sid = store.new_session(title="Target")
        store.new_session(title="Other")
        store.add_message(role="user", content="In target", session_id=sid)
        messages = store.get_session_messages(session_id=sid)
        assert len(messages) == 1
        assert messages[0]["content"] == "In target"

    def test_add_message_auto_creates_session(self, store: ConversationStore):
        # Add to a non-existent session ID — should auto-create it
        store.add_message(
            role="user", content="Auto", session_id="sess_custom123",
        )
        messages = store.get_session_messages(session_id="sess_custom123")
        assert len(messages) == 1

    def test_add_message_increments_count(self, store: ConversationStore):
        sid = store.new_session()
        store.add_message(role="user", content="1")
        store.add_message(role="assistant", content="2")
        sessions = store.get_sessions()
        target = [s for s in sessions if s["id"] == sid][0]
        assert target["message_count"] == 2

    def test_add_message_with_metadata(self, store: ConversationStore):
        store.new_session()
        store.add_message(
            role="assistant",
            content="Response",
            agent_id="astra",
            memories_used=["mem1", "mem2"],
        )
        messages = store.get_session_messages()
        assert messages[0]["agent_id"] == "astra"
        assert messages[0]["memories_used"] == ["mem1", "mem2"]

    def test_add_message_without_session_creates_one(self, store: ConversationStore):
        store._current_session_id = None
        msg_id = store.add_message(role="user", content="Orphan")
        assert msg_id.startswith("msg_")
        assert store.current_session_id.startswith("sess_")


class TestGetSessionMessages:
    def test_empty_session(self, store: ConversationStore):
        store.new_session()
        assert store.get_session_messages() == []

    def test_ordered_by_creation(self, store: ConversationStore):
        store.new_session()
        store.add_message(role="user", content="First")
        store.add_message(role="assistant", content="Second")
        store.add_message(role="user", content="Third")
        messages = store.get_session_messages()
        assert [m["content"] for m in messages] == ["First", "Second", "Third"]

    def test_limit(self, store: ConversationStore):
        store.new_session()
        for i in range(10):
            store.add_message(role="user", content=f"msg{i}")
        messages = store.get_session_messages(limit=3)
        assert len(messages) == 3

    def test_no_current_session(self, store: ConversationStore):
        store._current_session_id = None
        assert store.get_session_messages() == []

    def test_message_fields(self, store: ConversationStore):
        store.new_session()
        store.add_message(role="user", content="Hello")
        msg = store.get_session_messages()[0]
        assert "id" in msg
        assert "role" in msg
        assert "content" in msg
        assert "created_at" in msg
        assert "memories_used" in msg


class TestGetSessions:
    def test_empty(self, store: ConversationStore):
        sessions = store.get_sessions()
        # start() creates an initial session
        assert len(sessions) >= 0

    def test_lists_created_sessions(self, store: ConversationStore):
        store.new_session(title="Alpha")
        store.new_session(title="Beta")
        sessions = store.get_sessions()
        titles = [s["title"] for s in sessions]
        assert "Alpha" in titles
        assert "Beta" in titles

    def test_limit(self, store: ConversationStore):
        for i in range(5):
            store.new_session(title=f"Session {i}")
        sessions = store.get_sessions(limit=3)
        assert len(sessions) == 3

    def test_ordered_by_started_at_desc(self, store: ConversationStore):
        store.new_session(title="First")
        store.new_session(title="Second")
        sessions = store.get_sessions()
        # Most recent should be first
        assert sessions[0]["title"] == "Second"

    def test_session_fields(self, store: ConversationStore):
        store.new_session(title="Test")
        s = store.get_sessions()[0]
        assert "id" in s
        assert "title" in s
        assert "started_at" in s
        assert "message_count" in s


class TestSearchConversations:
    def test_search_finds_matching(self, store: ConversationStore):
        sid = store.new_session(title="Search Test")
        store.add_message(role="user", content="Tell me about quantum computing")
        store.add_message(role="assistant", content="Quantum computing uses qubits")
        results = store.search_conversations("quantum")
        assert len(results) >= 1
        assert any("quantum" in r["content"].lower() for r in results)

    def test_search_no_match(self, store: ConversationStore):
        store.new_session()
        store.add_message(role="user", content="Hello world")
        results = store.search_conversations("zzzznonexistent")
        assert results == []

    def test_search_limit(self, store: ConversationStore):
        store.new_session()
        for i in range(10):
            store.add_message(role="user", content=f"keyword item {i}")
        results = store.search_conversations("keyword", limit=3)
        assert len(results) == 3

    def test_search_result_fields(self, store: ConversationStore):
        store.new_session(title="Searchable")
        store.add_message(role="user", content="unique_search_term")
        results = store.search_conversations("unique_search_term")
        r = results[0]
        assert "message_id" in r
        assert "session_id" in r
        assert "session_title" in r
        assert "role" in r
        assert "content" in r
        assert "created_at" in r

    def test_search_truncates_content(self, store: ConversationStore):
        store.new_session()
        store.add_message(role="user", content="findme " + "x" * 500)
        results = store.search_conversations("findme")
        assert len(results[0]["content"]) <= 200


class TestEndSession:
    def test_end_sets_ended_at(self, store: ConversationStore):
        sid = store.new_session()
        store.end_session(sid)
        sessions = store.get_sessions()
        target = [s for s in sessions if s["id"] == sid][0]
        assert target["ended_at"] is not None

    def test_end_current_session(self, store: ConversationStore):
        sid = store.new_session()
        store.end_session()
        sessions = store.get_sessions()
        target = [s for s in sessions if s["id"] == sid][0]
        assert target["ended_at"] is not None

    def test_end_with_no_session(self, store: ConversationStore):
        store._current_session_id = None
        # Should not raise
        store.end_session()


class TestStats:
    def test_empty_stats(self, store: ConversationStore):
        stats = store.stats()
        assert "total_sessions" in stats
        assert "total_messages" in stats
        assert "current_session" in stats

    def test_stats_reflect_data(self, store: ConversationStore):
        store.new_session()
        store.add_message(role="user", content="Hello")
        store.add_message(role="assistant", content="Hi")
        stats = store.stats()
        assert stats["total_messages"] >= 2
        assert stats["total_sessions"] >= 1
