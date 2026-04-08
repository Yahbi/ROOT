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
            "topic": "agents",
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        result = await reflection.reflect(trigger="test")
        assert result is not None
        assert result.observation == "ROOT is functioning"
        assert result.topic == "agents"

    @pytest.mark.asyncio
    async def test_reflect_without_llm(self, memory_engine):
        engine = ReflectionEngine(memory=memory_engine, llm=None)
        result = await engine.reflect()
        assert result is None

    def test_get_reflections_empty(self, reflection: ReflectionEngine):
        assert reflection.get_reflections() == []

    @pytest.mark.asyncio
    async def test_reflect_deep_mode(self, reflection: ReflectionEngine, mock_llm):
        """Deep mode should set depth='deep' and capture evidence."""
        mock_llm.complete.return_value = json.dumps({
            "observation": "Detailed observation with evidence",
            "evidence": ["memory_id_1 shows X", "memory_id_2 shows Y"],
            "insight": "Evidence-backed insight about system performance",
            "action": "Research and learn more about agent routing",
            "topic": "agents",
            "contradictions_found": [],
            "impact_assessment": "high",
            "follow_up_topics": ["routing"],
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        result = await reflection.reflect(trigger="test", deep=True)
        assert result is not None
        assert result.depth == "deep"
        assert len(result.evidence) == 2
        assert result.topic == "agents"

    @pytest.mark.asyncio
    async def test_reflect_deep_convenience(self, reflection: ReflectionEngine, mock_llm):
        """reflect_deep() should behave same as reflect(deep=True)."""
        mock_llm.complete.return_value = json.dumps({
            "observation": "obs",
            "insight": "ins",
            "action": None,
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        result = await reflection.reflect_deep(trigger="deep-test")
        assert result is not None
        assert result.depth == "deep"


class TestReflectionScheduling:
    def test_pick_scheduled_topic_empty(self, reflection: ReflectionEngine):
        """No history → no topic suggested."""
        assert reflection._pick_scheduled_topic() is None

    def test_pick_scheduled_topic_fresh(self, reflection: ReflectionEngine):
        """Topic reflected on just now should NOT be suggested again."""
        from datetime import datetime, timezone
        reflection._topic_last_reflected["trading"] = datetime.now(timezone.utc)
        # Fresh topic should not be returned (< 30 min ago)
        result = reflection._pick_scheduled_topic()
        assert result is None

    def test_pick_scheduled_topic_stale(self, reflection: ReflectionEngine):
        """Topic reflected on 2 hours ago SHOULD be suggested."""
        from datetime import datetime, timezone, timedelta
        reflection._topic_last_reflected["trading"] = datetime.now(timezone.utc) - timedelta(hours=2)
        result = reflection._pick_scheduled_topic()
        assert result == "trading"

    def test_picks_oldest_topic(self, reflection: ReflectionEngine):
        """Should pick the topic with the oldest last-reflected timestamp."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        reflection._topic_last_reflected["trading"] = now - timedelta(hours=3)
        reflection._topic_last_reflected["memory"] = now - timedelta(hours=5)
        reflection._topic_last_reflected["agents"] = now - timedelta(hours=1)
        result = reflection._pick_scheduled_topic()
        assert result == "memory"  # oldest

    @pytest.mark.asyncio
    async def test_scheduling_updated_after_reflect(self, reflection: ReflectionEngine, mock_llm):
        """After reflecting, topic_last_reflected should be updated."""
        mock_llm.complete.return_value = json.dumps({
            "observation": "obs",
            "insight": "ins",
            "action": None,
            "topic": "trading",
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        assert "trading" not in reflection._topic_last_reflected
        await reflection.reflect(trigger="test")
        assert "trading" in reflection._topic_last_reflected


class TestReflectionChains:
    @pytest.mark.asyncio
    async def test_chain_produces_reflections(self, reflection: ReflectionEngine, mock_llm):
        """reflect_chain() should return multiple linked reflections."""
        mock_llm.complete.return_value = json.dumps({
            "observation": "Chain step observation",
            "insight": "Chain step insight",
            "action": None,
            "topic": "trading",
            "evidence": [],
            "contradictions_found": [],
            "impact_assessment": "medium",
            "follow_up_topics": [],
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        chain = await reflection.reflect_chain("trading", steps=2)
        assert len(chain) == 2

    @pytest.mark.asyncio
    async def test_chain_links_parent_ids(self, reflection: ReflectionEngine, mock_llm):
        """Each step (after first) should reference the previous reflection."""
        mock_llm.complete.return_value = json.dumps({
            "observation": "obs",
            "insight": "insight " + "x" * 60,
            "action": "research and learn more",
            "topic": "memory",
            "evidence": [],
            "contradictions_found": [],
            "impact_assessment": "low",
            "follow_up_topics": [],
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        chain = await reflection.reflect_chain("memory", steps=3)
        assert len(chain) == 3
        # First has no parent, subsequent ones should have increasing chain depth
        assert chain[0].chain_depth == 0
        assert chain[1].chain_depth == 1
        assert chain[2].chain_depth == 2

    @pytest.mark.asyncio
    async def test_chain_depth_cap(self, reflection: ReflectionEngine, mock_llm):
        """Steps are capped at MAX_CHAIN_DEPTH."""
        mock_llm.complete.return_value = json.dumps({
            "observation": "obs",
            "insight": "ins",
            "action": None,
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        chain = await reflection.reflect_chain("topic", steps=10)  # request 10, cap at 3
        assert len(chain) <= ReflectionEngine.MAX_CHAIN_DEPTH

    @pytest.mark.asyncio
    async def test_chain_without_llm(self, memory_engine):
        """reflect_chain() without LLM returns empty list."""
        engine = ReflectionEngine(memory=memory_engine, llm=None)
        chain = await engine.reflect_chain("trading")
        assert chain == []


class TestQualityScoring:
    def test_score_quality_sync_high_score(self, reflection: ReflectionEngine):
        """Reflection with action, long insight, evidence, and topic gets high score."""
        from backend.models.memory import Reflection
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="Good observation",
            insight="A very specific and detailed insight about system behavior that is non-trivial",
            action="Create skill for automated market scanning procedure with specific steps",
            topic="trading",
            depth="deep",
            evidence=["evidence A", "evidence B", "evidence C"],
            memories_referenced=[],
        )
        scored = reflection._score_quality_sync(ref)
        assert scored.quality_score is not None
        assert scored.quality_score >= 0.7  # action + long insight + evidence + topic
        assert scored.quality_rationale is not None

    def test_score_quality_sync_low_score(self, reflection: ReflectionEngine):
        """Reflection with no action, short insight, no evidence gets low score."""
        from backend.models.memory import Reflection
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="obs",
            insight="short",
            action=None,
            memories_referenced=[],
        )
        scored = reflection._score_quality_sync(ref)
        assert scored.quality_score is not None
        assert scored.quality_score <= 0.3

    def test_score_quality_sync_clamps_to_1(self, reflection: ReflectionEngine):
        """Score should never exceed 1.0."""
        from backend.models.memory import Reflection
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="obs",
            insight="A" * 200,
            action="Create a new skill for trading research investigation",
            topic="trading",
            depth="deep",
            evidence=["e1", "e2", "e3", "e4", "e5"],
            chain_depth=3,
            memories_referenced=[],
        )
        scored = reflection._score_quality_sync(ref)
        assert scored.quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_score_quality_async(self, reflection: ReflectionEngine, mock_llm):
        """Async LLM quality scoring should update score and rationale."""
        mock_llm.complete.return_value = json.dumps({
            "score": 0.82,
            "rationale": "Clear insight with specific action",
            "improvement_suggestion": None,
        })
        from backend.models.memory import Reflection
        ref = Reflection(
            id="ref_test",
            trigger="test",
            observation="obs",
            insight="ins",
            memories_referenced=[],
        )
        scored = await reflection.score_reflection_quality(ref)
        assert scored.quality_score == 0.82
        assert "Clear insight" in scored.quality_rationale


class TestMetaReflection:
    @pytest.mark.asyncio
    async def test_meta_reflect_needs_enough_reflections(self, reflection: ReflectionEngine):
        """Meta-reflection should skip if fewer than 3 reflections exist."""
        result = await reflection.meta_reflect()
        assert result is None

    @pytest.mark.asyncio
    async def test_meta_reflect_runs_with_history(self, reflection: ReflectionEngine, mock_llm):
        """Meta-reflection should run when there is enough history."""
        from backend.models.memory import Reflection
        # Seed reflections
        for i in range(5):
            reflection._reflections.append(Reflection(
                id=f"ref_{i:06d}",
                trigger="test",
                observation=f"Observation {i}",
                insight=f"Insight {i} - detailed and long to meet threshold",
                action="research and learn more" if i % 2 == 0 else None,
                topic="trading" if i < 3 else "memory",
                memories_referenced=[],
            ))

        mock_llm.complete.return_value = json.dumps({
            "observation": "Reflections have been consistent but miss agents topic",
            "insight": "ROOT under-reflects on agent performance",
            "action": "Set goal to reflect on agents weekly",
            "topic": "meta-reflection",
            "quality_trend": "stable",
            "blind_spots": ["agents"],
            "high_impact_reflection_ids": ["ref_000000"],
            "new_memories": [],
            "memories_to_supersede": [],
            "confidence_adjustments": [],
        })
        result = await reflection.meta_reflect()
        assert result is not None
        assert result.topic == "meta-reflection"
        assert result.insight != ""


class TestReflectionArchiving:
    @pytest.mark.asyncio
    async def test_archive_empty_when_no_old_reflections(self, reflection: ReflectionEngine, mock_llm):
        """Archiving should produce nothing when all reflections are recent."""
        from backend.models.memory import Reflection
        reflection._reflections.append(Reflection(
            id="ref_fresh",
            trigger="test",
            observation="obs",
            insight="ins",
            memories_referenced=[],
        ))
        result = await reflection.archive_old_reflections()
        assert result == []

    @pytest.mark.asyncio
    async def test_archive_old_reflections(self, reflection: ReflectionEngine, mock_llm):
        """Old reflections should be archived with key takeaway."""
        from backend.models.memory import Reflection
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        reflection._reflections.append(Reflection(
            id="ref_old001",
            trigger="test",
            observation="Old observation",
            insight="Old insight about trading",
            action=None,
            topic="trading",
            memories_referenced=[],
            created_at=old_ts,
        ))

        mock_llm.complete.return_value = json.dumps({
            "key_takeaway": "Trading reflections showed need for better signal detection",
            "dominant_topic": "trading",
            "trend_tags": ["trading", "signal-detection"],
        })
        archived = await reflection.archive_old_reflections()
        assert len(archived) == 1
        assert archived[0].archived is True
        assert "trading" in archived[0].key_takeaway.lower()
        assert archived[0].trend_tags != []

    @pytest.mark.asyncio
    async def test_archive_stores_takeaway_in_memory(self, reflection: ReflectionEngine, mock_llm, memory_engine):
        """Archiving should store the takeaway as a REFLECTION memory."""
        from backend.models.memory import Reflection
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        reflection._reflections.append(Reflection(
            id="ref_old002",
            trigger="test",
            observation="obs",
            insight="ins",
            topic="memory",
            memories_referenced=[],
            created_at=old_ts,
        ))
        mock_llm.complete.return_value = json.dumps({
            "key_takeaway": "Memory consolidation is key for system reliability",
            "dominant_topic": "memory",
            "trend_tags": ["memory", "reliability"],
        })
        before = memory_engine.count()
        await reflection.archive_old_reflections()
        assert memory_engine.count() > before


class TestTrendDetection:
    def test_detect_trends_empty(self, reflection: ReflectionEngine):
        """Empty reflection history returns empty dict."""
        assert reflection.detect_trends() == {}

    def test_detect_trends_basic(self, reflection: ReflectionEngine):
        """Basic trend detection works with a handful of reflections."""
        from backend.models.memory import Reflection
        topics = ["trading", "trading", "memory", "agents", "trading"]
        for i, topic in enumerate(topics):
            reflection._reflections.append(Reflection(
                id=f"ref_{i:06d}",
                trigger="test",
                observation="obs",
                insight=f"Root system analysis shows {topic} pattern in behavior",
                action="research and learn more" if i % 2 == 0 else None,
                topic=topic,
                quality_score=0.5 + i * 0.05,
                memories_referenced=[],
            ))

        trends = reflection.detect_trends()
        assert trends["total_reflections"] == 5
        assert trends["top_topics"][0]["topic"] == "trading"
        assert trends["top_topics"][0]["count"] == 3
        assert 0.0 <= trends["action_rate"] <= 1.0
        assert "recurring_insights" in trends

    def test_detect_trends_quality_trend_improving(self, reflection: ReflectionEngine):
        """Quality trend detection: scores going up → 'improving'."""
        from backend.models.memory import Reflection
        scores = [0.2, 0.3, 0.4, 0.5, 0.7, 0.8, 0.85, 0.9]  # clearly improving
        for i, score in enumerate(scores):
            reflection._reflections.append(Reflection(
                id=f"ref_{i:06d}",
                trigger="test",
                observation="obs",
                insight="ins",
                quality_score=score,
                memories_referenced=[],
            ))
        trends = reflection.detect_trends()
        assert trends["quality_trend"] == "improving"

    def test_detect_trends_quality_trend_declining(self, reflection: ReflectionEngine):
        """Quality trend detection: scores going down → 'declining'."""
        from backend.models.memory import Reflection
        scores = [0.9, 0.85, 0.7, 0.6, 0.3, 0.2, 0.15, 0.1]  # clearly declining
        for i, score in enumerate(scores):
            reflection._reflections.append(Reflection(
                id=f"ref_{i:06d}",
                trigger="test",
                observation="obs",
                insight="ins",
                quality_score=score,
                memories_referenced=[],
            ))
        trends = reflection.detect_trends()
        assert trends["quality_trend"] == "declining"

    def test_detect_trends_stale_topics(self, reflection: ReflectionEngine):
        """Topics not reflected on in > 7 days should appear in stale_topics."""
        from datetime import datetime, timezone, timedelta
        from backend.models.memory import Reflection
        reflection._reflections.append(Reflection(
            id="ref_000000",
            trigger="test",
            observation="obs",
            insight="ins",
            memories_referenced=[],
        ))
        reflection._topic_last_reflected["stale-topic"] = (
            datetime.now(timezone.utc) - timedelta(days=10)
        )
        trends = reflection.detect_trends()
        assert "stale-topic" in trends["stale_topics"]

    def test_get_reflections_filtered_by_topic(self, reflection: ReflectionEngine):
        """get_reflections() with topic filter returns only matching reflections."""
        from backend.models.memory import Reflection
        reflection._reflections.extend([
            Reflection(id="r1", trigger="t", observation="o", insight="i", topic="trading", memories_referenced=[]),
            Reflection(id="r2", trigger="t", observation="o", insight="i", topic="memory", memories_referenced=[]),
            Reflection(id="r3", trigger="t", observation="o", insight="i", topic="trading", memories_referenced=[]),
        ])
        trading = reflection.get_reflections(topic="trading")
        assert len(trading) == 2
        assert all(r.topic == "trading" for r in trading)

    def test_get_reflections_filtered_by_archived(self, reflection: ReflectionEngine):
        """get_reflections() with archived filter works."""
        from backend.models.memory import Reflection
        reflection._reflections.extend([
            Reflection(id="r1", trigger="t", observation="o", insight="i", archived=True, memories_referenced=[]),
            Reflection(id="r2", trigger="t", observation="o", insight="i", archived=False, memories_referenced=[]),
        ])
        active = reflection.get_reflections(archived=False)
        archived = reflection.get_reflections(archived=True)
        assert len(active) == 1
        assert len(archived) == 1


class TestExtractJson:
    def test_plain_json(self):
        text = '{"key": "value"}'
        assert ReflectionEngine._extract_json(text) == '{"key": "value"}'

    def test_json_in_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = ReflectionEngine._extract_json(text)
        assert result == '{"key": "value"}'

    def test_json_in_plain_code_block(self):
        text = '```\n{"key": "value"}\n```'
        result = ReflectionEngine._extract_json(text)
        assert result == '{"key": "value"}'
