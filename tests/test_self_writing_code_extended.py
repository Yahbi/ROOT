"""Extended tests for Self-Writing Code System — proposal validation, edge cases."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.self_writing_code import (
    SelfWritingCodeSystem,
    ProposalScope,
    ProposalStatus,
    CodeProposal,
)


@pytest.fixture
def swc(tmp_path):
    with patch("backend.core.self_writing_code.SELF_CODE_DB", tmp_path / "self_code.db"):
        engine = SelfWritingCodeSystem()
        engine.start()
        yield engine
        engine.stop()


# ── ProposalScope Enum ────────────────────────────────────────────────


class TestProposalScopeEnum:
    def test_minor_value(self):
        assert ProposalScope.MINOR == "minor"

    def test_major_value(self):
        assert ProposalScope.MAJOR == "major"

    def test_invalid_scope_raises(self, swc: SelfWritingCodeSystem):
        with pytest.raises((ValueError, Exception)):
            swc.propose_improvement(
                title="t", description="d",
                file_path="f.py", inefficiency="slow",
                proposed_change="fast", scope="mega",
            )


# ── ProposalStatus Enum ───────────────────────────────────────────────


class TestProposalStatusEnum:
    def test_statuses_exist(self):
        assert ProposalStatus.PROPOSED == "proposed"
        assert ProposalStatus.TESTING == "testing"
        assert ProposalStatus.APPROVED == "approved"
        assert ProposalStatus.REJECTED == "rejected"
        assert ProposalStatus.DEPLOYED == "deployed"
        assert ProposalStatus.PENDING_APPROVAL == "pending_approval"


# ── Proposal Creation ─────────────────────────────────────────────────


class TestProposalCreation:
    def test_id_format(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="Query optimisation", description="Reduce N+1",
            file_path="backend/core/memory.py", inefficiency="N+1 queries",
            proposed_change="Use JOIN",
        )
        assert prop.id.startswith("cp_")

    def test_default_scope_is_minor(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        assert prop.scope == ProposalScope.MINOR

    def test_explicit_major_scope(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c", scope="major",
        )
        assert prop.scope == ProposalScope.MAJOR

    def test_initial_status_is_proposed(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        assert prop.status == ProposalStatus.PROPOSED

    def test_file_path_stored(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="backend/core/brain.py",
            inefficiency="i", proposed_change="c",
        )
        all_props = swc.get_proposals()
        match = [p for p in all_props if p.id == prop.id]
        assert len(match) == 1
        assert match[0].file_path == "backend/core/brain.py"

    def test_multiple_proposals_independent(self, swc: SelfWritingCodeSystem):
        p1 = swc.propose_improvement(
            title="first", description="d", file_path="a.py",
            inefficiency="i", proposed_change="c",
        )
        p2 = swc.propose_improvement(
            title="second", description="d", file_path="b.py",
            inefficiency="i", proposed_change="c",
        )
        assert p1.id != p2.id
        assert swc.stats()["total_proposals"] == 2


# ── Test Result Recording ─────────────────────────────────────────────


class TestTestResults:
    def test_minor_passed_auto_approves(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        result = swc.record_test_result(
            prop.id, test_passed=True, test_output="All pass",
            improvement_pct=20.0,
        )
        assert result.status == ProposalStatus.APPROVED

    def test_major_passed_needs_approval(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c", scope="major",
        )
        result = swc.record_test_result(
            prop.id, test_passed=True, test_output="All pass",
        )
        assert result.status == ProposalStatus.PENDING_APPROVAL

    def test_failed_test_rejects(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        result = swc.record_test_result(
            prop.id, test_passed=False, test_output="5 failures",
        )
        assert result.status == ProposalStatus.REJECTED

    def test_record_nonexistent_returns_none(self, swc: SelfWritingCodeSystem):
        result = swc.record_test_result(
            "cp_doesnotexist", test_passed=True, test_output="ok",
        )
        assert result is None

    def test_improvement_pct_stored(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        swc.record_test_result(
            prop.id, test_passed=True, test_output="All pass",
            improvement_pct=42.5,
        )
        approved = swc.get_approved()
        assert len(approved) == 1
        assert approved[0].improvement_pct == pytest.approx(42.5, abs=0.01)


# ── Approval / Rejection ──────────────────────────────────────────────


class TestApprovalRejection:
    def test_approve_pending_approval(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c", scope="major",
        )
        swc.record_test_result(prop.id, test_passed=True, test_output="ok")
        assert swc.approve(prop.id) is True
        approved = swc.get_approved()
        assert any(p.id == prop.id for p in approved)

    def test_reject_pending_approval(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c", scope="major",
        )
        swc.record_test_result(prop.id, test_passed=True, test_output="ok")
        assert swc.reject(prop.id) is True
        rejected = swc.get_proposals(status="rejected")
        assert any(p.id == prop.id for p in rejected)

    def test_approve_nonexistent_returns_false(self, swc: SelfWritingCodeSystem):
        assert swc.approve("cp_nonexistent") is False

    def test_reject_nonexistent_returns_false(self, swc: SelfWritingCodeSystem):
        assert swc.reject("cp_nonexistent") is False


# ── Deployment ────────────────────────────────────────────────────────


class TestDeployment:
    def test_mark_deployed_from_approved(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="t", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        swc.record_test_result(prop.id, test_passed=True, test_output="ok")
        assert swc.mark_deployed(prop.id) is True
        deployed = swc.get_deployed()
        assert any(p.id == prop.id for p in deployed)

    def test_deployed_count_increments(self, swc: SelfWritingCodeSystem):
        for i in range(3):
            prop = swc.propose_improvement(
                title=f"Opt {i}", description="d", file_path="f.py",
                inefficiency="i", proposed_change="c",
            )
            swc.record_test_result(prop.id, test_passed=True, test_output="ok")
            swc.mark_deployed(prop.id)
        assert len(swc.get_deployed()) == 3


# ── Stats and Querying ────────────────────────────────────────────────


class TestStatsAndQueries:
    def test_stats_by_status(self, swc: SelfWritingCodeSystem):
        # Proposed
        swc.propose_improvement(title="p1", description="d", file_path="f.py",
                                inefficiency="i", proposed_change="c")
        # Rejected via failed test
        prop2 = swc.propose_improvement(title="p2", description="d", file_path="f.py",
                                        inefficiency="i", proposed_change="c")
        swc.record_test_result(prop2.id, test_passed=False, test_output="fail")

        stats = swc.stats()
        assert stats["total_proposals"] == 2
        assert "proposed" in stats["by_status"]
        assert "rejected" in stats["by_status"]

    def test_get_proposals_by_status(self, swc: SelfWritingCodeSystem):
        p1 = swc.propose_improvement(
            title="Pending", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        p2 = swc.propose_improvement(
            title="Will Reject", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        swc.record_test_result(p2.id, test_passed=False, test_output="fail")
        proposed_only = swc.get_proposals(status="proposed")
        assert all(p.status == ProposalStatus.PROPOSED for p in proposed_only)

    def test_stats_includes_improvement_avg(self, swc: SelfWritingCodeSystem):
        prop = swc.propose_improvement(
            title="High gain", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        swc.record_test_result(prop.id, test_passed=True, test_output="ok",
                                improvement_pct=50.0)
        stats = swc.stats()
        assert "avg_improvement_pct" in stats
