"""Tests for Verification Protocol — consensus, redundancy, confidence voting."""

from __future__ import annotations

import time

import pytest

from backend.core.verification_protocol import (
    AgentVerdict,
    ConsensusEngine,
    RedundancyDetector,
    ResolutionStrategy,
    VerificationLevel,
    VerificationProtocol,
    VerificationResult,
    classify_verification_need,
)


# ── Verification Level Classification ───────────────────────────


class TestClassifyVerificationNeed:
    def test_low_stakes_none(self):
        level = classify_verification_need("hello there")
        assert level == VerificationLevel.NONE

    def test_low_stakes_status(self):
        level = classify_verification_need("status check")
        assert level == VerificationLevel.NONE

    def test_financial_always_dual_plus(self):
        level = classify_verification_need("check price", is_financial=True)
        assert level in (VerificationLevel.DUAL, VerificationLevel.COUNCIL)

    def test_actionable_trade_council(self):
        level = classify_verification_need("buy 100 shares", is_financial=True, is_actionable=True)
        assert level == VerificationLevel.COUNCIL

    def test_high_stakes_keywords_dual(self):
        level = classify_verification_need("analyze the market price and revenue trends")
        assert level in (VerificationLevel.DUAL, VerificationLevel.COUNCIL)

    def test_many_high_stakes_council(self):
        level = classify_verification_need(
            "trade the security for profit to deploy into production at a financial cost"
        )
        assert level == VerificationLevel.COUNCIL

    def test_long_claim_dual(self):
        claim = "a" * 250  # Long but no keywords
        level = classify_verification_need(claim)
        assert level == VerificationLevel.DUAL

    def test_short_neutral_single(self):
        level = classify_verification_need("what is the weather today")
        assert level == VerificationLevel.SINGLE

    def test_actionable_deploy_council(self):
        level = classify_verification_need("deploy the app", is_actionable=True)
        assert level == VerificationLevel.COUNCIL


# ── Redundancy Detector ─────────────────────────────────────────


class TestRedundancyDetector:
    def test_no_redundancy_initially(self):
        rd = RedundancyDetector()
        assert rd.check_redundant("agent_a", "do task X") is None

    def test_same_agent_not_redundant(self):
        rd = RedundancyDetector()
        rd.register_task("agent_a", "do task X")
        assert rd.check_redundant("agent_a", "do task X") is None

    def test_different_agent_same_task_redundant(self):
        rd = RedundancyDetector()
        rd.register_task("agent_a", "do task X")
        result = rd.check_redundant("agent_b", "do task X")
        assert result is not None
        assert result["is_redundant"] is True
        assert result["original_agent"] == "agent_a"

    def test_case_insensitive(self):
        rd = RedundancyDetector()
        rd.register_task("agent_a", "Search for AAPL stock")
        result = rd.check_redundant("agent_b", "search for aapl stock")
        assert result is not None

    def test_expired_not_redundant(self):
        rd = RedundancyDetector(window_seconds=0)
        rd.register_task("agent_a", "do task X")
        time.sleep(0.01)
        assert rd.check_redundant("agent_b", "do task X") is None

    def test_different_tasks_not_redundant(self):
        rd = RedundancyDetector()
        rd.register_task("agent_a", "do task X")
        assert rd.check_redundant("agent_b", "completely different work") is None

    def test_stats(self):
        rd = RedundancyDetector()
        rd.register_task("a", "task 1")
        rd.register_task("b", "task 2")
        stats = rd.stats()
        assert stats["tracked_tasks"] == 2


# ── Consensus Engine ────────────────────────────────────────────


class TestConsensusEngine:
    def test_empty_verdicts(self):
        ce = ConsensusEngine()
        result = ce.resolve("claim", [])
        assert result.verified is False
        assert result.consensus_confidence == 0.0

    def test_single_verdict_high_confidence(self):
        ce = ConsensusEngine()
        v = AgentVerdict(agent_id="researcher", claim="AAPL up", confidence=0.9)
        result = ce.resolve("AAPL up", [v])
        assert result.verified is True
        assert result.consensus_confidence == 0.9

    def test_single_verdict_low_confidence(self):
        ce = ConsensusEngine()
        v = AgentVerdict(agent_id="researcher", claim="BTC crash", confidence=0.3)
        result = ce.resolve("BTC crash", [v])
        assert result.verified is False

    def test_highest_confidence_strategy(self):
        ce = ConsensusEngine()
        verdicts = [
            AgentVerdict(agent_id="a", claim="X", confidence=0.6),
            AgentVerdict(agent_id="b", claim="X", confidence=0.9),
            AgentVerdict(agent_id="c", claim="X", confidence=0.4),
        ]
        result = ce.resolve("X", verdicts, ResolutionStrategy.HIGHEST_CONFIDENCE)
        assert result.verified is True
        assert result.consensus_confidence == 0.9
        assert "b" in result.resolution_notes

    def test_majority_vote_positive(self):
        ce = ConsensusEngine()
        verdicts = [
            AgentVerdict(agent_id="a", claim="X", confidence=0.7),
            AgentVerdict(agent_id="b", claim="X", confidence=0.8),
            AgentVerdict(agent_id="c", claim="X", confidence=0.3),
        ]
        result = ce.resolve("X", verdicts, ResolutionStrategy.MAJORITY_VOTE)
        assert result.verified is True  # 2 vs 1
        assert "2 for" in result.resolution_notes

    def test_majority_vote_negative(self):
        ce = ConsensusEngine()
        verdicts = [
            AgentVerdict(agent_id="a", claim="X", confidence=0.2),
            AgentVerdict(agent_id="b", claim="X", confidence=0.3),
            AgentVerdict(agent_id="c", claim="X", confidence=0.8),
        ]
        result = ce.resolve("X", verdicts, ResolutionStrategy.MAJORITY_VOTE)
        assert result.verified is False  # 1 vs 2

    def test_weighted_vote(self):
        ce = ConsensusEngine()
        verdicts = [
            AgentVerdict(agent_id="a", claim="X", confidence=0.9),
            AgentVerdict(agent_id="b", claim="X", confidence=0.7),
        ]
        result = ce.resolve("X", verdicts, ResolutionStrategy.WEIGHTED_VOTE)
        # Default weight=0.5 → scores: 0.45, 0.35 → avg 0.4 < 0.5 → not verified
        # This is correct behavior: without track record, agents aren't fully trusted
        assert result.verified is False
        assert result.resolution_strategy == "weighted_vote"
        assert result.consensus_confidence == 0.4

    def test_weighted_vote_with_learning(self):
        class FakeLearning:
            def get_routing_weight(self, agent_id, category):
                return 0.9 if agent_id == "expert" else 0.1

        ce = ConsensusEngine(learning_engine=FakeLearning())
        verdicts = [
            AgentVerdict(agent_id="expert", claim="X", confidence=0.6),
            AgentVerdict(agent_id="novice", claim="X", confidence=0.8),
        ]
        result = ce.resolve("X", verdicts, ResolutionStrategy.WEIGHTED_VOTE)
        # Expert should win due to higher weight despite lower confidence
        assert "expert" in result.resolution_notes
        assert result.resolution_strategy == "weighted_vote"

    def test_agreement_ratio(self):
        ce = ConsensusEngine()
        verdicts = [
            AgentVerdict(agent_id="a", claim="X", confidence=0.8),
            AgentVerdict(agent_id="b", claim="X", confidence=0.7),
            AgentVerdict(agent_id="c", claim="X", confidence=0.6),
        ]
        result = ce.resolve("X", verdicts)
        assert result.agreement_ratio == 1.0  # All agree

    def test_disagreement_tracked(self):
        ce = ConsensusEngine()
        verdicts = [
            AgentVerdict(agent_id="a", claim="X", confidence=0.9),
            AgentVerdict(agent_id="b", claim="X", confidence=0.1),
        ]
        ce.resolve("X", verdicts)
        assert ce.stats()["disagreements"] == 1

    def test_agreement_tracked(self):
        ce = ConsensusEngine()
        verdicts = [
            AgentVerdict(agent_id="a", claim="X", confidence=0.9),
            AgentVerdict(agent_id="b", claim="X", confidence=0.8),
            AgentVerdict(agent_id="c", claim="X", confidence=0.7),
            AgentVerdict(agent_id="d", claim="X", confidence=0.6),
            AgentVerdict(agent_id="e", claim="X", confidence=0.75),
        ]
        ce.resolve("X", verdicts)
        assert ce.stats()["agreements"] == 1

    def test_stats_recent_results(self):
        ce = ConsensusEngine()
        v = AgentVerdict(agent_id="a", claim="test claim", confidence=0.8)
        ce.resolve("test claim", [v])
        stats = ce.stats()
        assert stats["total_verifications"] == 1
        assert len(stats["recent_results"]) == 1
        assert stats["recent_results"][0]["claim"] == "test claim"

    def test_verification_result_immutable(self):
        result = VerificationResult(
            claim="test", verified=True,
            consensus_confidence=0.8, agreement_ratio=1.0,
        )
        with pytest.raises(AttributeError):
            result.verified = False  # type: ignore[misc]


# ── Verification Protocol (Integration) ─────────────────────────


class TestVerificationProtocol:
    def test_should_verify_greeting_none(self):
        vp = VerificationProtocol()
        result = vp.should_verify("hello")
        assert result["level"] == "none"
        assert result["agents_needed"] == 0

    def test_should_verify_financial_dual(self):
        vp = VerificationProtocol()
        result = vp.should_verify("check stock price", is_financial=True)
        assert result["agents_needed"] >= 2

    def test_should_verify_actionable_trade_council(self):
        vp = VerificationProtocol()
        result = vp.should_verify("buy AAPL", is_financial=True, is_actionable=True)
        assert result["level"] == "council"
        assert result["agents_needed"] == 3

    def test_check_redundancy_none(self):
        vp = VerificationProtocol()
        assert vp.check_redundancy("agent_a", "task") is None

    def test_register_and_check_redundancy(self):
        vp = VerificationProtocol()
        vp.register_task("agent_a", "research AAPL")
        dup = vp.check_redundancy("agent_b", "research AAPL")
        assert dup is not None
        assert dup["is_redundant"] is True

    def test_resolve_verdicts(self):
        vp = VerificationProtocol()
        verdicts = [
            AgentVerdict(agent_id="a", claim="X", confidence=0.8),
            AgentVerdict(agent_id="b", claim="X", confidence=0.7),
        ]
        result = vp.resolve_verdicts("X", verdicts)
        # Default weight=0.5 → weighted confidence < 0.5 → not verified without track record
        assert result.verified is False
        assert isinstance(result, VerificationResult)
        assert result.consensus_confidence == 0.375

    def test_verify_agent_result(self):
        vp = VerificationProtocol()
        result = vp.verify_agent_result(
            agent_id="researcher",
            result="AAPL is trading at $180",
            confidence=0.85,
            claim="AAPL price",
        )
        assert result.verified is True
        assert result.consensus_confidence == 0.85

    def test_verify_agent_result_low_confidence(self):
        vp = VerificationProtocol()
        result = vp.verify_agent_result(
            agent_id="researcher",
            result="I'm not sure about this",
            confidence=0.3,
        )
        assert result.verified is False

    def test_stats(self):
        vp = VerificationProtocol()
        vp.register_task("a", "task 1")
        v = AgentVerdict(agent_id="a", claim="X", confidence=0.8)
        vp.resolve_verdicts("X", [v])
        stats = vp.stats()
        assert "consensus" in stats
        assert "redundancy" in stats
        assert stats["redundancy"]["tracked_tasks"] == 1

    def test_financial_strategy_is_weighted(self):
        vp = VerificationProtocol()
        result = vp.should_verify("analyze revenue", is_financial=True)
        assert result["strategy"] == "weighted_vote"

    def test_council_strategy_is_majority(self):
        vp = VerificationProtocol()
        result = vp.should_verify(
            "trade the security for profit and deploy to production at financial cost"
        )
        assert result["strategy"] == "majority_vote"
