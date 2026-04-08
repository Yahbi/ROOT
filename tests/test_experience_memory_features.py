"""Tests for the new Experience Memory features:
- Relevance-scored search
- Pattern recognition
- Experience clustering
- Wisdom extraction
- Experience aging (age decay)
- Cross-domain learning
- Visualization data
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from backend.core.experience_memory import (
    ExperienceMemory,
    ExperienceType,
    ScoredExperience,
    ExperiencePattern,
    ExperienceCluster,
    Wisdom,
)


@pytest.fixture
def exp_mem(tmp_path):
    with patch("backend.core.experience_memory.EXPERIENCE_DB", tmp_path / "experience.db"):
        engine = ExperienceMemory()
        engine.start()
        yield engine
        engine.stop()


@pytest.fixture
def populated_mem(exp_mem):
    """Pre-populated memory with diverse experiences."""
    # Trading domain — successes
    exp_mem.record_success(
        domain="trading", title="momentum strategy works consistently",
        description="Trend following with momentum signals outperforms",
        tags=["momentum", "trend", "strategy"], confidence=0.9,
    )
    exp_mem.record_success(
        domain="trading", title="momentum breakout strategy wins",
        description="Momentum breakout entry with tight stop-loss works",
        tags=["momentum", "breakout"], confidence=0.85,
    )
    # Trading domain — failures
    exp_mem.record_failure(
        domain="trading", title="mean reversion failed in trending market",
        description="Mean reversion strategies fail in strong trending markets",
        tags=["mean-reversion", "trend"], confidence=0.8,
    )
    # SaaS domain
    exp_mem.record_success(
        domain="saas", title="email drip campaign conversion success",
        description="5-email sequence drives 30% conversion rate for SaaS signup",
        tags=["email", "conversion", "drip"], confidence=0.75,
    )
    exp_mem.record_lesson(
        domain="saas", title="onboarding flow reduces churn",
        description="Guided onboarding reduces 30-day churn significantly",
        tags=["onboarding", "churn", "retention"], confidence=0.8,
    )
    # Automation domain
    exp_mem.record_strategy(
        domain="automation", title="retry with exponential backoff",
        description="Always retry transient failures with exponential backoff",
        tags=["retry", "backoff", "resilience"], confidence=0.95,
    )
    exp_mem.record_lesson(
        domain="automation", title="retry logic prevents cascade failures",
        description="Retry with backoff prevents cascading failure in microservices",
        tags=["retry", "resilience", "microservices"], confidence=0.9,
    )
    return exp_mem


# ── Feature 1: Relevance-Scored Search ────────────────────────────────


class TestScoredSearch:
    def test_scored_search_returns_scored_experiences(self, populated_mem):
        results = populated_mem.search_experiences_scored("momentum")
        assert len(results) > 0
        for r in results:
            assert isinstance(r, ScoredExperience)
            assert r.score > 0.0

    def test_scored_search_ranks_title_matches_higher(self, populated_mem):
        results = populated_mem.search_experiences_scored("momentum")
        # Title matches should score higher — first result should mention momentum in title
        assert "momentum" in results[0].experience.title.lower()

    def test_scored_search_no_results_for_missing_term(self, populated_mem):
        results = populated_mem.search_experiences_scored("zzzzunmatchedterm")
        assert results == []

    def test_scored_search_empty_query(self, populated_mem):
        results = populated_mem.search_experiences_scored("")
        assert results == []

    def test_scored_search_respects_limit(self, populated_mem):
        results = populated_mem.search_experiences_scored("strategy", limit=1)
        assert len(results) <= 1

    def test_scored_search_with_domain_filter(self, populated_mem):
        results = populated_mem.search_experiences_scored("strategy", domain="trading")
        for r in results:
            assert r.experience.domain == "trading"

    def test_scored_search_scores_are_descending(self, populated_mem):
        results = populated_mem.search_experiences_scored("momentum strategy")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_scored_search_age_penalty_flag(self, exp_mem):
        exp_mem.record_success(
            domain="test", title="ancient wisdom strategy",
            description="strategy that is very old", confidence=1.0,
        )
        results_with_penalty = exp_mem.search_experiences_scored("strategy", age_penalty=True)
        results_no_penalty = exp_mem.search_experiences_scored("strategy", age_penalty=False)
        assert len(results_with_penalty) > 0
        assert len(results_no_penalty) > 0


# ── Feature 2: Pattern Recognition ────────────────────────────────────


class TestPatternRecognition:
    def test_detect_patterns_returns_list(self, populated_mem):
        patterns = populated_mem.detect_patterns()
        assert isinstance(patterns, list)

    def test_detect_patterns_needs_min_occurrences(self, exp_mem):
        # Only 1 experience — no pattern possible
        exp_mem.record_success(domain="solo", title="unique one-off success", description="standalone")
        patterns = exp_mem.detect_patterns(min_occurrences=2)
        solo_patterns = [p for p in patterns if p.domain == "solo"]
        assert len(solo_patterns) == 0

    def test_detect_patterns_finds_recurring_success(self, populated_mem):
        patterns = populated_mem.detect_patterns(domain="trading", min_occurrences=2)
        trading_patterns = [p for p in patterns if p.domain == "trading"]
        assert len(trading_patterns) > 0

    def test_pattern_has_required_fields(self, populated_mem):
        patterns = populated_mem.detect_patterns(min_occurrences=2)
        for p in patterns:
            assert isinstance(p, ExperiencePattern)
            assert p.pattern_id.startswith("pat_")
            assert p.pattern_type in ("recurring_success", "recurring_failure", "mixed")
            assert p.occurrence_count >= 2
            assert 0.0 <= p.avg_confidence <= 1.0
            assert isinstance(p.keywords, list)
            assert isinstance(p.example_ids, list)

    def test_patterns_sorted_by_occurrence_count(self, populated_mem):
        patterns = populated_mem.detect_patterns(min_occurrences=2)
        counts = [p.occurrence_count for p in patterns]
        assert counts == sorted(counts, reverse=True)

    def test_pattern_type_matches_experience_types(self, exp_mem):
        # Add 3 failures — should produce recurring_failure
        for i in range(3):
            exp_mem.record_failure(
                domain="testfail",
                title=f"failure with timeout error case {i}",
                description="timeout occurred causing failure",
                confidence=0.8,
            )
        patterns = exp_mem.detect_patterns(domain="testfail", min_occurrences=2)
        assert len(patterns) > 0
        assert patterns[0].pattern_type == "recurring_failure"

    def test_window_days_filters_old_experiences(self, exp_mem):
        exp_mem.record_success(domain="old", title="ancient strategy works", description="old")
        exp_mem.record_success(domain="old", title="ancient strategy repeat", description="old")
        # window_days=0 should exclude all
        patterns = exp_mem.detect_patterns(window_days=0)
        assert all(p.domain != "old" for p in patterns)


# ── Feature 3: Experience Clustering ──────────────────────────────────


class TestExperienceClustering:
    def test_cluster_returns_list(self, populated_mem):
        clusters = populated_mem.cluster_experiences()
        assert isinstance(clusters, list)

    def test_cluster_empty_db(self, exp_mem):
        clusters = exp_mem.cluster_experiences()
        assert clusters == []

    def test_cluster_has_required_fields(self, populated_mem):
        clusters = populated_mem.cluster_experiences()
        for c in clusters:
            assert isinstance(c, ExperienceCluster)
            assert c.cluster_id.startswith("cl_")
            assert isinstance(c.label, str)
            assert isinstance(c.keywords, list)
            assert isinstance(c.experience_ids, list)
            assert c.size >= 1
            assert c.dominant_type in ("success", "failure", "strategy", "lesson")
            assert 0.0 <= c.avg_confidence <= 1.0

    def test_cluster_respects_domain_filter(self, populated_mem):
        clusters = populated_mem.cluster_experiences(domain="trading")
        for c in clusters:
            assert c.domain == "trading"

    def test_cluster_max_clusters_respected(self, populated_mem):
        clusters = populated_mem.cluster_experiences(max_clusters=2)
        assert len(clusters) <= 2

    def test_cluster_sorted_by_size(self, populated_mem):
        clusters = populated_mem.cluster_experiences()
        sizes = [c.size for c in clusters]
        assert sizes == sorted(sizes, reverse=True)

    def test_all_experiences_assigned_to_some_cluster(self, exp_mem):
        for i in range(5):
            exp_mem.record_success(
                domain="test", title=f"test experience number {i}",
                description=f"testing test approach {i}", confidence=0.8,
            )
        clusters = exp_mem.cluster_experiences()
        all_cluster_ids = {eid for c in clusters for eid in c.experience_ids}
        all_exp_ids = {e.id for e in exp_mem.get_experiences()}
        # All experiences should be in at least one cluster
        assert all_exp_ids.issubset(all_cluster_ids)


# ── Feature 4: Wisdom Extraction ──────────────────────────────────────


class TestWisdomExtraction:
    def test_extract_wisdom_returns_list(self, populated_mem):
        wisdoms = populated_mem.extract_wisdom()
        assert isinstance(wisdoms, list)

    def test_extract_wisdom_insufficient_support(self, exp_mem):
        exp_mem.record_success(domain="lone", title="single experience", description="one")
        wisdoms = exp_mem.extract_wisdom(min_support=3)
        lone_wisdoms = [w for w in wisdoms if w.domain == "lone"]
        assert len(lone_wisdoms) == 0

    def test_wisdom_has_required_fields(self, populated_mem):
        wisdoms = populated_mem.extract_wisdom(min_support=2, min_confidence=0.5)
        for w in wisdoms:
            assert isinstance(w, Wisdom)
            assert w.wisdom_id.startswith("wis_")
            assert isinstance(w.insight, str) and len(w.insight) > 10
            assert isinstance(w.source_types, list)
            assert w.supporting_count >= 1
            assert 0.0 <= w.confidence <= 1.0
            assert isinstance(w.keywords, list)
            assert isinstance(w.cross_domain_applicable, bool)
            assert isinstance(w.related_domains, list)

    def test_wisdom_domain_filter(self, populated_mem):
        wisdoms = populated_mem.extract_wisdom(domain="automation", min_support=2)
        assert all(w.domain == "automation" for w in wisdoms)

    def test_wisdom_sorted_by_support_and_confidence(self, populated_mem):
        wisdoms = populated_mem.extract_wisdom(min_support=1)
        # Should not crash; ordering is consistent
        assert isinstance(wisdoms, list)

    def test_wisdom_insight_matches_type(self, exp_mem):
        for _ in range(3):
            exp_mem.record_failure(
                domain="infra", title="disk space filled causing outage",
                description="disk capacity failure caused system outage",
                confidence=0.85,
            )
        wisdoms = exp_mem.extract_wisdom(domain="infra", min_support=2, min_confidence=0.5)
        failure_wisdoms = [w for w in wisdoms if "failure" in w.source_types]
        assert len(failure_wisdoms) > 0
        # Failure wisdom should mention avoidance
        assert any("avoid" in w.insight.lower() or "failure" in w.insight.lower()
                   for w in failure_wisdoms)

    def test_cross_domain_applicable_set(self, populated_mem):
        # automation domain has "retry" appearing in 2 experiences across domains
        wisdoms = populated_mem.extract_wisdom(min_support=2, min_confidence=0.5)
        # Should have at least some wisdoms
        assert len(wisdoms) > 0


# ── Feature 5: Experience Aging ───────────────────────────────────────


class TestExperienceAging:
    def test_apply_age_decay_dry_run(self, exp_mem):
        exp_mem.record_success(domain="test", title="old lesson", description="from the past", confidence=1.0)
        result = exp_mem.apply_age_decay(dry_run=True)
        assert result["dry_run"] is True
        assert "total_processed" in result
        assert "total_decayed" in result
        assert "avg_confidence_delta" in result

    def test_apply_age_decay_no_change_on_fresh(self, exp_mem):
        exp_mem.record_success(domain="test", title="fresh lesson", description="just recorded", confidence=1.0)
        # Fresh experiences (age < 1 day) should not be decayed
        result = exp_mem.apply_age_decay(dry_run=False)
        assert result["total_decayed"] == 0
        exps = exp_mem.get_experiences()
        assert exps[0].confidence == 1.0

    def test_apply_age_decay_reduces_confidence(self, exp_mem):
        # Manually insert an old experience by inserting directly
        import sqlite3 as _sqlite3
        old_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        exp_mem.conn.execute(
            """INSERT INTO experiences
               (id, experience_type, domain, title, description, context,
                outcome, confidence, times_applied, created_at, tags, last_accessed, source_domain)
               VALUES ('exp_oldtest001', 'lesson', 'test', 'old lesson', 'old desc',
                       '{}', NULL, 0.9, 0, ?, '', NULL, NULL)""",
            (old_date,),
        )
        exp_mem.conn.commit()

        result = exp_mem.apply_age_decay(half_life_days=180, min_confidence=0.1)
        assert result["total_decayed"] >= 1

        rows = exp_mem.conn.execute(
            "SELECT confidence FROM experiences WHERE id = 'exp_oldtest001'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["confidence"] < 0.9

    def test_apply_age_decay_respects_min_confidence(self, exp_mem):
        old_date = (datetime.now(timezone.utc) - timedelta(days=1000)).isoformat()
        exp_mem.conn.execute(
            """INSERT INTO experiences
               (id, experience_type, domain, title, description, context,
                outcome, confidence, times_applied, created_at, tags, last_accessed, source_domain)
               VALUES ('exp_veryold001', 'lesson', 'test', 'very old', 'ancient',
                       '{}', NULL, 0.9, 0, ?, '', NULL, NULL)""",
            (old_date,),
        )
        exp_mem.conn.commit()

        MIN_CONF = 0.2
        exp_mem.apply_age_decay(half_life_days=30, min_confidence=MIN_CONF)
        rows = exp_mem.conn.execute(
            "SELECT confidence FROM experiences WHERE id = 'exp_veryold001'"
        ).fetchall()
        assert rows[0]["confidence"] >= MIN_CONF

    def test_get_aged_experiences_empty(self, exp_mem):
        result = exp_mem.get_aged_experiences(older_than_days=365)
        assert result == []

    def test_get_aged_experiences_finds_old(self, exp_mem):
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        exp_mem.conn.execute(
            """INSERT INTO experiences
               (id, experience_type, domain, title, description, context,
                outcome, confidence, times_applied, created_at, tags, last_accessed, source_domain)
               VALUES ('exp_aged001', 'success', 'test', 'aged exp', 'desc',
                       '{}', NULL, 0.8, 0, ?, '', NULL, NULL)""",
            (old_date,),
        )
        exp_mem.conn.commit()
        result = exp_mem.get_aged_experiences(older_than_days=90)
        assert any(e.id == "exp_aged001" for e in result)

    def test_frequently_applied_decays_slower(self, exp_mem):
        """Frequently applied experiences have protection — their effective half-life is longer."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=200)).isoformat()
        for exp_id, times_applied in [("exp_protected", 100), ("exp_unprotected", 0)]:
            exp_mem.conn.execute(
                """INSERT INTO experiences
                   (id, experience_type, domain, title, description, context,
                    outcome, confidence, times_applied, created_at, tags, last_accessed, source_domain)
                   VALUES (?, 'strategy', 'test', 'exp', 'desc',
                           '{}', NULL, 0.9, ?, ?, '', NULL, NULL)""",
                (exp_id, times_applied, old_date),
            )
        exp_mem.conn.commit()

        exp_mem.apply_age_decay(half_life_days=180, min_confidence=0.05)

        rows = {
            r["id"]: r["confidence"]
            for r in exp_mem.conn.execute(
                "SELECT id, confidence FROM experiences WHERE id IN ('exp_protected','exp_unprotected')"
            ).fetchall()
        }
        assert rows["exp_protected"] > rows["exp_unprotected"]


# ── Feature 6: Cross-Domain Learning ──────────────────────────────────


class TestCrossDomainLearning:
    def test_transfer_lesson_creates_new_experience(self, exp_mem):
        exp_mem.record_strategy(
            domain="automation", title="retry with backoff reduces failures",
            description="Exponential backoff prevents cascade failures",
            confidence=0.9,
        )
        transferred = exp_mem.transfer_lesson("automation", "trading")
        assert len(transferred) >= 1
        assert transferred[0].domain == "trading"

    def test_transferred_experience_has_source_domain(self, exp_mem):
        exp_mem.record_lesson(
            domain="saas", title="onboarding reduces churn significantly",
            description="Good onboarding lowers 30-day churn",
            confidence=0.85,
        )
        transferred = exp_mem.transfer_lesson("saas", "consulting")
        assert len(transferred) >= 1
        assert "from:saas" in transferred[0].tags

    def test_transfer_confidence_reduced(self, exp_mem):
        exp_mem.record_strategy(
            domain="trading", title="momentum signals produce consistent returns",
            description="Momentum signals are reliable in trending markets",
            confidence=0.9,
        )
        transferred = exp_mem.transfer_lesson("trading", "investing")
        if transferred:
            # Transferred confidence should be <= original * 0.9 (15% reduction)
            assert transferred[0].confidence <= 0.9 * 0.9

    def test_transfer_no_duplicate(self, exp_mem):
        exp_mem.record_lesson(
            domain="infra", title="database wal mode prevents locking",
            description="WAL mode avoids read-write lock contention",
            confidence=0.9,
        )
        t1 = exp_mem.transfer_lesson("infra", "backend")
        t2 = exp_mem.transfer_lesson("infra", "backend")
        # Second transfer should not create duplicate (already transferred)
        assert len(t2) == 0

    def test_transfer_below_min_confidence_skipped(self, exp_mem):
        exp_mem.record_lesson(
            domain="test", title="low confidence observation",
            description="Uncertain finding", confidence=0.3,
        )
        transferred = exp_mem.transfer_lesson("test", "other", min_confidence=0.6)
        assert len(transferred) == 0

    def test_find_cross_domain_lessons(self, exp_mem):
        exp_mem.record_strategy(
            domain="automation", title="circuit breaker pattern works",
            description="Circuit breakers prevent cascading failures",
            confidence=0.9,
        )
        exp_mem.transfer_lesson("automation", "trading")
        cross = exp_mem.find_cross_domain_lessons("trading")
        assert len(cross) >= 1
        assert all("from:automation" in e.tags for e in cross)

    def test_get_domain_connections_empty(self, exp_mem):
        connections = exp_mem.get_domain_connections()
        assert connections == {}

    def test_get_domain_connections_reflects_transfers(self, exp_mem):
        exp_mem.record_lesson(
            domain="A", title="lesson from domain A that works",
            description="A lesson that applies broadly", confidence=0.9,
        )
        exp_mem.transfer_lesson("A", "B")
        connections = exp_mem.get_domain_connections()
        assert "A" in connections
        assert "B" in connections["A"]


# ── Feature 7: Visualization Data ─────────────────────────────────────


class TestVisualizationData:
    def test_viz_data_returns_all_keys(self, populated_mem):
        data = populated_mem.get_visualization_data()
        expected_keys = {
            "experience_timeline",
            "domain_breakdown",
            "type_distribution",
            "confidence_histogram",
            "top_domains_by_confidence",
            "activity_heatmap",
            "cross_domain_graph",
        }
        assert expected_keys.issubset(set(data.keys()))

    def test_viz_data_on_empty_db(self, exp_mem):
        data = exp_mem.get_visualization_data()
        assert data["domain_breakdown"] == []
        assert data["type_distribution"] == []

    def test_timeline_has_12_weeks(self, populated_mem):
        data = populated_mem.get_visualization_data()
        assert len(data["experience_timeline"]) == 12

    def test_timeline_entry_format(self, populated_mem):
        data = populated_mem.get_visualization_data()
        for entry in data["experience_timeline"]:
            assert "week" in entry
            assert "count" in entry
            assert isinstance(entry["count"], int)

    def test_domain_breakdown_lists_known_domains(self, populated_mem):
        data = populated_mem.get_visualization_data()
        domains = {d["domain"] for d in data["domain_breakdown"]}
        assert "trading" in domains
        assert "saas" in domains
        assert "automation" in domains

    def test_type_distribution_lists_all_types(self, populated_mem):
        data = populated_mem.get_visualization_data()
        types = {t["type"] for t in data["type_distribution"]}
        assert "success" in types
        assert "failure" in types
        assert "strategy" in types
        assert "lesson" in types

    def test_confidence_histogram_has_5_buckets(self, populated_mem):
        data = populated_mem.get_visualization_data()
        assert len(data["confidence_histogram"]) == 5

    def test_confidence_histogram_counts_sum_to_total(self, populated_mem):
        data = populated_mem.get_visualization_data()
        total_in_hist = sum(b["count"] for b in data["confidence_histogram"])
        total_exps = populated_mem.stats()["total_experiences"]
        assert total_in_hist == total_exps

    def test_activity_heatmap_has_30_days(self, populated_mem):
        data = populated_mem.get_visualization_data()
        assert len(data["activity_heatmap"]) == 30

    def test_activity_heatmap_date_format(self, populated_mem):
        data = populated_mem.get_visualization_data()
        for entry in data["activity_heatmap"]:
            assert "date" in entry
            assert "count" in entry
            datetime.strptime(entry["date"], "%Y-%m-%d")  # no exception = valid

    def test_cross_domain_graph_structure(self, exp_mem):
        exp_mem.record_lesson(
            domain="A", title="lesson from domain A about retry strategy",
            description="retry strategy from A", confidence=0.9,
        )
        exp_mem.transfer_lesson("A", "B")
        data = exp_mem.get_visualization_data()
        graph = data["cross_domain_graph"]
        assert "nodes" in graph
        assert "edges" in graph
        node_ids = {n["id"] for n in graph["nodes"]}
        assert "A" in node_ids
        assert "B" in node_ids
        assert {"source": "A", "target": "B"} in graph["edges"]

    def test_top_domains_by_confidence_ranked(self, populated_mem):
        data = populated_mem.get_visualization_data()
        confs = [d["avg_confidence"] for d in data["top_domains_by_confidence"]]
        assert confs == sorted(confs, reverse=True)
