"""Tests for ProjectEcosystem engine."""

import tempfile
from pathlib import Path

import pytest

from backend.core.project_ecosystem import (
    KNOWN_PROJECTS,
    PROJECT_CONNECTIONS,
    ProjectEcosystem,
)


@pytest.fixture
def ecosystem():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    eco = ProjectEcosystem(db_path=db_path)
    eco.start()
    yield eco
    eco.stop()
    db_path.unlink(missing_ok=True)


class TestLifecycle:
    def test_start_creates_tables(self, ecosystem):
        row = ecosystem.conn.execute(
            "SELECT COUNT(*) as c FROM projects"
        ).fetchone()
        assert row["c"] > 0

    def test_double_start_no_duplicates(self, ecosystem):
        count_before = len(ecosystem.get_all_projects())
        ecosystem.stop()
        ecosystem.start()
        count_after = len(ecosystem.get_all_projects())
        assert count_before == count_after


class TestKnownProjects:
    def test_all_known_projects_loaded(self, ecosystem):
        projects = ecosystem.get_all_projects()
        assert len(projects) == len(KNOWN_PROJECTS)

    def test_project_names_match(self, ecosystem):
        names = {p.name for p in ecosystem.get_all_projects()}
        expected = {p["name"] for p in KNOWN_PROJECTS}
        assert names == expected

    def test_root_project_exists(self, ecosystem):
        root = ecosystem.get_project("ROOT")
        assert root is not None
        assert root.project_type == "fastapi"
        assert root.port == 9000

    def test_onsite_project(self, ecosystem):
        onsite = ecosystem.get_project("Onsite")
        assert onsite is not None
        assert onsite.revenue_stream == "data_products"
        assert "FastAPI" in onsite.tech_stack

    def test_nonexistent_project_returns_none(self, ecosystem):
        assert ecosystem.get_project("DoesNotExist") is None


class TestRevenueMapping:
    def test_by_revenue_stream(self, ecosystem):
        data_projects = ecosystem.get_by_revenue_stream("data_products")
        assert len(data_projects) >= 3  # Onsite, API-Data, Kimi-Agents, OpenClaw

    def test_automation_stream(self, ecosystem):
        auto_projects = ecosystem.get_by_revenue_stream("automation_agency")
        names = {p.name for p in auto_projects}
        assert "OI-Astra" in names


class TestConnections:
    def test_connections_exist(self, ecosystem):
        connections = ecosystem.get_connections()
        assert len(connections) == len(PROJECT_CONNECTIONS)

    def test_connection_structure(self, ecosystem):
        connections = ecosystem.get_connections()
        for conn in connections:
            assert "source" in conn
            assert "target" in conn
            assert "description" in conn


class TestEcosystemSummary:
    def test_summary_keys(self, ecosystem):
        summary = ecosystem.get_ecosystem_summary()
        assert "total_projects" in summary
        assert "by_type" in summary
        assert "by_revenue_stream" in summary
        assert "connections" in summary
        assert "active_ports" in summary
        assert "tech_stack_coverage" in summary

    def test_summary_counts(self, ecosystem):
        summary = ecosystem.get_ecosystem_summary()
        assert summary["total_projects"] == len(KNOWN_PROJECTS)
        assert summary["connections"] == len(PROJECT_CONNECTIONS)

    def test_tech_stack_populated(self, ecosystem):
        summary = ecosystem.get_ecosystem_summary()
        assert "Python" in summary["tech_stack_coverage"]
        assert "FastAPI" in summary["tech_stack_coverage"]


class TestBrainContext:
    def test_context_contains_projects(self, ecosystem):
        ctx = ecosystem.get_context_for_brain()
        assert "ROOT" in ctx
        assert "Onsite" in ctx
        assert "OI-Astra" in ctx

    def test_context_contains_connections(self, ecosystem):
        ctx = ecosystem.get_context_for_brain()
        assert "Project connections:" in ctx


class TestEvents:
    def test_record_event(self, ecosystem):
        ecosystem.record_event("ROOT", "deployment", "Deployed v1.0.1")
        events = ecosystem.conn.execute(
            "SELECT * FROM project_events WHERE event_type = 'deployment'"
        ).fetchall()
        assert len(events) == 1
        assert events[0]["description"] == "Deployed v1.0.1"

    def test_event_for_unknown_project(self, ecosystem):
        # Should not raise, just log warning
        ecosystem.record_event("FakeProject", "test", "test")


class TestStats:
    def test_stats_matches_summary(self, ecosystem):
        stats = ecosystem.stats()
        summary = ecosystem.get_ecosystem_summary()
        assert stats == summary
