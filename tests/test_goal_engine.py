"""Tests for the Goal Engine — goal CRUD, progress tracking, milestones."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.goal_engine import GoalEngine, GOALS_DB


@pytest.fixture
def goal_engine(tmp_path):
    db_path = tmp_path / "test_goals.db"
    with patch("backend.core.goal_engine.GOALS_DB", db_path):
        engine = GoalEngine()
        engine.start()
        yield engine
        engine.stop()


class TestGoalCRUD:
    def test_add_goal(self, goal_engine):
        goal = goal_engine.add_goal(
            title="Learn Rust programming language deeply",
            description="Complete the Rust book and build a CLI tool",
            priority=3,
            category="learning",
        )
        assert goal.id.startswith("goal_")
        assert goal.title == "Learn Rust programming language deeply"
        assert goal.status == "active"

    def test_get_goal(self, goal_engine):
        created = goal_engine.add_goal(title="Test goal for retrieval testing")
        retrieved = goal_engine.get_goal(created.id)
        assert retrieved is not None
        assert retrieved.title == "Test goal for retrieval testing"

    def test_get_active_goals(self, goal_engine):
        goal_engine.add_goal(title="Goal A for active listing test")
        goal_engine.add_goal(title="Goal B for active listing test")
        active = goal_engine.get_active_goals()
        assert len(active) == 2

    def test_goals_by_category(self, goal_engine):
        goal_engine.add_goal(title="Trading goal number one", category="trading")
        goal_engine.add_goal(title="Learning goal number one", category="learning")
        trading = goal_engine.get_goals_by_category("trading")
        assert len(trading) == 1
        assert trading[0].category == "trading"


class TestGoalProgress:
    def test_update_progress(self, goal_engine):
        goal = goal_engine.add_goal(title="Progressive goal for tracking")
        updated = goal_engine.update_progress(goal.id, 0.5, "Halfway there")
        assert updated.progress == 0.5

    def test_auto_complete_at_100(self, goal_engine):
        goal = goal_engine.add_goal(title="Goal that will auto complete")
        updated = goal_engine.update_progress(goal.id, 1.0, "Done!")
        assert updated.status == "completed"

    def test_complete_milestone(self, goal_engine):
        goal = goal_engine.add_goal(
            title="Milestone tracked goal for testing",
            milestones=["Step 1", "Step 2", "Step 3"],
        )
        updated = goal_engine.complete_milestone(goal.id, "Step 1")
        assert "Step 1" in updated.completed_milestones
        assert updated.progress == pytest.approx(1 / 3, abs=0.01)


class TestGoalLifecycle:
    def test_pause_and_resume(self, goal_engine):
        goal = goal_engine.add_goal(title="Pausable goal for lifecycle test")
        assert goal_engine.pause_goal(goal.id) is True
        paused = goal_engine.get_goal(goal.id)
        assert paused.status == "paused"

        assert goal_engine.resume_goal(goal.id) is True
        resumed = goal_engine.get_goal(goal.id)
        assert resumed.status == "active"

    def test_abandon(self, goal_engine):
        goal = goal_engine.add_goal(title="Abandonable goal for testing")
        assert goal_engine.abandon_goal(goal.id) is True
        abandoned = goal_engine.get_goal(goal.id)
        assert abandoned.status == "abandoned"

    def test_stats(self, goal_engine):
        goal_engine.add_goal(title="Active goal one", category="trading")
        goal_engine.add_goal(title="Active goal two", category="learning")
        stats = goal_engine.stats()
        assert stats["total_goals"] == 2
        assert stats["by_status"]["active"] == 2


class TestGoalEvents:
    def test_events_logged(self, goal_engine):
        goal = goal_engine.add_goal(title="Event tracked goal for testing")
        goal_engine.update_progress(goal.id, 0.5)
        events = goal_engine.get_goal_events(goal.id)
        assert len(events) >= 2  # created + progress
        assert events[0]["event_type"] == "progress"
