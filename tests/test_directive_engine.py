"""Tests for DirectiveEngine — ROOT's autonomous strategic executive function."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

import backend.core.directive_engine as de_mod
from backend.core.directive_engine import (
    Directive,
    DirectiveEngine,
    _CATEGORY_AGENTS,
    _CATEGORY_RISK,
    _now_iso,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def directive_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(de_mod, "DIRECTIVE_DB", tmp_path / "directives.db")
    engine = DirectiveEngine()
    engine.start()
    yield engine
    engine.stop()


def _make_directive(**overrides) -> Directive:
    """Helper to create a Directive with sensible defaults."""
    defaults = {
        "id": "dir_test123",
        "title": "Test directive",
        "rationale": "Testing rationale",
        "priority": 5,
        "category": "general",
        "assigned_agents": ("researcher",),
        "collab_pattern": "delegate",
        "task_description": "Do something useful",
        "status": "proposed",
        "source_signals": (),
        "ttl_minutes": 120,
        "created_at": _now_iso(),
    }
    defaults.update(overrides)
    return Directive(**defaults)


# ── 1. Directive dataclass immutability ───────────────────────────


class TestDirectiveDataclass:
    def test_frozen_immutability(self):
        d = _make_directive()
        with pytest.raises(FrozenInstanceError):
            d.title = "mutated"  # type: ignore[misc]

    def test_frozen_status_immutability(self):
        d = _make_directive()
        with pytest.raises(FrozenInstanceError):
            d.status = "completed"  # type: ignore[misc]

    def test_default_values(self):
        d = Directive(id="x", title="t", rationale="r")
        assert d.priority == 5
        assert d.category == "general"
        assert d.assigned_agents == ()
        assert d.collab_pattern == "delegate"
        assert d.status == "proposed"
        assert d.result is None
        assert d.ttl_minutes == 120
        assert d.source_signals == ()

    def test_created_at_auto_generated(self):
        d = Directive(id="x", title="t", rationale="r")
        # Should be a valid ISO timestamp
        parsed = datetime.fromisoformat(d.created_at)
        assert parsed.tzinfo is not None


# ── 2. Category mappings ─────────────────────────────────────────


class TestCategoryMappings:
    def test_category_agents_keys(self):
        expected = {"trading", "research", "learning", "automation", "product", "health", "general"}
        assert set(_CATEGORY_AGENTS.keys()) == expected

    def test_category_risk_keys(self):
        expected = {"trading", "research", "learning", "automation", "product", "health", "general"}
        assert set(_CATEGORY_RISK.keys()) == expected

    def test_trading_is_high_risk(self):
        assert _CATEGORY_RISK["trading"] == "high"

    def test_research_is_low_risk(self):
        assert _CATEGORY_RISK["research"] == "low"

    def test_trading_agents_include_swarm(self):
        assert "swarm" in _CATEGORY_AGENTS["trading"]

    def test_all_categories_have_agents(self):
        for cat, agents in _CATEGORY_AGENTS.items():
            assert len(agents) > 0, f"Category {cat} has no agents"

    def test_category_agents_and_risk_have_same_keys(self):
        assert set(_CATEGORY_AGENTS.keys()) == set(_CATEGORY_RISK.keys())


# ── 3. Lifecycle ─────────────────────────────────────────────────


class TestLifecycle:
    def test_start_creates_tables(self, directive_engine):
        tables = directive_engine.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        assert "directives" in table_names

    def test_start_creates_indexes(self, directive_engine):
        indexes = directive_engine.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        idx_names = {r["name"] for r in indexes}
        assert "idx_dir_status" in idx_names
        assert "idx_dir_created" in idx_names
        assert "idx_dir_category" in idx_names

    def test_stop_closes_connection(self, tmp_path, monkeypatch):
        monkeypatch.setattr(de_mod, "DIRECTIVE_DB", tmp_path / "directives.db")
        engine = DirectiveEngine()
        engine.start()
        assert engine._conn is not None
        engine.stop()
        assert engine._conn is None

    def test_conn_property_raises_when_not_started(self):
        engine = DirectiveEngine()
        with pytest.raises(RuntimeError, match="not started"):
            _ = engine.conn


# ── 4. Storage and retrieval ─────────────────────────────────────


class TestStorageAndRetrieval:
    def test_store_and_get_directive(self, directive_engine):
        d = _make_directive(id="dir_store1")
        directive_engine._store_directive(d)
        retrieved = directive_engine._get_directive("dir_store1")
        assert retrieved.id == "dir_store1"
        assert retrieved.title == "Test directive"
        assert retrieved.rationale == "Testing rationale"
        assert retrieved.priority == 5
        assert retrieved.category == "general"
        assert retrieved.assigned_agents == ("researcher",)

    def test_get_missing_directive_returns_fallback(self, directive_engine):
        d = directive_engine._get_directive("nonexistent")
        assert d.id == "nonexistent"
        assert d.title == "unknown"
        assert d.status == "failed"

    def test_store_preserves_source_signals(self, directive_engine):
        d = _make_directive(id="dir_signals", source_signals=("market_intel", "chain_depth:1"))
        directive_engine._store_directive(d)
        retrieved = directive_engine._get_directive("dir_signals")
        assert retrieved.source_signals == ("market_intel", "chain_depth:1")

    def test_duplicate_insert_ignored(self, directive_engine):
        d = _make_directive(id="dir_dup")
        directive_engine._store_directive(d)
        # Store again with different title — should be ignored (INSERT OR IGNORE)
        d2 = _make_directive(id="dir_dup", title="Different title")
        directive_engine._store_directive(d2)
        retrieved = directive_engine._get_directive("dir_dup")
        assert retrieved.title == "Test directive"


# ── 5. Text overlap ─────────────────────────────────────────────


class TestTextOverlap:
    def test_identical_strings(self):
        assert DirectiveEngine._text_overlap("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert DirectiveEngine._text_overlap("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        result = DirectiveEngine._text_overlap("the quick brown fox", "the slow brown dog")
        # Shared: {"the", "brown"} = 2, Union: {"the", "quick", "brown", "fox", "slow", "dog"} = 6
        assert abs(result - 2 / 6) < 0.001

    def test_empty_string_returns_zero(self):
        assert DirectiveEngine._text_overlap("", "hello") == 0.0
        assert DirectiveEngine._text_overlap("hello", "") == 0.0
        assert DirectiveEngine._text_overlap("", "") == 0.0

    def test_case_insensitive(self):
        assert DirectiveEngine._text_overlap("Hello World", "hello world") == 1.0


# ── 6. Chain depth ───────────────────────────────────────────────


class TestChainDepth:
    def test_no_chain_depth(self):
        d = _make_directive(source_signals=())
        assert DirectiveEngine._get_chain_depth(d) == 0

    def test_chain_depth_present(self):
        d = _make_directive(source_signals=("market_intel", "chain_depth:2"))
        assert DirectiveEngine._get_chain_depth(d) == 2

    def test_chain_depth_first_match(self):
        d = _make_directive(source_signals=("chain_depth:1", "chain_depth:3"))
        assert DirectiveEngine._get_chain_depth(d) == 1

    def test_chain_depth_invalid_value(self):
        d = _make_directive(source_signals=("chain_depth:abc",))
        assert DirectiveEngine._get_chain_depth(d) == 0

    def test_chain_depth_missing_value(self):
        d = _make_directive(source_signals=("chain_depth:",))
        # split(":")[1] is "" → int("") → ValueError → returns 0
        assert DirectiveEngine._get_chain_depth(d) == 0

    def test_unrelated_signals_ignored(self):
        d = _make_directive(source_signals=("stalled_goal", "task_backlog"))
        assert DirectiveEngine._get_chain_depth(d) == 0


# ── 7. Filtering / deduplication ─────────────────────────────────


class TestFilterDirectives:
    def test_filters_duplicates(self, directive_engine):
        # Store a directive to establish "recent" titles
        existing = _make_directive(id="dir_existing", title="Evaluate trading opportunities from market intel")
        directive_engine._store_directive(existing)

        # New directive with similar title should be filtered out
        candidate = _make_directive(id="dir_new", title="Evaluate trading opportunities from market intel")
        result = directive_engine._filter_directives([candidate])
        assert len(result) == 0

    def test_keeps_unique_directives(self, directive_engine):
        existing = _make_directive(id="dir_existing", title="Analyze market data")
        directive_engine._store_directive(existing)

        candidate = _make_directive(id="dir_unique", title="Build new automation pipeline")
        result = directive_engine._filter_directives([candidate])
        assert len(result) == 1
        assert result[0].id == "dir_unique"

    def test_empty_input_returns_empty(self, directive_engine):
        result = directive_engine._filter_directives([])
        assert result == []


# ── 8. Expiration ────────────────────────────────────────────────


class TestExpireDirectives:
    def test_expire_old_proposed(self, directive_engine):
        old_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        d = _make_directive(id="dir_old", status="proposed", ttl_minutes=120, created_at=old_time)
        directive_engine._store_directive(d)

        expired = directive_engine._expire_directives()
        assert expired == 1

        retrieved = directive_engine._get_directive("dir_old")
        assert retrieved.status == "expired"

    def test_no_expire_recent(self, directive_engine):
        d = _make_directive(id="dir_recent", status="proposed", ttl_minutes=120)
        directive_engine._store_directive(d)

        expired = directive_engine._expire_directives()
        assert expired == 0

        retrieved = directive_engine._get_directive("dir_recent")
        assert retrieved.status == "proposed"

    def test_expire_old_executing(self, directive_engine):
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        d = _make_directive(id="dir_exec_old", status="executing", ttl_minutes=60, created_at=old_time)
        directive_engine._store_directive(d)

        expired = directive_engine._expire_directives()
        assert expired == 1

    def test_completed_not_expired(self, directive_engine):
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        d = _make_directive(id="dir_comp", status="proposed", created_at=old_time)
        directive_engine._store_directive(d)
        directive_engine._update_directive("dir_comp", status="completed")

        expired = directive_engine._expire_directives()
        assert expired == 0


# ── 9. Rule-based generation ────────────────────────────────────


class TestGenerateRuleBased:
    def test_stalled_goals_generate_unblock(self, directive_engine):
        snapshot = {
            "stalled_goals": [{"title": "Revenue target Q1", "days_inactive": 14}],
            "task_queue": {},
            "market_intel": [],
        }
        directives = directive_engine._generate_rule_based(snapshot)
        assert len(directives) >= 1
        assert "Unblock" in directives[0].title
        assert directives[0].category == "automation"
        assert directives[0].priority == 3
        assert "stalled_goal" in directives[0].source_signals

    def test_task_backlog_generates_drain(self, directive_engine):
        snapshot = {
            "stalled_goals": [],
            "task_queue": {"by_status": {"pending": 10}},
            "market_intel": [],
        }
        directives = directive_engine._generate_rule_based(snapshot)
        assert any("Drain" in d.title for d in directives)
        drain = [d for d in directives if "Drain" in d.title][0]
        assert drain.category == "automation"
        assert "task_backlog" in drain.source_signals

    def test_market_intel_generates_trading(self, directive_engine):
        snapshot = {
            "stalled_goals": [],
            "task_queue": {},
            "market_intel": ["BTC up 5%"],
        }
        directives = directive_engine._generate_rule_based(snapshot)
        assert any(d.category == "trading" for d in directives)
        trading = [d for d in directives if d.category == "trading"][0]
        assert "market_intel" in trading.source_signals

    def test_empty_snapshot_generates_nothing(self, directive_engine):
        snapshot = {"stalled_goals": [], "task_queue": {}, "market_intel": []}
        directives = directive_engine._generate_rule_based(snapshot)
        assert directives == []

    def test_low_pending_no_drain(self, directive_engine):
        snapshot = {
            "stalled_goals": [],
            "task_queue": {"by_status": {"pending": 3}},
            "market_intel": [],
        }
        directives = directive_engine._generate_rule_based(snapshot)
        assert not any("Drain" in d.title for d in directives)

    def test_combined_signals(self, directive_engine):
        snapshot = {
            "stalled_goals": [{"title": "Goal A", "days_inactive": 7}],
            "task_queue": {"by_status": {"pending": 20}},
            "market_intel": ["ETH momentum signal"],
        }
        directives = directive_engine._generate_rule_based(snapshot)
        assert len(directives) == 3


# ── 10. Stats ────────────────────────────────────────────────────


class TestStats:
    def test_empty_stats(self, directive_engine):
        s = directive_engine.stats()
        assert s["total_directives"] == 0
        assert s["completed"] == 0
        assert s["failed"] == 0
        assert s["active"] == 0
        assert s["cycles"] == 0
        assert s["success_rate"] == 0.0
        assert s["by_category"] == {}

    def test_stats_with_data(self, directive_engine):
        d1 = _make_directive(id="dir_s1", category="trading", status="proposed")
        d2 = _make_directive(id="dir_s2", category="research", status="proposed")
        directive_engine._store_directive(d1)
        directive_engine._store_directive(d2)
        directive_engine._update_directive("dir_s2", status="completed")

        s = directive_engine.stats()
        assert s["total_directives"] == 2
        assert s["completed"] == 1
        assert s["active"] == 1
        assert s["success_rate"] == 0.5
        assert s["by_category"]["trading"] == 1
        assert s["by_category"]["research"] == 1


# ── 11. Active count and recent titles ───────────────────────────


class TestActiveCountAndRecentTitles:
    def test_active_count_empty(self, directive_engine):
        assert directive_engine._get_active_count() == 0

    def test_active_count_mixed(self, directive_engine):
        directive_engine._store_directive(_make_directive(id="d1", status="proposed"))
        directive_engine._store_directive(_make_directive(id="d2", status="proposed"))
        directive_engine._store_directive(_make_directive(id="d3", status="proposed"))
        directive_engine._update_directive("d2", status="completed")
        directive_engine._update_directive("d3", status="failed")

        assert directive_engine._get_active_count() == 1

    def test_recent_titles_empty(self, directive_engine):
        assert directive_engine._get_recent_titles() == []

    def test_recent_titles_returns_correct(self, directive_engine):
        directive_engine._store_directive(_make_directive(id="d1", title="Alpha"))
        directive_engine._store_directive(_make_directive(id="d2", title="Beta"))
        titles = directive_engine._get_recent_titles(limit=10)
        assert set(titles) == {"Alpha", "Beta"}

    def test_recent_titles_respects_limit(self, directive_engine):
        for i in range(5):
            directive_engine._store_directive(_make_directive(id=f"d{i}", title=f"Title {i}"))
        titles = directive_engine._get_recent_titles(limit=2)
        assert len(titles) == 2


# ── 12. Directive history and active directives ──────────────────


class TestHistoryAndActive:
    def test_get_history_empty(self, directive_engine):
        assert directive_engine.get_history() == []

    def test_get_history_returns_dicts(self, directive_engine):
        directive_engine._store_directive(_make_directive(id="h1", title="History item"))
        history = directive_engine.get_history(limit=10)
        assert len(history) == 1
        assert isinstance(history[0], dict)
        assert history[0]["id"] == "h1"
        assert history[0]["title"] == "History item"

    def test_get_history_respects_limit(self, directive_engine):
        for i in range(10):
            directive_engine._store_directive(_make_directive(id=f"h{i}", title=f"Item {i}"))
        assert len(directive_engine.get_history(limit=3)) == 3

    def test_get_active_directives_only_active(self, directive_engine):
        directive_engine._store_directive(_make_directive(id="a1", status="proposed"))
        directive_engine._store_directive(_make_directive(id="a2", status="proposed"))
        directive_engine._store_directive(_make_directive(id="a3", status="proposed"))
        directive_engine._update_directive("a2", status="completed")
        directive_engine._update_directive("a3", status="failed")

        active = directive_engine.get_active_directives()
        assert len(active) == 1
        assert active[0]["id"] == "a1"

    def test_active_directives_sorted_by_priority(self, directive_engine):
        directive_engine._store_directive(_make_directive(id="p9", priority=9, status="proposed"))
        directive_engine._store_directive(_make_directive(id="p1", priority=1, status="proposed"))
        directive_engine._store_directive(_make_directive(id="p5", priority=5, status="proposed"))

        active = directive_engine.get_active_directives()
        priorities = [d["priority"] for d in active]
        assert priorities == sorted(priorities)


# ── 13. Update directive ─────────────────────────────────────────


class TestUpdateDirective:
    def test_update_status(self, directive_engine):
        directive_engine._store_directive(_make_directive(id="u1"))
        updated = directive_engine._update_directive("u1", status="completed")
        assert updated.status == "completed"

    def test_update_result(self, directive_engine):
        directive_engine._store_directive(_make_directive(id="u2"))
        updated = directive_engine._update_directive("u2", result="Success output")
        assert updated.result == "Success output"

    def test_update_multiple_fields(self, directive_engine):
        directive_engine._store_directive(_make_directive(id="u3"))
        ts = _now_iso()
        updated = directive_engine._update_directive(
            "u3", status="executing", executed_at=ts,
        )
        assert updated.status == "executing"
        assert updated.executed_at == ts

    def test_update_nonexistent_returns_fallback(self, directive_engine):
        result = directive_engine._update_directive("missing", status="completed")
        assert result.id == "missing"
        assert result.title == "unknown"


# ── 14. Row conversion ──────────────────────────────────────────


class TestRowConversion:
    def test_row_to_directive_roundtrip(self, directive_engine):
        original = _make_directive(
            id="rt1",
            assigned_agents=("swarm", "analyst"),
            source_signals=("market_intel", "chain_depth:1"),
        )
        directive_engine._store_directive(original)
        row = directive_engine.conn.execute(
            "SELECT * FROM directives WHERE id = ?", ("rt1",)
        ).fetchone()

        converted = directive_engine._row_to_directive(row)
        assert converted.id == original.id
        assert converted.title == original.title
        assert converted.assigned_agents == original.assigned_agents
        assert converted.source_signals == original.source_signals
        assert converted.priority == original.priority
        assert converted.category == original.category

    def test_row_to_dict_roundtrip(self, directive_engine):
        original = _make_directive(
            id="rd1",
            assigned_agents=("coder", "builder"),
        )
        directive_engine._store_directive(original)
        row = directive_engine.conn.execute(
            "SELECT * FROM directives WHERE id = ?", ("rd1",)
        ).fetchone()

        d = directive_engine._row_to_dict(row)
        assert isinstance(d, dict)
        assert d["id"] == "rd1"
        assert d["assigned_agents"] == ["coder", "builder"]
        assert d["status"] == "proposed"

    def test_row_to_dict_handles_null_agents(self, directive_engine):
        directive_engine.conn.execute(
            "INSERT INTO directives (id, title, created_at, assigned_agents, source_signals) "
            "VALUES (?, ?, ?, ?, ?)",
            ("null1", "Null test", _now_iso(), None, None),
        )
        directive_engine.conn.commit()
        row = directive_engine.conn.execute(
            "SELECT * FROM directives WHERE id = ?", ("null1",)
        ).fetchone()

        d = directive_engine._row_to_dict(row)
        assert d["assigned_agents"] == []

        converted = directive_engine._row_to_directive(row)
        assert converted.assigned_agents == ()
        assert converted.source_signals == ()


# ── 15. Directive history summary ────────────────────────────────


class TestDirectiveHistorySummary:
    def test_empty_history_summary(self, directive_engine):
        summary = directive_engine._get_directive_history_summary()
        assert summary == "No directive history yet."

    def test_history_summary_with_data(self, directive_engine):
        d1 = _make_directive(id="hs1", category="trading", status="proposed")
        d2 = _make_directive(id="hs2", category="research", status="proposed")
        d3 = _make_directive(id="hs3", category="trading", status="proposed")
        directive_engine._store_directive(d1)
        directive_engine._store_directive(d2)
        directive_engine._store_directive(d3)
        directive_engine._update_directive("hs1", status="completed")
        directive_engine._update_directive("hs2", status="failed")
        directive_engine._update_directive("hs3", status="completed")

        summary = directive_engine._get_directive_history_summary()
        assert "2 completed" in summary
        assert "1 failed" in summary
        assert "trading" in summary
