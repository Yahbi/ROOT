"""Tests for the Money Engine — Strategy Council."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.money_engine import (
    CouncilSession,
    MoneyEngine,
    Opportunity,
    OpportunityType,
    RiskLevel,
    _CLUSTER_META,
)


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    # Return fake MemoryEntry-like objects from search
    entry1 = MagicMock(content="trading strategy backtest BTC/USD with 65% win rate", confidence=0.8, tags=["trading", "crypto"])
    entry2 = MagicMock(content="automation workflow for data scraping pipeline", confidence=0.7, tags=["automation", "scraping"])
    entry3 = MagicMock(content="ai agent orchestration saas product idea", confidence=0.9, tags=["ai", "saas", "product"])
    mem.search.return_value = [entry1, entry2, entry3]
    mem.store = MagicMock()
    return mem


@pytest.fixture
def mock_skills():
    skills = MagicMock()
    skills.search.return_value = []
    return skills


@pytest.fixture
def mock_self_dev():
    sd = MagicMock()
    sd.propose_improvement = MagicMock()
    return sd


@pytest.fixture
def engine(mock_memory, mock_skills, mock_self_dev):
    return MoneyEngine(
        memory=mock_memory,
        skills=mock_skills,
        self_dev=mock_self_dev,
    )


@pytest.fixture
def engine_with_llm(mock_memory, mock_skills, mock_self_dev):
    llm = AsyncMock()
    collab = AsyncMock()
    bus = MagicMock()
    return MoneyEngine(
        memory=mock_memory,
        skills=mock_skills,
        self_dev=mock_self_dev,
        llm=llm,
        collab=collab,
        bus=bus,
    )


# ── Offline Council ────────────────────────────────────────


@pytest.mark.asyncio
async def test_offline_council_produces_opportunities(engine):
    session = await engine.convene_council()
    assert isinstance(session, CouncilSession)
    assert session.mode == "offline"
    assert session.total_opportunities > 0
    assert len(session.opportunities) == session.total_opportunities
    assert all(isinstance(o, Opportunity) for o in session.opportunities)


@pytest.mark.asyncio
async def test_offline_council_with_focus(engine):
    session = await engine.convene_council(focus="trading")
    assert session.mode == "offline"
    assert session.total_opportunities > 0


@pytest.mark.asyncio
async def test_offline_council_stores_to_memory(engine, mock_memory):
    session = await engine.convene_council()
    assert mock_memory.store.called
    # Should store up to 3 top opportunities
    assert mock_memory.store.call_count <= 3


@pytest.mark.asyncio
async def test_offline_council_logs_evolution(engine, mock_self_dev):
    await engine.convene_council()
    mock_self_dev.propose_improvement.assert_called_once()


# ── _generate_from_intelligence ─────────────────────────────


def test_generate_from_intelligence_uses_memory(engine, mock_memory):
    insights, skills = engine._gather_intelligence()
    opps = engine._generate_from_intelligence(insights, skills, focus=None)

    # Should produce opportunities based on the mock memory entries
    assert len(opps) > 0
    assert all(isinstance(o, Opportunity) for o in opps)
    # Confidence is based on evidence strength
    for o in opps:
        assert 0.0 < o.confidence_score <= 0.95


def test_generate_from_intelligence_descriptions_contain_memory(engine, mock_memory):
    insights, skills = engine._gather_intelligence()
    opps = engine._generate_from_intelligence(insights, skills, focus=None)
    # Descriptions should contain actual memory content snippets
    for o in opps:
        assert "Based on" in o.description


def test_generate_from_intelligence_caps_at_5(engine, mock_memory):
    insights, skills = engine._gather_intelligence()
    opps = engine._generate_from_intelligence(insights, skills, focus=None)
    assert len(opps) <= 5


# ── Stats ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_empty(engine):
    s = engine.stats()
    assert s["total_sessions"] == 0
    assert s["total_opportunities"] == 0
    assert s["avg_confidence"] == 0.0


@pytest.mark.asyncio
async def test_stats_after_session(engine):
    await engine.convene_council()
    s = engine.stats()
    assert s["total_sessions"] == 1
    assert s["total_opportunities"] > 0
    assert 0.0 < s["avg_confidence"] <= 1.0
    assert isinstance(s["opportunity_types"], list)


# ── Sessions / Opportunities API ────────────────────────────


@pytest.mark.asyncio
async def test_get_sessions(engine):
    assert engine.get_sessions() == []
    await engine.convene_council()
    sessions = engine.get_sessions()
    assert len(sessions) == 1
    assert sessions[0].mode == "offline"


@pytest.mark.asyncio
async def test_get_latest_opportunities(engine):
    assert engine.get_latest_opportunities() == []
    await engine.convene_council()
    opps = engine.get_latest_opportunities(limit=2)
    assert len(opps) <= 2


@pytest.mark.asyncio
async def test_get_opportunity_by_id(engine):
    session = await engine.convene_council()
    if session.opportunities:
        opp = session.opportunities[0]
        found = engine.get_opportunity(opp.id)
        assert found is not None
        assert found.id == opp.id


@pytest.mark.asyncio
async def test_get_opportunity_not_found(engine):
    assert engine.get_opportunity("nonexistent") is None


# ── Online Council Fallback ─────────────────────────────────


@pytest.mark.asyncio
async def test_online_falls_back_without_llm(engine):
    """Without LLM/collab, online council falls back to offline."""
    session = await engine.convene_council_online()
    assert session.mode == "offline"


# ── JSON Parsing ────────────────────────────────────────────


def test_parse_opportunities_json_valid():
    raw = json.dumps([{
        "title": "Test Opp",
        "description": "A test",
        "type": "trading",
        "risk": "high",
        "confidence": 0.85,
        "estimated_monthly_revenue": 5000,
        "time_to_first_revenue_days": 7,
        "capital_required": 1000,
        "action_steps": ["step1"],
        "agent_sources": ["swarm"],
        "tags": ["test"],
    }])
    opps = MoneyEngine._parse_opportunities_json(raw)
    assert len(opps) == 1
    assert opps[0].title == "Test Opp"
    assert opps[0].opportunity_type == OpportunityType.TRADING
    assert opps[0].risk_level == RiskLevel.HIGH
    assert opps[0].confidence_score == 0.85


def test_parse_opportunities_json_markdown_fenced():
    raw = '```json\n[{"title":"X","description":"Y","type":"saas","risk":"low","confidence":0.5}]\n```'
    opps = MoneyEngine._parse_opportunities_json(raw)
    assert len(opps) == 1
    assert opps[0].opportunity_type == OpportunityType.SaaS


def test_parse_opportunities_json_invalid():
    opps = MoneyEngine._parse_opportunities_json("not json at all")
    assert opps == []


def test_parse_opportunities_json_bad_type_defaults():
    raw = json.dumps([{"title": "X", "type": "invalid_type", "risk": "invalid_risk"}])
    opps = MoneyEngine._parse_opportunities_json(raw)
    assert len(opps) == 1
    assert opps[0].opportunity_type == OpportunityType.SaaS  # default
    assert opps[0].risk_level == RiskLevel.MEDIUM  # default


# ── Immutability ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sessions_list_is_immutable(engine):
    await engine.convene_council()
    sessions_before = engine.get_sessions()
    await engine.convene_council()
    sessions_after = engine.get_sessions()
    # New session added without mutating old list
    assert len(sessions_after) == 2
    assert len(sessions_before) == 1  # original reference unchanged


def test_opportunity_is_frozen():
    opp = Opportunity(
        id="test", title="T", description="D",
        opportunity_type=OpportunityType.TRADING,
        risk_level=RiskLevel.LOW, confidence_score=0.5,
    )
    with pytest.raises(AttributeError):
        opp.title = "changed"  # type: ignore[misc]
