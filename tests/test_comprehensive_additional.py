"""Comprehensive additional tests filling gaps in coverage — correct API usage."""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.agent_collab import (
    AgentCollaboration,
    CollabPattern,
    CollabStep,
    CollabWorkflow,
    WorkflowStatus,
)
from backend.core.action_chains import build_default_chains, ActionChainEngine, ActionChain
from backend.core.prediction_ledger import PredictionLedger
from backend.core.self_writing_code import SelfWritingCodeSystem, ProposalScope, ProposalStatus
from backend.core.revenue_engine import RevenueEngine, StreamStatus
from backend.core.experiment_lab import ExperimentLab, ExperimentStatus


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_orchestrator():
    orch = AsyncMock()
    result = MagicMock()
    result.tasks = []
    result.success_count = 0
    orch.execute_parallel = AsyncMock(return_value=result)
    return orch


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    connector = AsyncMock()
    connector.send_task = AsyncMock(return_value={"result": "done"})
    registry.get_connector.return_value = connector
    return registry


@pytest.fixture
def collab(mock_orchestrator, mock_registry):
    return AgentCollaboration(
        orchestrator=mock_orchestrator,
        bus=None,
        registry=mock_registry,
    )


@pytest.fixture
def ledger(tmp_path):
    with patch("backend.core.prediction_ledger.PREDICTION_DB", tmp_path / "predictions.db"):
        engine = PredictionLedger()
        engine.start()
        yield engine
        engine.stop()


@pytest.fixture
def swc(tmp_path):
    with patch("backend.core.self_writing_code.SELF_CODE_DB", tmp_path / "self_code.db"):
        engine = SelfWritingCodeSystem()
        engine.start()
        yield engine
        engine.stop()


@pytest.fixture
def rev(tmp_path):
    with patch("backend.core.revenue_engine.REVENUE_DB", tmp_path / "revenue.db"):
        engine = RevenueEngine()
        engine.start()
        yield engine
        engine.stop()


@pytest.fixture
def lab(tmp_path):
    with patch("backend.core.experiment_lab.EXPERIMENT_DB", tmp_path / "experiments.db"):
        engine = ExperimentLab()
        engine.start()
        yield engine
        engine.stop()


# ── CollabWorkflow via dataclasses.replace ────────────────────────────


class TestCollabWorkflowReplace:
    def test_replace_status(self):
        wf = CollabWorkflow(
            id="wf_z", pattern=CollabPattern.COUNCIL,
            initiator="hermes", goal="council goal",
        )
        updated = dataclasses.replace(wf, status=WorkflowStatus.RUNNING)
        assert updated.status == WorkflowStatus.RUNNING
        assert wf.status == WorkflowStatus.PENDING  # original unchanged

    def test_replace_final_result(self):
        wf = CollabWorkflow(
            id="wf_1", pattern=CollabPattern.DELEGATE,
            initiator="root", goal="do task",
        )
        updated = dataclasses.replace(wf, final_result="done successfully")
        assert updated.final_result == "done successfully"
        assert wf.final_result is None


# ── Agent Domain Mapping Correct ──────────────────────────────────────


class TestAgentDomainMappingCorrect:
    def test_swarm_maps_to_trading(self):
        assert AgentCollaboration._agent_to_domain("swarm") == "trading"

    def test_coder_maps_to_code(self):
        assert AgentCollaboration._agent_to_domain("coder") == "code"

    def test_guardian_maps_to_security(self):
        assert AgentCollaboration._agent_to_domain("guardian") == "security"

    def test_root_maps_to_system(self):
        assert AgentCollaboration._agent_to_domain("root") == "system"

    def test_writer_maps_to_writing(self):
        assert AgentCollaboration._agent_to_domain("writer") == "writing"

    def test_analyst_maps_to_market(self):
        assert AgentCollaboration._agent_to_domain("analyst") == "market"

    def test_hermes_maps_to_system(self):
        assert AgentCollaboration._agent_to_domain("hermes") == "system"

    def test_builder_maps_to_code(self):
        assert AgentCollaboration._agent_to_domain("builder") == "code"

    def test_miro_maps_to_market(self):
        assert AgentCollaboration._agent_to_domain("miro") == "market"

    def test_unknown_defaults_to_research(self):
        assert AgentCollaboration._agent_to_domain("unknown_xyz") == "research"


# ── Council Pattern Uses Fanout ───────────────────────────────────────


class TestCouncilUsesFanout:
    @pytest.mark.asyncio
    async def test_council_pattern_is_fanout(self, collab, mock_orchestrator, mock_registry):
        """Council internally uses the fanout pattern."""
        orch_result = MagicMock()
        orch_result.tasks = []
        orch_result.success_count = 0
        mock_orchestrator.execute_parallel = AsyncMock(return_value=orch_result)

        wf = await collab.council(
            initiator="root", question="What should we do?", agents=[],
        )
        # Council wraps fanout, so pattern is FANOUT internally
        assert wf.pattern in (CollabPattern.COUNCIL, CollabPattern.FANOUT)

    @pytest.mark.asyncio
    async def test_council_with_agents_gathers_opinions(
        self, collab, mock_orchestrator, mock_registry,
    ):
        advisor = MagicMock()
        advisor.agent_id = "analyst"
        advisor.result = "Recommend option A"
        advisor.error = None
        advisor.status = MagicMock(value="completed")

        orch_result = MagicMock()
        orch_result.tasks = [advisor]
        orch_result.success_count = 1
        mock_orchestrator.execute_parallel = AsyncMock(return_value=orch_result)

        connector = AsyncMock()
        connector.send_task = AsyncMock(return_value={"result": "consensus: A"})
        mock_registry.get_connector.return_value = connector

        wf = await collab.council(
            initiator="root",
            question="Which option?",
            agents=["analyst"],
        )
        assert wf.status == WorkflowStatus.COMPLETED


# ── Action Chain Correct Triggers ─────────────────────────────────────


class TestActionChainCorrectTriggers:
    @pytest.mark.asyncio
    async def test_survival_economics_triggers_remediation(self):
        p = AsyncMock()
        p.trigger = AsyncMock(return_value="remediated")
        engine = build_default_chains(proactive_engine=p)
        execs = await engine.evaluate_trigger(
            "survival_economics", {"result": "emergency mode active"},
        )
        matching = [e for e in execs if e.chain_id == "survival_to_revenue_remediation"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_skill_discovery_triggers_improvement(self):
        p = AsyncMock()
        p.trigger = AsyncMock(return_value="improved")
        engine = build_default_chains(proactive_engine=p)
        execs = await engine.evaluate_trigger(
            "skill_discovery", {"result": "insight found with weight update"},
        )
        matching = [e for e in execs if e.chain_id == "learning_to_improvement"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_goal_assessment_stalled_triggers_recovery(self):
        p = AsyncMock()
        p.trigger = AsyncMock(return_value="recovery started")
        engine = build_default_chains(proactive_engine=p)
        execs = await engine.evaluate_trigger(
            "goal_assessment", {"result": "goal is stalled after 48h"},
        )
        matching = [e for e in execs if e.chain_id == "goal_stalled_to_recovery"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_code_scanner_triggers_rewrite(self):
        p = AsyncMock()
        p.trigger = AsyncMock(return_value="rewrite started")
        engine = build_default_chains(proactive_engine=p)
        execs = await engine.evaluate_trigger(
            "code_scanner", {"result": "found 3 improvement proposals"},
        )
        matching = [e for e in execs if e.chain_id == "code_scanner_to_rewrite"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_experiment_proposer_triggers_revenue(self):
        p = AsyncMock()
        p.trigger = AsyncMock(return_value="revenue cycle")
        engine = build_default_chains(proactive_engine=p)
        execs = await engine.evaluate_trigger(
            "experiment_proposer", {"result": "experiment completed with result"},
        )
        matching = [e for e in execs if e.chain_id == "experiment_to_revenue"]
        assert len(matching) == 1


# ── Prediction Ledger Valid Directions ───────────────────────────────


class TestPredictionValidDirections:
    def test_hold_direction_valid(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="miro", symbol="AAPL", direction="hold",
            confidence=0.5, reasoning="Sideways market consolidation",
        )
        assert pid.startswith("pred_")

    def test_long_and_short_are_valid(self, ledger: PredictionLedger):
        for direction in ("long", "short"):
            pid = ledger.record_prediction(
                source="swarm", symbol="TSLA", direction=direction,
                confidence=0.7, reasoning=f"Test {direction}",
            )
            assert pid.startswith("pred_")

    def test_hold_resolved_as_hit(self, ledger: PredictionLedger):
        pid = ledger.record_prediction(
            source="directive", symbol="ETH", direction="hold",
            confidence=0.5, reasoning="Consolidation phase",
        )
        is_hit = ledger.resolve_prediction(pid, actual_direction="hold", actual_price=2000.0)
        assert is_hit is True

    def test_invalid_direction_raises(self, ledger: PredictionLedger):
        with pytest.raises(ValueError, match="Invalid direction"):
            ledger.record_prediction(
                source="miro", symbol="AAPL", direction="neutral",
                confidence=0.5, reasoning="test",
            )


# ── SelfWritingCode Correct Query Methods ────────────────────────────


class TestSelfWritingCodeCorrectQueries:
    def test_get_history_returns_all_proposals(self, swc: SelfWritingCodeSystem):
        p1 = swc.propose_improvement(
            title="t1", description="d", file_path="backend/core/brain.py",
            inefficiency="i", proposed_change="c",
        )
        p2 = swc.propose_improvement(
            title="t2", description="d", file_path="backend/core/memory.py",
            inefficiency="i", proposed_change="c",
        )
        history = swc.get_history()
        ids = [p.id for p in history]
        assert p1.id in ids
        assert p2.id in ids

    def test_get_proposed_returns_proposed_only(self, swc: SelfWritingCodeSystem):
        p1 = swc.propose_improvement(
            title="Stays Proposed", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        p2 = swc.propose_improvement(
            title="Gets Rejected", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c",
        )
        swc.record_test_result(p2.id, test_passed=False, test_output="fail")
        proposed = swc.get_proposed()
        assert all(p.status == ProposalStatus.PROPOSED for p in proposed)
        assert any(p.id == p1.id for p in proposed)

    def test_get_pending_approval_returns_pending_only(self, swc: SelfWritingCodeSystem):
        major = swc.propose_improvement(
            title="Major Change", description="d", file_path="brain.py",
            inefficiency="i", proposed_change="c", scope="major",
        )
        swc.record_test_result(major.id, test_passed=True, test_output="ok")
        pending = swc.get_pending_approval()
        assert any(p.id == major.id for p in pending)
        assert all(p.status == ProposalStatus.PENDING_APPROVAL for p in pending)

    def test_reject_from_pending_approval(self, swc: SelfWritingCodeSystem):
        major = swc.propose_improvement(
            title="Major Rewrite", description="d", file_path="f.py",
            inefficiency="i", proposed_change="c", scope="major",
        )
        swc.record_test_result(major.id, test_passed=True, test_output="ok")
        assert swc.reject(major.id) is True
        # After rejection, should not be in pending approval
        pending = swc.get_pending_approval()
        assert not any(p.id == major.id for p in pending)


# ── Revenue Auto-Remediate with Launched Products ─────────────────────


class TestRevenueAutoRemediateWithLaunchedProducts:
    def test_remediate_skips_idea_status_products(self, rev: RevenueEngine):
        """Products in 'idea' status are skipped by auto_remediate."""
        # Create emergency condition: cost > revenue
        prod = rev.add_product(name="Idea Only", stream="micro_saas")
        rev.record_revenue(prod.id, 100.0)
        loss = rev.add_product(name="Loss SaaS", stream="automation_agency")
        rev.record_cost(loss.id, 5000.0)
        result = rev.auto_remediate()
        # Emergency triggered (rev < cost), but both in idea status → paused list is empty
        assert result["emergency"] is True
        assert result["paused"] == []  # Idea-status products skipped

    def test_remediate_acts_on_launched_products(self, rev: RevenueEngine):
        """Launched products with losses are paused by auto_remediate."""
        # Create loss-making product (launched) - profit < -20
        loser = rev.add_product(name="Money Sink", stream="automation_agency")
        rev.record_cost(loser.id, 1000.0)  # -1000 profit
        rev.update_status(loser.id, "launched")

        result = rev.auto_remediate()
        assert result["emergency"] is True
        # The loser should be paused (profit < -20)
        paused_ids = [p["id"] for p in result["paused"]]
        assert loser.id in paused_ids

    def test_remediate_identifies_top_earning_launched(self, rev: RevenueEngine):
        """Top earners (launched, profit > 100) are identified."""
        earner = rev.add_product(name="Strong Earner", stream="micro_saas")
        rev.record_revenue(earner.id, 5000.0)
        rev.record_cost(earner.id, 200.0)
        rev.update_status(earner.id, "launched")

        # Create emergency
        loser = rev.add_product(name="Big Loss", stream="content_network")
        rev.record_cost(loser.id, 8000.0)
        rev.update_status(loser.id, "launched")

        result = rev.auto_remediate()
        earner_ids = [e["id"] for e in result["top_earners"]]
        assert earner.id in earner_ids


# ── Experiment Lab ProposalValidation Title Required ─────────────────


class TestExperimentProposeValidation:
    def test_valid_title_stores_experiment(self, lab: ExperimentLab):
        """A valid title stores the experiment."""
        exp = lab.propose(title="Valid Title", hypothesis="h", category="saas")
        assert exp.title == "Valid Title"
        assert exp.status == ExperimentStatus.PROPOSED

    def test_all_categories_accepted(self, lab: ExperimentLab):
        from backend.core.experiment_lab import ExperimentCategory
        for cat in ExperimentCategory:
            exp = lab.propose(
                title=f"Cat {cat.value}", hypothesis="h", category=cat.value,
            )
            assert exp.category == cat

    def test_cannot_scale_failed_experiment(self, lab: ExperimentLab):
        exp = lab.propose(title="t", hypothesis="h", category="saas")
        lab.start_experiment(exp.id)
        lab.complete_experiment(exp.id, result="fail", success=False)
        result = lab.scale_experiment(exp.id)
        assert result is False

    def test_experiment_stats_category_breakdown(self, lab: ExperimentLab):
        lab.propose(title="SaaS A", hypothesis="h", category="saas")
        lab.propose(title="SaaS B", hypothesis="h", category="saas")
        lab.propose(title="Trade C", hypothesis="h", category="trading")
        stats = lab.stats()
        assert stats["by_category"]["saas"] == 2
        assert stats["by_category"]["trading"] == 1


# ── Mixed Workflow Stats ──────────────────────────────────────────────


class TestMixedWorkflowStats:
    @pytest.mark.asyncio
    async def test_stats_tracks_all_patterns(self, collab, mock_orchestrator, mock_registry):
        # Do delegate
        await collab.delegate(from_agent="root", to_agent="coder", task="code task")
        # Do pipeline
        await collab.pipeline(
            initiator="root", goal="pipeline",
            steps=[{"agent_id": "analyst", "task": "analyze"}],
        )
        s = collab.stats()
        assert s["total_workflows"] == 2
        assert s["by_pattern"]["delegate"] == 1
        assert s["by_pattern"]["pipeline"] == 1
        assert s["by_pattern"]["fanout"] == 0

    @pytest.mark.asyncio
    async def test_success_rate_all_succeed(self, collab):
        for _ in range(3):
            await collab.delegate(from_agent="root", to_agent="coder", task="t")
        s = collab.stats()
        assert s["success_rate"] == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_get_history_limit(self, collab):
        for i in range(8):
            await collab.delegate(from_agent="root", to_agent="writer", task=f"t{i}")
        history = collab.get_history(limit=5)
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_get_active_is_empty_after_complete(self, collab):
        await collab.delegate(from_agent="root", to_agent="analyst", task="analyze")
        assert collab.get_active() == []
