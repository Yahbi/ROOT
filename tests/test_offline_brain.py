"""Tests for OfflineBrain — chat, knowledge matching, skill matching, responses."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, PropertyMock

from backend.core.offline_brain import OfflineBrain
from backend.core.skill_engine import Skill
from backend.models.memory import MemoryEntry, MemoryType


def _make_skill(name: str = "test_skill", category: str = "coding") -> Skill:
    return Skill(
        name=name,
        category=category,
        description=f"A {name} skill",
        version="1.0.0",
        tags=["test"],
        content="Skill content body",
        path="/tmp/test",
    )


def _make_memory(content: str = "Test memory", mem_type: MemoryType = MemoryType.FACT) -> MemoryEntry:
    return MemoryEntry(
        id="mem_test123",
        content=content,
        memory_type=mem_type,
        tags=["test"],
        source="test",
        confidence=0.9,
    )


@pytest.fixture
def mock_memory():
    m = MagicMock()
    m.search.return_value = []
    m.stats.return_value = {"total": 5}
    m.get_recent.return_value = []
    m.store.return_value = _make_memory()
    return m


@pytest.fixture
def mock_skills():
    s = MagicMock()
    s.search.return_value = []
    s.list_categories.return_value = {}
    s.stats.return_value = {"total": 3, "categories": {}}
    return s


@pytest.fixture
def mock_self_dev():
    sd = MagicMock()
    sd.assess.return_value = {
        "maturity_level": "developing",
        "maturity_score": 0.45,
        "memories": {"total": 5},
        "skills": {"total": 3},
        "evolution_count": 2,
        "capability_gaps": [],
        "recent_evolution": [],
    }
    sd.identify_gaps.return_value = []
    return sd


@pytest.fixture
def mock_context():
    return MagicMock()


@pytest.fixture
def brain(mock_memory, mock_skills, mock_self_dev, mock_context) -> OfflineBrain:
    return OfflineBrain(
        memory=mock_memory,
        skills=mock_skills,
        self_dev=mock_self_dev,
        context=mock_context,
    )


class TestChatBasic:
    @pytest.mark.asyncio
    async def test_returns_chat_message(self, brain: OfflineBrain):
        result = await brain.chat("Hello")
        assert result.role == "assistant"
        assert result.agent_id == "root_offline"
        assert result.content  # non-empty

    @pytest.mark.asyncio
    async def test_increments_interaction_count(self, brain: OfflineBrain):
        await brain.chat("first")
        await brain.chat("second")
        assert brain._interaction_count == 2

    @pytest.mark.asyncio
    async def test_appends_to_conversation(self, brain: OfflineBrain):
        await brain.chat("Hello")
        conv = brain.get_conversation()
        assert len(conv) == 2  # user + assistant
        assert conv[0]["role"] == "user"
        assert conv[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_timestamp_present(self, brain: OfflineBrain):
        result = await brain.chat("hi")
        assert result.timestamp is not None


class TestChatWithMemories:
    @pytest.mark.asyncio
    async def test_uses_memories_in_response(self, brain: OfflineBrain, mock_memory):
        mock_memory.search.return_value = [_make_memory("Python is a language")]
        result = await brain.chat("What is Python?")
        assert "memory" in result.content.lower() or "Python" in result.content

    @pytest.mark.asyncio
    async def test_memory_ids_in_result(self, brain: OfflineBrain, mock_memory):
        mem = _make_memory("fact")
        mock_memory.search.return_value = [mem]
        result = await brain.chat("something")
        assert "mem_test123" in result.memories_used


class TestChatWithSkills:
    @pytest.mark.asyncio
    async def test_uses_skills_in_response(self, brain: OfflineBrain, mock_skills):
        mock_skills.search.return_value = [_make_skill("python_debug")]
        result = await brain.chat("debug my code")
        assert "skill" in result.content.lower() or "python_debug" in result.content


class TestSpecialCommands:
    @pytest.mark.asyncio
    async def test_status_command(self, brain: OfflineBrain):
        result = await brain.chat("status")
        assert "Status" in result.content or "Maturity" in result.content

    @pytest.mark.asyncio
    async def test_how_are_you(self, brain: OfflineBrain):
        result = await brain.chat("how are you")
        assert "Status" in result.content or "Maturity" in result.content

    @pytest.mark.asyncio
    async def test_skills_command(self, brain: OfflineBrain, mock_skills):
        mock_skills.list_categories.return_value = {
            "coding": [_make_skill("python_debug")],
        }
        result = await brain.chat("skills")
        assert "Skill" in result.content or "coding" in result.content

    @pytest.mark.asyncio
    async def test_skills_empty(self, brain: OfflineBrain, mock_skills):
        mock_skills.list_categories.return_value = {}
        result = await brain.chat("skills")
        assert "No skills" in result.content

    @pytest.mark.asyncio
    async def test_remember_command(self, brain: OfflineBrain, mock_memory):
        result = await brain.chat("remember Python was created by Guido")
        assert "Stored in memory" in result.content
        mock_memory.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_assess_command(self, brain: OfflineBrain):
        result = await brain.chat("assess")
        assert "Self-Assessment" in result.content or "Maturity" in result.content

    @pytest.mark.asyncio
    async def test_gaps_command(self, brain: OfflineBrain, mock_self_dev):
        mock_self_dev.identify_gaps.return_value = [
            {"area": "trading", "description": "No trading skills", "suggestion": "Learn trading"},
        ]
        result = await brain.chat("gaps")
        assert "Gap" in result.content or "trading" in result.content

    @pytest.mark.asyncio
    async def test_gaps_empty(self, brain: OfflineBrain, mock_self_dev):
        mock_self_dev.identify_gaps.return_value = []
        result = await brain.chat("gaps")
        assert "well-rounded" in result.content

    @pytest.mark.asyncio
    async def test_knowledge_command(self, brain: OfflineBrain, mock_memory):
        mock_memory.stats.return_value = {
            "total": 10,
            "by_type": {
                "fact": {"count": 5, "avg_confidence": 0.9},
            },
        }
        mock_memory.get_recent.return_value = [_make_memory("recent fact")]
        result = await brain.chat("knowledge")
        assert "Knowledge" in result.content


class TestCouncilTrigger:
    @pytest.mark.asyncio
    async def test_money_trigger_without_engine(self, brain: OfflineBrain):
        # No money engine — council_trigger becomes the response
        result = await brain.chat("make money")
        # Without money engine, council_trigger stays as literal text
        assert result.content  # Should have some content

    @pytest.mark.asyncio
    async def test_money_trigger_with_engine(self, brain: OfflineBrain):
        mock_money = MagicMock()
        session = MagicMock()
        session.total_opportunities = 3
        session.agents_consulted = ["swarm", "miro"]
        session.id = "council_1"
        session.session_duration_seconds = 5.2
        session.top_recommendation = None
        session.opportunities = []
        mock_money.convene_council = MagicMock(return_value=session)

        brain._money = mock_money

        # Make convene_council a coroutine
        import asyncio

        async def fake_council(focus):
            return session

        mock_money.convene_council = fake_council

        result = await brain.chat("strategy council")
        assert "Strategy Council" in result.content


class TestChatStream:
    @pytest.mark.asyncio
    async def test_stream_yields_content(self, brain: OfflineBrain):
        chunks = []
        async for chunk in brain.chat_stream("Hello"):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert chunks[0]  # non-empty


class TestRemember:
    @pytest.mark.asyncio
    async def test_stores_memory(self, brain: OfflineBrain, mock_memory):
        result = await brain.remember("test fact", memory_type="fact", tags=["test"])
        mock_memory.store.assert_called_once()
        call_arg = mock_memory.store.call_args[0][0]
        assert call_arg.content == "test fact"
        assert call_arg.memory_type == MemoryType.FACT

    @pytest.mark.asyncio
    async def test_invalid_memory_type_defaults_to_fact(self, brain: OfflineBrain, mock_memory):
        await brain.remember("test", memory_type="invalid_type")
        call_arg = mock_memory.store.call_args[0][0]
        assert call_arg.memory_type == MemoryType.FACT


class TestDelegate:
    @pytest.mark.asyncio
    async def test_returns_error(self, brain: OfflineBrain):
        result = await brain.delegate("agent1", "some task")
        assert "error" in result
        assert "offline" in result["error"].lower()


class TestConversation:
    @pytest.mark.asyncio
    async def test_get_conversation(self, brain: OfflineBrain):
        await brain.chat("msg1")
        await brain.chat("msg2")
        conv = brain.get_conversation()
        assert len(conv) == 4  # 2 user + 2 assistant

    @pytest.mark.asyncio
    async def test_clear_conversation(self, brain: OfflineBrain):
        await brain.chat("msg1")
        brain.clear_conversation()
        assert brain.get_conversation() == []

    def test_get_conversation_returns_copy(self, brain: OfflineBrain):
        conv = brain.get_conversation()
        conv.append({"role": "user", "content": "injected"})
        assert len(brain.get_conversation()) == 0


class TestNoKnowledgeResponse:
    @pytest.mark.asyncio
    async def test_offline_guidance(self, brain: OfflineBrain):
        # No memories, no skills — should show offline guidance
        result = await brain.chat("random query with no matches")
        assert "offline" in result.content.lower() or "API" in result.content
