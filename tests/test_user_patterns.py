"""Tests for the User Pattern Engine — activity tracking, preferences, anticipation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.user_patterns import UserPatternEngine, PATTERNS_DB


@pytest.fixture
def pattern_engine(tmp_path):
    db_path = tmp_path / "test_patterns.db"
    with patch("backend.core.user_patterns.PATTERNS_DB", db_path):
        engine = UserPatternEngine()
        engine.start()
        yield engine
        engine.stop()


class TestActivityTracking:
    def test_record_activity(self, pattern_engine):
        pattern_engine.record_activity(
            message="What are the latest AI trends?",
            topic="ai_research",
            intent="research",
        )
        stats = pattern_engine.stats()
        assert stats["activities_tracked"] == 1

    def test_active_hours(self, pattern_engine):
        for _ in range(5):
            pattern_engine.record_activity(message="Test activity message here")
        hours = pattern_engine.get_active_hours()
        assert sum(hours.values()) == 5

    def test_top_topics(self, pattern_engine):
        for _ in range(3):
            pattern_engine.record_activity(message="Trading query", topic="trading")
        for _ in range(2):
            pattern_engine.record_activity(message="AI query here", topic="ai")

        topics = pattern_engine.get_top_topics()
        assert topics[0]["topic"] == "trading"
        assert topics[0]["count"] == 3


class TestRecurringPatterns:
    def test_detect_recurring(self, pattern_engine):
        for _ in range(5):
            pattern_engine.record_activity(
                message="what is the market doing today please check",
                topic="trading",
            )
        patterns = pattern_engine.get_recurring_patterns(min_frequency=3)
        assert len(patterns) >= 1
        assert patterns[0]["frequency"] >= 3


class TestPreferences:
    def test_learn_and_get_preference(self, pattern_engine):
        pattern_engine.learn_preference("response_style", "concise", confidence=0.6)
        value = pattern_engine.get_preference("response_style")
        assert value == "concise"

    def test_preference_confidence_grows(self, pattern_engine):
        pattern_engine.learn_preference("tone", "professional")
        pattern_engine.learn_preference("tone", "professional")
        pattern_engine.learn_preference("tone", "professional")
        prefs = pattern_engine.get_all_preferences()
        assert prefs["tone"]["confidence"] > 0.5


class TestAnticipation:
    def test_anticipation_candidates(self, pattern_engine):
        # Record enough activity to generate time pattern
        for _ in range(10):
            pattern_engine.record_activity(message="Check something for me")
        candidates = pattern_engine.get_anticipation_candidates()
        # Should have at least a time pattern
        assert any(c["type"] == "time_pattern" for c in candidates)
