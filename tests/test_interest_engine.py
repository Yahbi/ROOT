"""Tests for the Interest Assessment Engine."""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.core.interest_engine import (
    InterestAssessment,
    InterestEngine,
    RiskLevel,
    Verdict,
    YOHAN_PROFILE,
)


@pytest.fixture
def engine():
    """Provide a bare InterestEngine (no memory, no LLM)."""
    return InterestEngine()


@pytest.fixture
def engine_with_memory(memory_engine):
    """Provide an InterestEngine with memory."""
    return InterestEngine(memory=memory_engine)


@pytest.fixture
def engine_with_llm(mock_llm):
    """Provide an InterestEngine with mock LLM."""
    return InterestEngine(llm=mock_llm)


# ── Verdict enum ────────────────────────────────────────────────


class TestVerdict:
    def test_verdict_values(self):
        assert Verdict.STRONGLY_ALIGNED == "strongly_aligned"
        assert Verdict.MISALIGNED == "misaligned"

    def test_risk_level_values(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.VERY_HIGH == "very_high"


# ── InterestAssessment dataclass ────────────────────────────────


class TestInterestAssessment:
    def test_frozen(self):
        a = InterestAssessment(
            subject="test", verdict=Verdict.NEUTRAL, score=0.0,
            financial_impact=0, time_cost_hours=0, risk_level=RiskLevel.LOW,
            reasoning="test",
        )
        with pytest.raises(AttributeError):
            a.score = 0.5  # type: ignore[misc]

    def test_defaults(self):
        a = InterestAssessment(
            subject="x", verdict=Verdict.NEUTRAL, score=0.0,
            financial_impact=0, time_cost_hours=0, risk_level=RiskLevel.LOW,
            reasoning="r",
        )
        assert a.benefits == []
        assert a.risks == []
        assert a.recommendation == ""
        assert a.knowledge_domains == []
        assert a.timestamp  # auto-populated


# ── assess() ────────────────────────────────────────────────────


class TestAssess:
    def test_neutral_for_generic_subject(self, engine: InterestEngine):
        result = engine.assess("something unrelated")
        assert isinstance(result, InterestAssessment)
        assert result.verdict == Verdict.NEUTRAL
        assert result.score == 0.0

    def test_positive_financial_impact(self, engine: InterestEngine):
        result = engine.assess("New project", financial_impact=5000)
        assert result.score > 0
        assert any("Financial gain" in b for b in result.benefits)

    def test_large_financial_gain_capped_at_04(self, engine: InterestEngine):
        result = engine.assess("Huge deal", financial_impact=1_000_000)
        # Financial scoring caps at 0.4
        assert result.score <= 1.0

    def test_negative_financial_impact_small(self, engine: InterestEngine):
        result = engine.assess("Small expense", financial_impact=-100)
        assert any("Cost" in r for r in result.risks)

    def test_negative_financial_impact_large(self, engine: InterestEngine):
        result = engine.assess("Big expense", financial_impact=-10000)
        assert any("Significant cost" in r for r in result.risks)

    def test_revenue_term_boosts_score(self, engine: InterestEngine):
        result = engine.assess("Build SaaS subscription platform")
        assert result.score > 0
        assert "financial" in result.knowledge_domains

    def test_tech_term_boosts_score(self, engine: InterestEngine):
        result = engine.assess("Build an API for data pipeline")
        assert result.score > 0
        assert "technology" in result.knowledge_domains

    def test_construction_term_boosts_score(self, engine: InterestEngine):
        result = engine.assess("Permit tracking for contractors")
        assert "construction" in result.knowledge_domains

    def test_learning_term_boosts_score(self, engine: InterestEngine):
        result = engine.assess("Learn new skill in machine learning")
        assert "personal_development" in result.knowledge_domains

    def test_automation_boosts_score(self, engine: InterestEngine):
        result = engine.assess("Automate the data pipeline")
        assert any("automation" in b.lower() for b in result.benefits)

    def test_high_time_cost_penalty(self, engine: InterestEngine):
        result = engine.assess("Manual task", time_cost_hours=50)
        assert any("High time investment" in r for r in result.risks)

    def test_moderate_time_cost_penalty(self, engine: InterestEngine):
        result = engine.assess("Some task", time_cost_hours=25)
        assert any("Moderate time investment" in r for r in result.risks)

    def test_very_high_risk_penalty(self, engine: InterestEngine):
        result = engine.assess("Risky move", risk_level="very_high")
        assert result.risk_level == RiskLevel.VERY_HIGH
        assert any("Very high risk" in r for r in result.risks)

    def test_high_risk_penalty(self, engine: InterestEngine):
        result = engine.assess("Risky move", risk_level="high")
        assert any("High risk" in r for r in result.risks)

    def test_invalid_risk_level_defaults_to_medium(self, engine: InterestEngine):
        result = engine.assess("Something", risk_level="invalid_level")
        assert result.risk_level == RiskLevel.MEDIUM

    def test_deal_breaker_large_upfront_capital(self, engine: InterestEngine):
        result = engine.assess("Requires large upfront capital investment")
        assert any("DEAL BREAKER" in r for r in result.risks)
        assert result.score < 0

    def test_deal_breaker_legal_risk(self, engine: InterestEngine):
        result = engine.assess("Venture with legal risk")
        assert any("DEAL BREAKER" in r for r in result.risks)

    def test_deal_breaker_single_client(self, engine: InterestEngine):
        result = engine.assess("Dependent on single client for revenue")
        assert any("DEAL BREAKER" in r for r in result.risks)

    def test_strongly_aligned_verdict(self, engine: InterestEngine):
        result = engine.assess(
            "SaaS subscription API platform with automation",
            financial_impact=10000,
        )
        assert result.verdict == Verdict.STRONGLY_ALIGNED
        assert "PROCEED" in result.recommendation

    def test_misaligned_verdict(self, engine: InterestEngine):
        result = engine.assess("Manual labor with legal risk", risk_level="very_high")
        assert result.verdict in (Verdict.MISALIGNED, Verdict.STRONGLY_MISALIGNED)
        assert "AVOID" in result.recommendation

    def test_neutral_verdict_recommendation(self, engine: InterestEngine):
        result = engine.assess("Something generic")
        assert result.verdict == Verdict.NEUTRAL
        assert "EVALUATE FURTHER" in result.recommendation

    def test_score_clamped_to_range(self, engine: InterestEngine):
        # Stack all negatives
        result = engine.assess(
            "large upfront capital legal risk manual labor single client",
            financial_impact=-20000,
            time_cost_hours=100,
            risk_level="very_high",
        )
        assert result.score >= -1.0

    def test_context_also_analyzed(self, engine: InterestEngine):
        result = engine.assess("Generic thing", context="Build SaaS revenue stream")
        assert result.score > 0


# ── History ─────────────────────────────────────────────────────


class TestHistory:
    def test_assessment_stored_in_history(self, engine: InterestEngine):
        engine.assess("Item 1")
        engine.assess("Item 2")
        history = engine.get_history()
        assert len(history) == 2
        # Most recent first
        assert history[0].subject == "Item 2"

    def test_history_limit(self, engine: InterestEngine):
        for i in range(5):
            engine.assess(f"Item {i}")
        assert len(engine.get_history(limit=3)) == 3


# ── Stats ───────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, engine: InterestEngine):
        s = engine.stats()
        assert s["total_assessments"] == 0
        assert s["avg_score"] == 0
        assert s["aligned_pct"] == 0

    def test_stats_after_assessments(self, engine: InterestEngine):
        engine.assess("SaaS revenue API", financial_impact=5000)
        engine.assess("Something neutral")
        s = engine.stats()
        assert s["total_assessments"] == 2
        assert "aligned" in s
        assert "neutral" in s
        assert isinstance(s["avg_score"], float)


# ── Memory integration ──────────────────────────────────────────


class TestMemoryIntegration:
    def test_assessment_stored_in_memory(self, engine_with_memory, memory_engine):
        before = memory_engine.count()
        engine_with_memory.assess("Build API platform")
        after = memory_engine.count()
        assert after > before


# ── assess_with_llm ─────────────────────────────────────────────


class TestAssessWithLLM:
    @pytest.mark.asyncio
    async def test_fallback_when_no_llm(self, engine: InterestEngine):
        result = await engine.assess_with_llm("Build SaaS", "context")
        assert isinstance(result, InterestAssessment)

    @pytest.mark.asyncio
    async def test_llm_response_parsed(self, engine_with_llm):
        llm_response = json.dumps({
            "score": 0.7,
            "financial_impact": 5000,
            "time_cost_hours": 10,
            "risk_level": "low",
            "benefits": ["Good ROI"],
            "risks": [],
            "recommendation": "Go for it",
            "knowledge_domains": ["tech"],
        })
        engine_with_llm._llm.complete = AsyncMock(return_value=llm_response)
        result = await engine_with_llm.assess_with_llm("New SaaS")
        assert result.verdict == Verdict.STRONGLY_ALIGNED
        assert result.score == 0.7
        assert result.financial_impact == 5000
        assert result.risk_level == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_llm_json_in_code_block(self, engine_with_llm):
        llm_response = '```json\n{"score": 0.3, "financial_impact": 0, "time_cost_hours": 5, "risk_level": "medium", "benefits": [], "risks": [], "recommendation": "OK", "knowledge_domains": []}\n```'
        engine_with_llm._llm.complete = AsyncMock(return_value=llm_response)
        result = await engine_with_llm.assess_with_llm("Something")
        assert result.verdict == Verdict.ALIGNED

    @pytest.mark.asyncio
    async def test_llm_invalid_risk_defaults(self, engine_with_llm):
        llm_response = json.dumps({
            "score": 0.0, "financial_impact": 0, "time_cost_hours": 0,
            "risk_level": "bogus", "benefits": [], "risks": [],
            "recommendation": "", "knowledge_domains": [],
        })
        engine_with_llm._llm.complete = AsyncMock(return_value=llm_response)
        result = await engine_with_llm.assess_with_llm("Test")
        assert result.risk_level == RiskLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back(self, engine_with_llm):
        engine_with_llm._llm.complete = AsyncMock(side_effect=Exception("API down"))
        result = await engine_with_llm.assess_with_llm("Test", "context")
        assert isinstance(result, InterestAssessment)

    @pytest.mark.asyncio
    async def test_llm_score_clamped(self, engine_with_llm):
        llm_response = json.dumps({
            "score": 5.0, "financial_impact": 0, "time_cost_hours": 0,
            "risk_level": "low", "benefits": [], "risks": [],
            "recommendation": "", "knowledge_domains": [],
        })
        engine_with_llm._llm.complete = AsyncMock(return_value=llm_response)
        result = await engine_with_llm.assess_with_llm("Test")
        assert result.score == 1.0


# ── Profile ─────────────────────────────────────────────────────


class TestProfile:
    def test_yohan_profile_has_core_fields(self):
        assert "core_values" in YOHAN_PROFILE
        assert "financial_goals" in YOHAN_PROFILE
        assert "risk_tolerance" in YOHAN_PROFILE
        assert "deal_breakers" in YOHAN_PROFILE
        assert len(YOHAN_PROFILE["core_values"]) > 0
