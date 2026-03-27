"""Tests for the Agent Network — inter-agent knowledge sharing."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from backend.core.agent_network import AgentInsight, AgentNetwork, _DOMAIN_AFFINITY, _AGENT_DOMAINS


@pytest.fixture
def network(tmp_path):
    """Provide an AgentNetwork with in-memory DB."""
    db_path = tmp_path / "test_network.db"
    with patch("backend.core.agent_network.NETWORK_DB", db_path):
        net = AgentNetwork()
        net.start()
        yield net
        net.stop()


@pytest.fixture
def network_with_memory(tmp_path, memory_engine):
    """Provide an AgentNetwork with memory engine."""
    db_path = tmp_path / "test_network_mem.db"
    with patch("backend.core.agent_network.NETWORK_DB", db_path):
        net = AgentNetwork(memory=memory_engine)
        net.start()
        yield net
        net.stop()


# ── AgentInsight dataclass ─────────────────────────────────────


class TestAgentInsight:
    def test_frozen(self):
        ins = AgentInsight(
            id="i1", source_agent="builder", insight_type="discovery",
            domain="code", content="test insight",
        )
        with pytest.raises(AttributeError):
            ins.content = "changed"  # type: ignore[misc]

    def test_defaults(self):
        ins = AgentInsight(
            id="i1", source_agent="a", insight_type="t", domain="d", content="c",
        )
        assert ins.confidence == 0.7
        assert ins.relevance_agents == ()
        assert ins.ttl_hours == 48
        assert ins.applied_count == 0
        assert ins.created_at  # auto-populated


# ── Domain affinity ────────────────────────────────────────────


class TestDomainAffinity:
    def test_domain_affinity_populated(self):
        assert "market" in _DOMAIN_AFFINITY
        assert "code" in _DOMAIN_AFFINITY
        assert len(_DOMAIN_AFFINITY) > 0

    def test_agent_domains_reverse_map(self):
        assert "builder" in _AGENT_DOMAINS
        assert "code" in _AGENT_DOMAINS["builder"]

    def test_researcher_in_multiple_domains(self):
        assert "research" in _AGENT_DOMAINS.get("researcher", set())


# ── Lifecycle ──────────────────────────────────────────────────


class TestLifecycle:
    def test_start_creates_tables(self, network: AgentNetwork):
        tables = network.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        assert "insights" in table_names
        assert "network_effects" in table_names

    def test_conn_raises_when_not_started(self):
        net = AgentNetwork()
        with pytest.raises(RuntimeError, match="not started"):
            _ = net.conn

    def test_stop_closes_connection(self, tmp_path):
        db_path = tmp_path / "stop_test.db"
        with patch("backend.core.agent_network.NETWORK_DB", db_path):
            net = AgentNetwork()
            net.start()
            net.stop()
            assert net._conn is None


# ── Share insight ──────────────────────────────────────────────


class TestShareInsight:
    def test_share_insight_basic(self, network: AgentNetwork):
        insight = network.share_insight(
            source_agent="builder",
            insight_type="discovery",
            domain="code",
            content="Found a useful pattern",
        )
        assert isinstance(insight, AgentInsight)
        assert insight.source_agent == "builder"
        assert insight.domain == "code"
        assert insight.content == "Found a useful pattern"
        assert insight.expires_at is not None

    def test_share_insight_persisted(self, network: AgentNetwork):
        network.share_insight(
            source_agent="researcher", insight_type="pattern",
            domain="research", content="Research finding",
        )
        rows = network.conn.execute("SELECT COUNT(*) as c FROM insights").fetchone()
        assert rows["c"] == 1

    def test_share_insight_auto_relevance(self, network: AgentNetwork):
        insight = network.share_insight(
            source_agent="builder", insight_type="discovery",
            domain="code", content="Code pattern",
        )
        # builder is in code domain — should be removed from relevance
        assert "builder" not in insight.relevance_agents
        # Other code-domain agents should be included
        assert "coder" in insight.relevance_agents

    def test_share_insight_custom_relevance(self, network: AgentNetwork):
        insight = network.share_insight(
            source_agent="researcher", insight_type="technique",
            domain="research", content="Custom target",
            relevance_agents=["analyst", "writer"],
        )
        assert set(insight.relevance_agents) == {"analyst", "writer"}

    def test_share_insight_truncates_content(self, network: AgentNetwork):
        long_content = "x" * 5000
        insight = network.share_insight(
            source_agent="a", insight_type="t", domain="code", content=long_content,
        )
        assert len(insight.content) == 2000

    def test_share_insight_with_confidence(self, network: AgentNetwork):
        insight = network.share_insight(
            source_agent="analyst", insight_type="pattern",
            domain="market", content="Market signal",
            confidence=0.95,
        )
        assert insight.confidence == 0.95

    def test_share_multiple_insights(self, network: AgentNetwork):
        for i in range(5):
            network.share_insight(
                source_agent="researcher", insight_type="discovery",
                domain="research", content=f"Insight {i}",
            )
        total = network.conn.execute("SELECT COUNT(*) as c FROM insights").fetchone()["c"]
        assert total == 5


# ── Query insights ─────────────────────────────────────────────


class TestGetInsights:
    def test_get_insights_for_relevant_agent(self, network: AgentNetwork):
        network.share_insight(
            source_agent="builder", insight_type="discovery",
            domain="code", content="Code finding",
        )
        # coder is in code domain affinity
        insights = network.get_insights_for("coder")
        assert len(insights) == 1
        assert insights[0].content == "Code finding"

    def test_get_insights_excludes_irrelevant(self, network: AgentNetwork):
        network.share_insight(
            source_agent="builder", insight_type="discovery",
            domain="code", content="Code only",
            relevance_agents=["coder"],
        )
        # swarm is in market/trading, not code
        insights = network.get_insights_for("swarm")
        assert len(insights) == 0

    def test_get_insights_respects_limit(self, network: AgentNetwork):
        for i in range(10):
            network.share_insight(
                source_agent="researcher", insight_type="discovery",
                domain="research", content=f"Finding {i}",
            )
        insights = network.get_insights_for("analyst", limit=3)
        assert len(insights) <= 3

    def test_get_insights_excludes_expired(self, network: AgentNetwork):
        # Insert an expired insight directly
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        network.conn.execute(
            """INSERT INTO insights
               (id, source_agent, insight_type, domain, content, confidence,
                relevance_agents, ttl_hours, applied_count, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            ("expired1", "builder", "discovery", "code", "Old stuff", 0.7,
             '["coder"]', 1, past, past),
        )
        network.conn.commit()
        insights = network.get_insights_for("coder")
        assert len(insights) == 0


# ── Network context ────────────────────────────────────────────


class TestNetworkContext:
    def test_empty_context(self, network: AgentNetwork):
        ctx = network.get_network_context("coder")
        assert ctx == ""

    def test_context_includes_header(self, network: AgentNetwork):
        network.share_insight(
            source_agent="builder", insight_type="technique",
            domain="code", content="Use async patterns",
        )
        ctx = network.get_network_context("coder")
        assert "Network Intelligence" in ctx
        assert "async patterns" in ctx

    def test_context_respects_max_chars(self, network: AgentNetwork):
        for i in range(20):
            network.share_insight(
                source_agent="researcher", insight_type="discovery",
                domain="research", content=f"Long insight content number {i} " * 10,
            )
        ctx = network.get_network_context("analyst", max_chars=500)
        assert len(ctx) <= 600  # Small buffer for last line


# ── Get all recent ─────────────────────────────────────────────


class TestGetAllRecent:
    def test_get_all_recent(self, network: AgentNetwork):
        network.share_insight(
            source_agent="a", insight_type="t", domain="code", content="c1",
        )
        network.share_insight(
            source_agent="b", insight_type="t", domain="market", content="c2",
        )
        recent = network.get_all_recent()
        assert len(recent) == 2
        assert all(isinstance(r, dict) for r in recent)
        assert "id" in recent[0]

    def test_get_all_recent_limit(self, network: AgentNetwork):
        for i in range(10):
            network.share_insight(
                source_agent="a", insight_type="t", domain="code", content=f"c{i}",
            )
        assert len(network.get_all_recent(limit=3)) == 3


# ── Record effects ─────────────────────────────────────────────


class TestRecordEffect:
    def test_record_network_effect(self, network: AgentNetwork):
        insight = network.share_insight(
            source_agent="builder", insight_type="technique",
            domain="code", content="Pattern found",
        )
        network.record_network_effect(
            insight_id=insight.id, target_agent="coder",
            effect="Applied pattern successfully", quality_delta=0.1,
        )
        # Check effect recorded
        effects = network.conn.execute(
            "SELECT * FROM network_effects WHERE insight_id = ?", (insight.id,)
        ).fetchall()
        assert len(effects) == 1
        assert effects[0]["target_agent"] == "coder"

    def test_record_effect_increments_applied_count(self, network: AgentNetwork):
        insight = network.share_insight(
            source_agent="a", insight_type="t", domain="code", content="c",
        )
        network.record_network_effect(insight.id, "coder")
        network.record_network_effect(insight.id, "hermes")
        row = network.conn.execute(
            "SELECT applied_count FROM insights WHERE id = ?", (insight.id,)
        ).fetchone()
        assert row["applied_count"] == 2


# ── Expire insights ────────────────────────────────────────────


class TestExpireInsights:
    def test_expire_old_insights(self, network: AgentNetwork):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        network.conn.execute(
            """INSERT INTO insights
               (id, source_agent, insight_type, domain, content, confidence,
                relevance_agents, ttl_hours, applied_count, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            ("old1", "a", "t", "code", "expired", 0.7, "[]", 1, past, past),
        )
        network.conn.commit()
        expired = network._expire_insights()
        assert expired == 1

    def test_active_insights_not_expired(self, network: AgentNetwork):
        network.share_insight(
            source_agent="a", insight_type="t", domain="code", content="fresh",
        )
        expired = network._expire_insights()
        assert expired == 0


# ── Text overlap ───────────────────────────────────────────────


class TestTextOverlap:
    def test_identical_texts(self):
        assert AgentNetwork._text_overlap("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert AgentNetwork._text_overlap("hello", "goodbye") == 0.0

    def test_partial_overlap(self):
        score = AgentNetwork._text_overlap("hello world", "hello there")
        assert 0.0 < score < 1.0

    def test_empty_string(self):
        assert AgentNetwork._text_overlap("", "hello") == 0.0
        assert AgentNetwork._text_overlap("hello", "") == 0.0


# ── Stats ──────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, network: AgentNetwork):
        s = network.stats()
        assert s["total_insights"] == 0
        assert s["active_insights"] == 0
        assert s["total_effects"] == 0
        assert s["propagation_cycles"] == 0

    def test_stats_after_sharing(self, network: AgentNetwork):
        network.share_insight(
            source_agent="builder", insight_type="discovery",
            domain="code", content="insight 1",
        )
        network.share_insight(
            source_agent="researcher", insight_type="pattern",
            domain="research", content="insight 2",
        )
        s = network.stats()
        assert s["total_insights"] == 2
        assert s["active_insights"] == 2
        assert s["by_domain"]["code"] == 1
        assert s["by_domain"]["research"] == 1
        assert s["by_source"]["builder"] == 1
        assert s["by_source"]["researcher"] == 1

    def test_stats_includes_effects(self, network: AgentNetwork):
        insight = network.share_insight(
            source_agent="a", insight_type="t", domain="code", content="c",
        )
        network.record_network_effect(insight.id, "coder")
        s = network.stats()
        assert s["total_effects"] == 1
