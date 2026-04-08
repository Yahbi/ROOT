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


class TestGoalDependencies:
    def test_add_dependency(self, goal_engine):
        parent = goal_engine.add_goal(title="Parent goal must finish first")
        child = goal_engine.add_goal(title="Child goal depends on parent")
        assert goal_engine.add_dependency(child.id, parent.id) is True
        refreshed = goal_engine.get_goal(child.id)
        assert parent.id in refreshed.depends_on

    def test_dependency_idempotent(self, goal_engine):
        g1 = goal_engine.add_goal(title="Idempotent dep source goal")
        g2 = goal_engine.add_goal(title="Idempotent dep target goal")
        goal_engine.add_dependency(g1.id, g2.id)
        assert goal_engine.add_dependency(g1.id, g2.id) is True
        refreshed = goal_engine.get_goal(g1.id)
        assert refreshed.depends_on.count(g2.id) == 1

    def test_remove_dependency(self, goal_engine):
        g1 = goal_engine.add_goal(title="Removable dep source goal")
        g2 = goal_engine.add_goal(title="Removable dep target goal")
        goal_engine.add_dependency(g1.id, g2.id)
        goal_engine.remove_dependency(g1.id, g2.id)
        refreshed = goal_engine.get_goal(g1.id)
        assert g2.id not in refreshed.depends_on

    def test_cycle_detection(self, goal_engine):
        a = goal_engine.add_goal(title="Cycle test goal A")
        b = goal_engine.add_goal(title="Cycle test goal B")
        goal_engine.add_dependency(a.id, b.id)
        # Adding b -> a would create a cycle
        assert goal_engine.add_dependency(b.id, a.id) is False

    def test_get_blocked_goals(self, goal_engine):
        blocker = goal_engine.add_goal(title="Blocker active goal here")
        blocked = goal_engine.add_goal(title="Blocked by blocker goal here")
        goal_engine.add_dependency(blocked.id, blocker.id)
        blocked_list = goal_engine.get_blocked_goals()
        goal_ids = [b["goal_id"] for b in blocked_list]
        assert blocked.id in goal_ids

    def test_dependency_graph(self, goal_engine):
        g1 = goal_engine.add_goal(title="Graph node one for dep test")
        g2 = goal_engine.add_goal(title="Graph node two for dep test")
        goal_engine.add_dependency(g1.id, g2.id)
        graph = goal_engine.get_dependency_graph()
        assert g1.id in graph
        assert g2.id in graph[g1.id]

    def test_dependency_on_unknown_goal(self, goal_engine):
        g = goal_engine.add_goal(title="Valid goal for unknown dep test")
        assert goal_engine.add_dependency(g.id, "goal_nonexistent") is False


class TestProgressEstimation:
    def test_estimate_no_progress(self, goal_engine):
        goal = goal_engine.add_goal(title="Zero progress estimation test")
        est = goal_engine.estimate_completion(goal.id)
        assert "current_progress" in est
        assert est["current_progress"] == 0.0

    def test_estimate_with_progress(self, goal_engine):
        goal = goal_engine.add_goal(title="Progress estimation velocity test")
        goal_engine.update_progress(goal.id, 0.5, "Halfway there")
        est = goal_engine.estimate_completion(goal.id)
        assert est["current_progress"] == pytest.approx(0.5, abs=0.01)

    def test_estimate_completed_goal(self, goal_engine):
        goal = goal_engine.add_goal(title="Completed estimation test goal")
        goal_engine.update_progress(goal.id, 1.0, "Done")
        est = goal_engine.estimate_completion(goal.id)
        assert est["status"] == "completed"

    def test_estimate_unknown_goal(self, goal_engine):
        est = goal_engine.estimate_completion("goal_nonexistent_xyz")
        assert "error" in est

    def test_velocity_report(self, goal_engine):
        goal_engine.add_goal(title="Velocity report test goal one")
        goal_engine.add_goal(title="Velocity report test goal two")
        report = goal_engine.get_velocity_report()
        assert len(report) == 2
        for entry in report:
            assert "goal_id" in entry
            assert "current_progress" in entry


class TestPriorityScoring:
    def test_compute_priority_score_best(self, goal_engine):
        # importance=1, urgency=1 → highest priority → score = 1.0
        score = goal_engine.compute_priority_score(1, 1)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_compute_priority_score_worst(self, goal_engine):
        # importance=9, urgency=9 → lowest priority → score near 0
        score = goal_engine.compute_priority_score(9, 9)
        assert score == pytest.approx(0.0, abs=0.02)

    def test_add_goal_with_importance_urgency(self, goal_engine):
        goal = goal_engine.add_goal(
            title="Scored priority goal for matrix test",
            importance=2,
            urgency=3,
        )
        assert goal.importance == 2
        assert goal.urgency == 3
        assert goal.priority_score > 0.5  # high importance+urgency → high score

    def test_update_priority_score(self, goal_engine):
        goal = goal_engine.add_goal(title="Priority score update test goal")
        updated = goal_engine.update_priority_score(goal.id, importance=1, urgency=1)
        assert updated is not None
        assert updated.priority_score == pytest.approx(1.0, abs=0.01)

    def test_get_prioritised_goals_order(self, goal_engine):
        goal_engine.add_goal(title="Low priority matrix goal", importance=8, urgency=8)
        goal_engine.add_goal(title="High priority matrix goal", importance=1, urgency=1)
        prioritised = goal_engine.get_prioritised_goals()
        # High-priority (score=1.0) should be first
        assert "High priority" in prioritised[0].title


class TestStructuredMilestones:
    def test_add_milestone(self, goal_engine):
        goal = goal_engine.add_goal(title="Structured milestone test goal")
        ms = goal_engine.add_milestone(goal.id, title="Phase 1 research complete")
        assert ms is not None
        assert ms["goal_id"] == goal.id
        assert ms["status"] == "pending"

    def test_add_milestone_unknown_goal(self, goal_engine):
        result = goal_engine.add_milestone("goal_unknown_xyz", title="Orphan milestone")
        assert result is None

    def test_get_milestones(self, goal_engine):
        goal = goal_engine.add_goal(title="Multi milestone retrieval test")
        goal_engine.add_milestone(goal.id, title="Milestone A", order_index=0)
        goal_engine.add_milestone(goal.id, title="Milestone B", order_index=1)
        milestones = goal_engine.get_milestones(goal.id)
        assert len(milestones) == 2

    def test_complete_structured_milestone(self, goal_engine):
        goal = goal_engine.add_goal(title="Complete structured milestone test")
        ms1 = goal_engine.add_milestone(goal.id, title="First sub-task complete")
        ms2 = goal_engine.add_milestone(goal.id, title="Second sub-task complete")
        result = goal_engine.complete_structured_milestone(goal.id, ms1["id"])
        assert result is not None
        refreshed = goal_engine.get_goal(goal.id)
        # 1 of 2 milestones done → 50% progress
        assert refreshed.progress == pytest.approx(0.5, abs=0.01)

    def test_complete_milestone_updates_progress(self, goal_engine):
        goal = goal_engine.add_goal(title="Progress from milestones test")
        ms_list = []
        for i in range(4):
            ms_list.append(goal_engine.add_milestone(goal.id, title=f"Quarter step {i}"))
        for ms in ms_list[:2]:
            goal_engine.complete_structured_milestone(goal.id, ms["id"])
        refreshed = goal_engine.get_goal(goal.id)
        assert refreshed.progress == pytest.approx(0.5, abs=0.01)

    def test_complete_unknown_milestone(self, goal_engine):
        goal = goal_engine.add_goal(title="Unknown milestone completion test")
        result = goal_engine.complete_structured_milestone(goal.id, "ms_notexist")
        assert result is None


class TestConflictDetection:
    def test_no_conflicts_no_resources(self, goal_engine):
        goal_engine.add_goal(title="No resource conflict goal A")
        goal_engine.add_goal(title="No resource conflict goal B")
        conflicts = goal_engine.detect_conflicts()
        # No shared resources → no resource conflicts
        assert all("shared_resources" in c for c in conflicts)
        resource_conflicts = [c for c in conflicts if not str(c["shared_resources"][0]).startswith("category:")]
        assert len(resource_conflicts) == 0

    def test_conflict_detected_shared_resource(self, goal_engine):
        goal_engine.add_goal(
            title="Capital-heavy trading goal one",
            resources=["capital", "time"],
        )
        goal_engine.add_goal(
            title="Capital-heavy startup goal two",
            resources=["capital", "llm"],
        )
        conflicts = goal_engine.detect_conflicts()
        assert len(conflicts) >= 1
        shared = conflicts[0]["shared_resources"]
        assert "capital" in shared

    def test_conflict_severity_labels(self, goal_engine):
        goal_engine.add_goal(
            title="Critical importance resource goal A",
            importance=1, urgency=1, resources=["llm"],
        )
        goal_engine.add_goal(
            title="Critical importance resource goal B",
            importance=1, urgency=1, resources=["llm"],
        )
        conflicts = goal_engine.detect_conflicts()
        resource_conflicts = [
            c for c in conflicts
            if not str(c.get("shared_resources", [""])[0]).startswith("category:")
        ]
        assert len(resource_conflicts) >= 1
        assert resource_conflicts[0]["severity"] in ("medium", "high", "critical")


class TestGoalSuggestions:
    def test_offline_suggestions(self, goal_engine):
        """Without an LLM, suggest goals for uncovered categories."""
        goal_engine.add_goal(title="Trading strategy alpha backtest", category="trading")
        suggestions = goal_engine._offline_goal_suggestions()
        # Should suggest from uncovered categories
        assert len(suggestions) >= 1
        for s in suggestions:
            assert "title" in s
            assert "category" in s
            assert "priority_score" in s

    def test_suggestions_all_categories_covered(self, goal_engine):
        """No uncovered categories → no offline suggestions."""
        for cat in ("trading", "learning", "automation", "health"):
            goal_engine.add_goal(title=f"Covering category {cat}", category=cat)
        suggestions = goal_engine._offline_goal_suggestions()
        assert len(suggestions) == 0

    def test_priority_score_in_suggestions(self, goal_engine):
        suggestions = goal_engine._offline_goal_suggestions()
        for s in suggestions:
            assert 0.0 <= s["priority_score"] <= 1.0


class TestGoalRetrospective:
    def test_retrospective_only_on_completed(self, goal_engine):
        import asyncio
        goal = goal_engine.add_goal(title="Active goal no retro allowed")
        result = asyncio.get_event_loop().run_until_complete(
            goal_engine.run_retrospective(goal.id)
        )
        assert result is None

    def test_retrospective_completed_goal(self, goal_engine):
        import asyncio
        goal = goal_engine.add_goal(title="Completed retro test goal")
        goal_engine.update_progress(goal.id, 1.0, "All done!")
        result = asyncio.get_event_loop().run_until_complete(
            goal_engine.run_retrospective(goal.id)
        )
        assert result is not None
        assert result["goal_id"] == goal.id
        assert "lessons" in result
        assert "successes" in result
        assert "obstacles" in result
        assert result["duration_days"] >= 0

    def test_retrospective_abandoned_goal(self, goal_engine):
        import asyncio
        goal = goal_engine.add_goal(title="Abandoned retro test goal")
        goal_engine.abandon_goal(goal.id)
        result = asyncio.get_event_loop().run_until_complete(
            goal_engine.run_retrospective(goal.id)
        )
        assert result is not None
        assert any("abandon" in o.lower() for o in result.get("obstacles", []))

    def test_retrospective_persisted(self, goal_engine):
        import asyncio
        goal = goal_engine.add_goal(title="Persisted retrospective test goal")
        goal_engine.update_progress(goal.id, 1.0, "Complete!")
        asyncio.get_event_loop().run_until_complete(
            goal_engine.run_retrospective(goal.id)
        )
        retros = goal_engine.get_retrospectives(goal.id)
        assert len(retros) == 1
        assert retros[0]["goal_id"] == goal.id

    def test_get_all_retrospectives(self, goal_engine):
        import asyncio
        for i in range(3):
            g = goal_engine.add_goal(title=f"Multiple retro test goal {i}")
            goal_engine.update_progress(g.id, 1.0, "Done")
            asyncio.get_event_loop().run_until_complete(
                goal_engine.run_retrospective(g.id)
            )
        retros = goal_engine.get_retrospectives(limit=10)
        assert len(retros) == 3

    def test_offline_retrospective_stalled(self, goal_engine):
        goal = goal_engine.add_goal(title="Stalled retrospective test goal")
        goal_engine.update_progress(goal.id, 1.0, "Done")
        goal_refreshed = goal_engine.get_goal(goal.id)
        events = goal_engine.get_goal_events(goal.id, limit=50)
        retro = goal_engine._offline_retrospective(goal_refreshed, events, 5.0)
        assert "lessons" in retro
        assert "successes" in retro
        assert 0.0 <= retro["completion_accuracy"] <= 1.0
