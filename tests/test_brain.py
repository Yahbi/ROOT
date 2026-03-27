"""Tests for the Brain — routing, learning recording, offline fallback."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.brain import Brain


@pytest.fixture
def brain_deps(memory_engine, mock_llm, mock_plugins, tmp_path):
    """Provide all Brain dependencies."""
    from backend.core.learning_engine import LearningEngine
    from backend.core.reflection import ReflectionEngine
    from backend.core.conversation_store import ConversationStore
    from backend.core.skill_engine import SkillEngine

    with patch("backend.core.learning_engine.LEARNING_DB", tmp_path / "learning.db"):
        learning = LearningEngine()
        learning.start()

    skills = SkillEngine()
    reflection = ReflectionEngine(memory=memory_engine, llm=mock_llm, learning=learning)

    conversations = MagicMock()
    conversations.add_message = MagicMock()
    conversations.current_session_id = "test_session"

    router = MagicMock()
    router.route = AsyncMock(return_value={"agent": None, "confidence": 0.0})

    registry = MagicMock()
    registry.list_agents.return_value = []
    registry.get_agent.return_value = None
    registry.get_connector.return_value = None

    orchestrator = MagicMock()
    money = MagicMock()
    interest = MagicMock()

    return {
        "llm": mock_llm,
        "memory": memory_engine,
        "reflection": reflection,
        "router": router,
        "registry": registry,
        "skills": skills,
        "plugins": mock_plugins,
        "conversations": conversations,
        "money_engine": money,
        "interest_engine": interest,
        "orchestrator": orchestrator,
        "learning_engine": learning,
    }


@pytest.fixture
def brain(brain_deps):
    """Provide a Brain instance with mocked dependencies."""
    return Brain(**brain_deps)


class TestBrainConstruction:
    def test_creates_successfully(self, brain: Brain):
        assert brain is not None

    def test_has_learning_engine(self, brain: Brain):
        assert brain._learning is not None


class TestBestAgentFor:
    def test_returns_fallback_without_learning(self, brain: Brain):
        brain._learning = None
        result = brain._best_agent_for("research", "default_agent")
        assert result == "default_agent"

    def test_returns_fallback_when_no_data(self, brain: Brain):
        result = brain._best_agent_for("nonexistent_category", "fallback")
        assert result == "fallback"

    def test_returns_best_agent_with_data(self, brain: Brain):
        # Record outcomes so researcher is best for research
        for _ in range(5):
            brain._learning.record_agent_outcome(
                agent_id="researcher",
                task_description="research task",
                status="completed",
                result_quality=0.9,
                task_category="research",
            )
        result = brain._best_agent_for("research", "fallback")
        assert result == "researcher"


class TestOfflineFallback:
    def test_offline_brain_attribute(self, brain: Brain):
        assert not hasattr(brain, '_offline_brain') or brain._offline_brain is None

    def test_set_offline_brain(self, brain: Brain):
        mock_offline = MagicMock()
        brain._offline_brain = mock_offline
        assert brain._offline_brain is mock_offline

    def test_degraded_starts_false(self, brain: Brain):
        assert brain._degraded is False


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_returns_response(self, brain: Brain):
        result = await brain.chat("Hello ROOT")
        assert result is not None

    @pytest.mark.asyncio
    async def test_chat_records_conversation(self, brain: Brain, brain_deps):
        await brain.chat("Test message")
        # Verify conversation store was called
        brain_deps["conversations"].add_message.assert_called()
