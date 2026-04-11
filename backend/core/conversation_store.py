"""
Conversation Store — persistent conversation history for ROOT.

Stores all conversations in SQLite so ROOT can reference past sessions.
Conversations persist across server restarts.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import DATA_DIR


class ConversationStore:
    """Persistent conversation storage using SQLite."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or (DATA_DIR / "conversations.db"))
        self._conn: Optional[sqlite3.Connection] = None
        self._current_session_id: Optional[str] = None

    def start(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        self._current_session_id = f"sess_{uuid.uuid4().hex[:12]}"

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self, '_conn') and self._conn:
            self._conn.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("ConversationStore not started")
        return self._conn

    @property
    def current_session_id(self) -> str:
        return self._current_session_id or "unknown"

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                started_at TEXT NOT NULL,
                ended_at TEXT,
                message_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                agent_id TEXT,
                memories_used TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
        """)

    def new_session(self, title: str = "") -> str:
        """Start a new conversation session."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            "INSERT INTO sessions (id, title, started_at) VALUES (?, ?, ?)",
            (session_id, title, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()
        self._current_session_id = session_id
        return session_id

    def add_message(
        self,
        role: str,
        content: str,
        agent_id: Optional[str] = None,
        memories_used: Optional[list[str]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Store a message in the current session."""
        sid = session_id or self._current_session_id
        if not sid:
            sid = self.new_session()

        # Ensure session exists
        existing = self.conn.execute("SELECT id FROM sessions WHERE id = ?", (sid,)).fetchone()
        if not existing:
            self.conn.execute(
                "INSERT INTO sessions (id, title, started_at) VALUES (?, ?, ?)",
                (sid, "", datetime.now(timezone.utc).isoformat()),
            )

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            "INSERT INTO messages (id, session_id, role, content, agent_id, memories_used, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, sid, role, content, agent_id, json.dumps(memories_used or []), datetime.now(timezone.utc).isoformat()),
        )
        self.conn.execute(
            "UPDATE sessions SET message_count = message_count + 1 WHERE id = ?",
            (sid,),
        )
        self.conn.commit()
        return msg_id

    def get_session_messages(self, session_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get messages from a session."""
        sid = session_id or self._current_session_id
        if not sid:
            return []
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (sid, limit),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "agent_id": r["agent_id"],
                "memories_used": json.loads(r["memories_used"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_sessions(self, limit: int = 20) -> list[dict]:
        """List recent conversation sessions with first user message as preview."""
        rows = self.conn.execute(
            """
            SELECT s.id, s.title, s.started_at, s.ended_at, s.message_count,
                   (SELECT content FROM messages WHERE session_id = s.id AND role = 'user'
                    ORDER BY created_at ASC LIMIT 1) AS first_message
            FROM sessions s
            ORDER BY s.started_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"] or r["first_message"] or "",
                "started_at": r["started_at"],
                "ended_at": r["ended_at"],
                "message_count": r["message_count"],
            }
            for r in rows
        ]

    def search_conversations(self, query: str, limit: int = 20) -> list[dict]:
        """Search across all conversation messages."""
        rows = self.conn.execute(
            "SELECT m.*, s.title as session_title FROM messages m JOIN sessions s ON m.session_id = s.id WHERE m.content LIKE ? ORDER BY m.created_at DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [
            {
                "message_id": r["id"],
                "session_id": r["session_id"],
                "session_title": r["session_title"],
                "role": r["role"],
                "content": r["content"][:200],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def end_session(self, session_id: Optional[str] = None) -> None:
        """Mark a session as ended."""
        sid = session_id or self._current_session_id
        if sid:
            self.conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), sid),
            )
            self.conn.commit()

    def stats(self) -> dict:
        total_sessions = self.conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]
        total_messages = self.conn.execute("SELECT COUNT(*) as c FROM messages").fetchone()["c"]
        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "current_session": self._current_session_id,
        }
