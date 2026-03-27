"""Tests for the Reflection Engine — self-reflection and action execution."""

from __future__ import annotations

import json

import pytest
from unittest.mock import MagicMock

from backend.core.reflection import ReflectionEngine
from backend.models.memory import MemoryType


@pytest.fixture
def reflection(memory_engine, mock_llm):
    """Provide a ReflectionEngine with temp memory and mock LLM."""
    from backend.core.learning_engine import LearningEngine
    learning = LearningEngine()
    learning.start()
    engine = ReflectionEngine(memory=memory_engine, llm=mock_llm, learning=learning)
    yield engine
    learning.stop()


class TestReflectionParsing:
    def test_parse_valid_json(self, reflection: ReflectionEngine):
        response = json.dumps({
            "observation": "ROOT is improving",
            "insight": "Learning is working well",
            "action": None,
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        result = reflection._parse_and_apply(response, "test", [])
        assert result is not None
        assert result.observation == "ROOT is improving"
        assert result.insight == "Learning is working well"

    def test_parse_json_in_code_block(self, reflection: ReflectionEngine):
        response = '```json\n{"observation": "test", "insight": "insight", "action": null}\n```'
        result = reflection._parse_and_apply(response, "test", [])
        assert result is not None
        assert result.observation == "test"

    def test_parse_invalid_json_fallback(self, reflection: ReflectionEngine):
        result = reflection._parse_and_apply("not valid json", "test", [])
        assert result is not None
        assert result.insight == "(unparsed reflection)"

    def test_parse_creates_new_memories(self, reflection: ReflectionEngine, memory_engine):
        before = memory_engine.count()
        response = json.dumps({
            "observation": "Noticed pattern",
            "insight": "Key learning",
            "action": None,
            "new_memories": [
                {"content": "New learning from reflection", "memory_type": "learning", "tags": ["test"]},
            ],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        reflection._parse_and_apply(response, "test", [])
        assert memory_engine.count() > before


class TestReflectionActionExecution:
    def test_agent_routing_boost(self, reflection: ReflectionEngine):
        """Action mentioning an agent + boost words should adjust routing weight."""
        from backend.models.memory import Reflection
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="Researcher performs well on market tasks",
            insight="Agent routing can be optimized",
            action="Use researcher more for market analysis tasks",
            memories_referenced=[],
        )
        reflection._execute_reflection_action(ref)
        weight = reflection._learning.get_agent_weight("researcher", "market")
        assert weight > 0.5  # Should have been boosted

    def test_skill_creation_queued(self, reflection: ReflectionEngine, memory_engine):
        """Action mentioning skill creation should store a SKILL memory."""
        from backend.models.memory import Reflection
        before = memory_engine.count()
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="Missing capability",
            insight="Need new skill",
            action="Create skill for automated market scanning procedure",
            memories_referenced=[],
        )
        reflection._execute_reflection_action(ref)
        assert memory_engine.count() > before

    def test_goal_stored(self, reflection: ReflectionEngine, memory_engine):
        """Action mentioning a goal should store a GOAL memory."""
        from backend.models.memory import Reflection
        before = memory_engine.count()
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="Need direction",
            insight="Should set objectives",
            action="Set goal to improve trading accuracy to 70%",
            memories_referenced=[],
        )
        reflection._execute_reflection_action(ref)
        assert memory_engine.count() > before

    def test_knowledge_gap_stored(self, reflection: ReflectionEngine, memory_engine):
        """Action about knowledge gaps stores a LEARNING memory."""
        from backend.models.memory import Reflection
        before = memory_engine.count()
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="Missing info",
            insight="Gap in knowledge",
            action="Research and learn about options pricing models",
            memories_referenced=[],
        )
        reflection._execute_reflection_action(ref)
        assert memory_engine.count() > before

    def test_unclassified_action_still_stored(self, reflection: ReflectionEngine, memory_engine):
        """Unclassified actions still get stored as generic learning."""
        from backend.models.memory import Reflection
        before = memory_engine.count()
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="Misc observation",
            insight="Misc insight",
            action="Do something completely unique and novel",
            memories_referenced=[],
        )
        reflection._execute_reflection_action(ref)
        assert memory_engine.count() > before

    def test_no_action_does_nothing(self, reflection: ReflectionEngine, memory_engine):
        """None action should not create any memories."""
        from backend.models.memory import Reflection
        before = memory_engine.count()
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="obs",
            insight="ins",
            action=None,
            memories_referenced=[],
        )
        reflection._execute_reflection_action(ref)
        assert memory_engine.count() == before


class TestExtractCategory:
    def test_market(self):
        assert ReflectionEngine._extract_category("market analysis") == "market"

    def test_trading(self):
        assert ReflectionEngine._extract_category("improve trading") == "trading"

    def test_coding(self):
        assert ReflectionEngine._extract_category("better code generation") == "coding"

    def test_default_general(self):
        assert ReflectionEngine._extract_category("something random") == "general"


class TestReflect:
    @pytest.mark.asyncio
    async def test_reflect_with_mock_llm(self, reflection: ReflectionEngine, mock_llm):
        mock_llm.complete.return_value = json.dumps({
            "observation": "ROOT is functioning",
            "insight": "Systems nominal",
            "action": None,
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        result = await reflection.reflect(trigger="test")
        assert result is not None
        assert result.observation == "ROOT is functioning"

    @pytest.mark.asyncio
    async def test_reflect_without_llm(self, memory_engine):
        engine = ReflectionEngine(memory=memory_engine, llm=None)
        result = await engine.reflect()
        assert result is None

    def test_get_reflections_empty(self, reflection: ReflectionEngine):
        assert reflection.get_reflections() == []
