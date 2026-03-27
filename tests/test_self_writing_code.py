"""Tests for the Self-Writing Code System."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.self_writing_code import SelfWritingCodeSystem, ProposalScope, ProposalStatus


@pytest.fixture
def swc(tmp_path):
    with patch("backend.core.self_writing_code.SELF_CODE_DB", tmp_path / "self_code.db"):
        engine = SelfWritingCodeSystem()
        engine.start()
        yield engine
        engine.stop()


class TestPropose:
    def test_propose_minor(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="Optimize query",
            description="Replace N+1 query with join",
            file_path="backend/core/memory_engine.py",
            inefficiency="N+1 query pattern",
            proposed_change="Use JOIN instead of loop",
        )
        assert prop.id.startswith("cp_")
        assert prop.scope == ProposalScope.MINOR
        assert prop.status == ProposalStatus.PROPOSED

    def test_propose_major(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="Rewrite brain routing",
            description="Complete routing rewrite",
            file_path="backend/core/brain.py",
            inefficiency="Complex routing logic",
            proposed_change="New routing architecture",
            scope="major",
        )
        assert prop.scope == ProposalScope.MAJOR


class TestTestResults:
    def test_passed_minor_auto_approves(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="slow", proposed_change="fast",
        )
        result = swc.record_test_result(
            prop.id, test_passed=True, test_output="All tests pass",
            improvement_pct=15.0,
        )
        assert result is not None
        assert result.status == ProposalStatus.APPROVED

    def test_passed_major_needs_approval(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="slow", proposed_change="fast", scope="major",
        )
        result = swc.record_test_result(
            prop.id, test_passed=True, test_output="All tests pass",
        )
        assert result is not None
        assert result.status == ProposalStatus.PENDING_APPROVAL

    def test_failed_rejects(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="slow", proposed_change="fast",
        )
        result = swc.record_test_result(
            prop.id, test_passed=False, test_output="3 tests failed",
        )
        assert result is not None
        assert result.status == ProposalStatus.REJECTED


class TestApprovalFlow:
    def test_approve_pending(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="slow", proposed_change="fast", scope="major",
        )
        swc.record_test_result(prop.id, test_passed=True, test_output="ok")
        assert swc.approve(prop.id) is True
        approved = swc.get_approved()
        assert len(approved) == 1

    def test_reject_pending(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="slow", proposed_change="fast", scope="major",
        )
        swc.record_test_result(prop.id, test_passed=True, test_output="ok")
        assert swc.reject(prop.id) is True

    def test_mark_deployed(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="slow", proposed_change="fast",
        )
        swc.record_test_result(prop.id, test_passed=True, test_output="ok")
        assert swc.mark_deployed(prop.id) is True
        deployed = swc.get_deployed()
        assert len(deployed) == 1


class TestStats:
    def test_empty_stats(self, swc: SelfWritingCodeSystem):
        stats = swc.stats()
        assert stats["total_proposals"] == 0

    def test_stats_with_data(self, swc: SelfWritingCodeSystem):
        swc.propose_improvement(
            title="t1", description="d", file_path="f.py",
            inefficiency="slow", proposed_change="fast",
        )
        prop = swc.propose_improvement(
            title="t2", description="d", file_path="f.py",
            inefficiency="slow", proposed_change="fast",
        )
        swc.record_test_result(prop.id, test_passed=True, test_output="ok",
                                improvement_pct=20.0)
        swc.mark_deployed(prop.id)
        stats = swc.stats()
        assert stats["total_proposals"] == 2
        assert "proposed" in stats["by_status"]
        assert "deployed" in stats["by_status"]
