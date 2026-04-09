"""
Agent Network — Inter-agent learning and knowledge sharing.

Agents share insights, cross-pollinate learnings, and build collective
intelligence. When one agent learns something useful, the network
propagates it to relevant peers.

Key concepts:
- AgentInsight: A piece of knowledge shared by one agent, useful to others
- Domain affinity: Maps domains to agents likely to benefit from insights
- Propagation: Background loop distributes insights to relevant agents
- Network context: Injected into agent prompts before task dispatch

Stored in SQLite for persistence across restarts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.network")

NETWORK_DB = ROOT_DIR / "data" / "agent_network.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data models ──────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentInsight:
    """A piece of knowledge shared across the agent network."""
    id: str
    source_agent: str
    insight_type: str  # discovery, pattern, warning, technique, market_signal
    domain: str  # market, code, research, trading, system, learning
    content: str
    confidence: float = 0.7
    relevance_agents: tuple[str, ...] = ()  # Agents this is most relevant to
    ttl_hours: int = 48
    applied_count: int = 0
    created_at: str = field(default_factory=_now_iso)
    expires_at: Optional[str] = None


# ── Domain → agent affinity ─────────────────────────────────────

_DOMAIN_AFFINITY: dict[str, tuple[str, ...]] = {
    "market": ("swarm", "miro", "analyst", "researcher"),
    "trading": ("swarm", "miro", "analyst"),
    "code": ("coder", "builder", "hermes"),
    "research": ("researcher", "analyst", "openclaw"),
    "system": ("guardian", "builder", "hermes"),
    "learning": ("researcher", "analyst", "coder", "builder"),
    "product": ("coder", "analyst", "researcher", "writer"),
    "writing": ("writer", "researcher"),
    "security": ("guardian", "analyst"),
    "data": ("openclaw", "researcher", "analyst"),
}

# Reverse: agent → domains they care about
_AGENT_DOMAINS: dict[str, set[str]] = {}
for _domain, _agents in _DOMAIN_AFFINITY.items():
    for _agent in _agents:
        _AGENT_DOMAINS.setdefault(_agent, set()).add(_domain)


class AgentNetwork:
    """Inter-agent knowledge sharing and collective intelligence.

    Agents share insights through the network. The network propagates
    relevant insights to agents that would benefit, building collective
    intelligence across the system.
    """

    PROPAGATION_INTERVAL = 300  # 5 minutes
    MAX_INSIGHTS_PER_AGENT = 10  # Context window budget

    def __init__(self, bus=None, learning=None, memory=None) -> None:
        self._bus = bus
        self._learning = learning
        self._memory = memory
        self._conn: Optional[sqlite3.Connection] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._propagation_count = 0
        self._failure_count: int = 0

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        NETWORK_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(NETWORK_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        self._expire_insights()
        logger.info("AgentNetwork started (db=%s)", NETWORK_DB)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
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
            raise RuntimeError("AgentNetwork not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS insights (
                id TEXT PRIMARY KEY,
                source_agent TEXT NOT NULL,
                insight_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL DEFAULT 0.7,
                relevance_agents TEXT DEFAULT '[]',
                ttl_hours INTEGER DEFAULT 48,
                applied_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                expires_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_ins_domain ON insights(domain);
            CREATE INDEX IF NOT EXISTS idx_ins_source ON insights(source_agent);
            CREATE INDEX IF NOT EXISTS idx_ins_created ON insights(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_ins_expires ON insights(expires_at);

            CREATE TABLE IF NOT EXISTS network_effects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                insight_id TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                effect TEXT DEFAULT '',
                quality_delta REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ne_insight ON network_effects(insight_id);
        """)

    # ── Share insights ────────────────────────────────────────────

    def share_insight(
        self,
        source_agent: str,
        insight_type: str,
        domain: str,
        content: str,
        confidence: float = 0.7,
        relevance_agents: Optional[list[str]] = None,
        ttl_hours: int = 48,
    ) -> AgentInsight:
        """An agent shares a piece of knowledge with the network."""
        insight_id = f"ins_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        expires = (
            datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        ).isoformat()

        # Auto-determine relevant agents from domain affinity
        if relevance_agents is None:
            relevance_agents = list(
                _DOMAIN_AFFINITY.get(domain, ("researcher",))
            )
            # Remove the source agent — they already know
            relevance_agents = [a for a in relevance_agents if a != source_agent]

        insight = AgentInsight(
            id=insight_id,
            source_agent=source_agent,
            insight_type=insight_type,
            domain=domain,
            content=content[:2000],
            confidence=confidence,
            relevance_agents=tuple(relevance_agents),
            ttl_hours=ttl_hours,
            created_at=now,
            expires_at=expires,
        )

        self.conn.execute(
            """INSERT INTO insights
               (id, source_agent, insight_type, domain, content, confidence,
                relevance_agents, ttl_hours, applied_count, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (insight.id, insight.source_agent, insight.insight_type,
             insight.domain, insight.content, insight.confidence,
             json.dumps(list(insight.relevance_agents)),
             insight.ttl_hours, insight.created_at, insight.expires_at),
        )
        self.conn.commit()

        logger.info(
            "Insight shared: [%s] %s → %s (conf=%.2f, domain=%s)",
            insight_type, source_agent, relevance_agents, confidence, domain,
        )

        # Publish to bus
        if self._bus:
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(self._publish_insight(insight))
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
            except RuntimeError:
                pass  # No running event loop — skip publishing

        return insight

    async def _publish_insight(self, insight: AgentInsight) -> None:
        if self._bus:
            msg = self._bus.create_message(
                topic=f"network.insight.{insight.domain}",
                sender=insight.source_agent,
                payload={
                    "type": "insight_shared",
                    "insight_id": insight.id,
                    "domain": insight.domain,
                    "insight_type": insight.insight_type,
                    "content": insight.content[:500],
                    "relevance_agents": list(insight.relevance_agents),
                },
            )
            await self._bus.publish(msg)

    # ── Query insights ────────────────────────────────────────────

    def get_insights_for(
        self, agent_id: str, limit: int = 10,
    ) -> list[AgentInsight]:
        """Get relevant insights for a specific agent."""
        now = _now_iso()
        # Get insights where agent is in relevance list or domain matches
        agent_domains = _AGENT_DOMAINS.get(agent_id, set())

        rows = self.conn.execute(
            """SELECT * FROM insights
               WHERE (expires_at IS NULL OR expires_at > ?)
               ORDER BY confidence DESC, created_at DESC
               LIMIT ?""",
            (now, limit * 3),  # Fetch extra, then filter
        ).fetchall()

        insights: list[AgentInsight] = []
        for row in rows:
            try:
                relevance = json.loads(row["relevance_agents"] or "[]")
            except (json.JSONDecodeError, TypeError):
                relevance = []
            domain = row["domain"]

            # Include if agent is explicitly relevant or domain matches
            if agent_id in relevance or domain in agent_domains:
                insights.append(self._row_to_insight(row))
                if len(insights) >= limit:
                    break

        return insights

    def get_network_context(self, agent_id: str, max_chars: int = 2000) -> str:
        """Build a context string of network insights for injection into agent prompts."""
        insights = self.get_insights_for(agent_id, limit=self.MAX_INSIGHTS_PER_AGENT)
        if not insights:
            return ""

        lines = ["## Network Intelligence (shared by other agents)"]
        char_count = len(lines[0])

        for ins in insights:
            line = (
                f"- [{ins.insight_type}] from {ins.source_agent} "
                f"({ins.domain}, conf={ins.confidence:.0%}): {ins.content[:300]}"
            )
            if char_count + len(line) > max_chars:
                break
            lines.append(line)
            char_count += len(line)

        return "\n".join(lines)

    def get_all_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get all recent insights."""
        rows = self.conn.execute(
            "SELECT * FROM insights ORDER BY created_at DESC LIMIT ?", (limit,),
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    # ── Record effects ────────────────────────────────────────────

    def record_network_effect(
        self, insight_id: str, target_agent: str,
        effect: str = "", quality_delta: float = 0.0,
    ) -> None:
        """Record that an insight was used by an agent and its effect."""
        self.conn.execute(
            """INSERT INTO network_effects (insight_id, target_agent, effect, quality_delta, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (insight_id, target_agent, effect, quality_delta, _now_iso()),
        )
        # Increment applied count
        self.conn.execute(
            "UPDATE insights SET applied_count = applied_count + 1 WHERE id = ?",
            (insight_id,),
        )
        self.conn.commit()

    # ── Propagation loop ──────────────────────────────────────────

    async def run_propagation_loop(self, interval: Optional[int] = None) -> None:
        """Background loop: expire old insights, propagate to memory."""
        if self._running:
            return
        self._running = True
        actual_interval = interval or self.PROPAGATION_INTERVAL

        await asyncio.sleep(60)  # Let systems warm up

        while self._running:
            try:
                self._propagation_count = self._propagation_count + 1
                expired = self._expire_insights()
                promoted = self._promote_high_value_insights()

                if expired or promoted:
                    logger.info(
                        "Network propagation #%d: expired=%d, promoted=%d",
                        self._propagation_count, expired, promoted,
                    )
                self._failure_count = 0
            except Exception as exc:
                self._failure_count = self._failure_count + 1
                logger.error("Network propagation error: %s", exc)
                if self._failure_count >= 5:
                    logger.critical(
                        "Agent network: %d consecutive failures — backing off 300s",
                        self._failure_count,
                    )
                    self._failure_count = 0
                    await asyncio.sleep(300)
                    continue
            await asyncio.sleep(actual_interval)

    def _expire_insights(self) -> int:
        """Remove expired insights."""
        now = _now_iso()
        cursor = self.conn.execute(
            "DELETE FROM insights WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        self.conn.commit()
        return cursor.rowcount

    def _promote_high_value_insights(self) -> int:
        """Promote high-confidence, high-use insights to long-term memory."""
        if not self._memory:
            return 0

        from backend.models.memory import MemoryEntry, MemoryType

        rows = self.conn.execute(
            """SELECT * FROM insights
               WHERE applied_count >= 3 AND confidence >= 0.8
               ORDER BY applied_count DESC LIMIT 5""",
        ).fetchall()

        promoted = 0
        for row in rows:
            # Check if already in memory (avoid duplicates)
            existing = self._memory.search(
                __import__("backend.models.memory", fromlist=["MemoryQuery"]).MemoryQuery(
                    query=row["content"][:100], limit=3,
                )
            )
            already_stored = any(
                self._text_overlap(m.content, row["content"]) > 0.6
                for m in existing
            )
            if already_stored:
                continue

            self._memory.store(MemoryEntry(
                content=f"Network insight ({row['domain']}): {row['content'][:500]}",
                memory_type=MemoryType.LEARNING,
                tags=["network", row["domain"], row["insight_type"], row["source_agent"]],
                source="agent_network",
                confidence=row["confidence"],
            ))
            promoted += 1

        return promoted

    @staticmethod
    def _safe_json_list(raw: Any) -> list:
        """Parse a JSON string as a list, returning [] on failure."""
        try:
            return json.loads(raw or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def _text_overlap(a: str, b: str) -> float:
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    # ── Statistics ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        total = self.conn.execute("SELECT COUNT(*) as c FROM insights").fetchone()["c"]
        active = self.conn.execute(
            "SELECT COUNT(*) as c FROM insights WHERE expires_at IS NULL OR expires_at > ?",
            (_now_iso(),),
        ).fetchone()["c"]
        effects = self.conn.execute(
            "SELECT COUNT(*) as c FROM network_effects"
        ).fetchone()["c"]

        domain_rows = self.conn.execute(
            "SELECT domain, COUNT(*) as cnt FROM insights GROUP BY domain"
        ).fetchall()
        source_rows = self.conn.execute(
            "SELECT source_agent, COUNT(*) as cnt FROM insights GROUP BY source_agent"
        ).fetchall()

        return {
            "total_insights": total,
            "active_insights": active,
            "total_effects": effects,
            "propagation_cycles": self._propagation_count,
            "by_domain": {r["domain"]: r["cnt"] for r in domain_rows},
            "by_source": {r["source_agent"]: r["cnt"] for r in source_rows},
        }

    # ── Helpers ───────────────────────────────────────────────────

    def _row_to_insight(self, row: sqlite3.Row) -> AgentInsight:
        return AgentInsight(
            id=row["id"],
            source_agent=row["source_agent"],
            insight_type=row["insight_type"],
            domain=row["domain"],
            content=row["content"],
            confidence=row["confidence"],
            relevance_agents=tuple(self._safe_json_list(row["relevance_agents"])),
            ttl_hours=row["ttl_hours"],
            applied_count=row["applied_count"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
        )

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "source_agent": row["source_agent"],
            "insight_type": row["insight_type"],
            "domain": row["domain"],
            "content": row["content"],
            "confidence": row["confidence"],
            "relevance_agents": self._safe_json_list(row["relevance_agents"]),
            "ttl_hours": row["ttl_hours"],
            "applied_count": row["applied_count"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }
