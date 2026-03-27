"""Tests for ContextManager — compression, windowing, token estimation."""

from __future__ import annotations

import pytest

from backend.core.context_manager import (
    CHARS_PER_TOKEN,
    COMPRESS_THRESHOLD,
    PROTECT_FIRST_N,
    PROTECT_LAST_N,
    CompressionResult,
    ContextManager,
)


@pytest.fixture
def manager() -> ContextManager:
    return ContextManager()


def _make_messages(n: int, content_len: int = 50) -> list[dict[str, str]]:
    """Create n messages with given content length."""
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i} " + "x" * content_len}
        for i in range(n)
    ]


class TestCompressionResultDataclass:
    def test_frozen(self):
        result = CompressionResult(
            original_turns=10, compressed_turns=5, summary="s", chars_saved=100,
        )
        with pytest.raises(AttributeError):
            result.original_turns = 20  # type: ignore[misc]


class TestShouldCompress:
    def test_small_context_no_compression(self, manager: ContextManager):
        messages = _make_messages(3, content_len=10)
        assert manager.should_compress(messages) is False

    def test_large_context_triggers_compression(self):
        # Create context that exceeds 85% of max tokens
        max_tokens = 1000
        mgr = ContextManager(max_tokens=max_tokens, threshold=0.85)
        # Need chars > max_tokens * threshold * CHARS_PER_TOKEN
        target_chars = int(max_tokens * 0.85 * CHARS_PER_TOKEN) + 100
        messages = [{"role": "user", "content": "x" * target_chars}]
        assert mgr.should_compress(messages) is True

    def test_threshold_boundary(self):
        max_tokens = 100
        mgr = ContextManager(max_tokens=max_tokens, threshold=0.5)
        # Exactly at threshold: 100 * 0.5 = 50 tokens = 200 chars
        messages = [{"role": "user", "content": "x" * 200}]
        assert mgr.should_compress(messages) is True

    def test_empty_messages(self, manager: ContextManager):
        assert manager.should_compress([]) is False

    def test_handles_missing_content(self, manager: ContextManager):
        messages = [{"role": "user"}, {"role": "assistant"}]
        assert manager.should_compress(messages) is False


class TestCompress:
    def test_short_conversation_unchanged(self, manager: ContextManager):
        # Fewer than PROTECT_FIRST_N + PROTECT_LAST_N + 1 messages
        messages = _make_messages(PROTECT_FIRST_N + PROTECT_LAST_N)
        compressed, result = manager.compress(messages)
        assert len(compressed) == len(messages)
        assert result.chars_saved == 0
        assert result.summary == ""

    def test_compresses_middle_turns(self, manager: ContextManager):
        n = PROTECT_FIRST_N + PROTECT_LAST_N + 5
        messages = _make_messages(n)
        compressed, result = manager.compress(messages)
        # head (3) + summary (1) + tail (4) = 8
        assert len(compressed) == PROTECT_FIRST_N + 1 + PROTECT_LAST_N
        assert result.original_turns == n
        assert result.compressed_turns == PROTECT_FIRST_N + 1 + PROTECT_LAST_N

    def test_preserves_head_and_tail(self, manager: ContextManager):
        n = 20
        messages = _make_messages(n)
        compressed, _ = manager.compress(messages)
        # First N messages preserved
        for i in range(PROTECT_FIRST_N):
            assert compressed[i]["content"] == messages[i]["content"]
        # Last N messages preserved
        for i in range(1, PROTECT_LAST_N + 1):
            assert compressed[-i]["content"] == messages[-i]["content"]

    def test_summary_message_is_user_role(self, manager: ContextManager):
        messages = _make_messages(15)
        compressed, _ = manager.compress(messages)
        summary_msg = compressed[PROTECT_FIRST_N]
        assert summary_msg["role"] == "user"
        assert "[Context compressed" in summary_msg["content"]

    def test_compression_count_increments(self, manager: ContextManager):
        messages = _make_messages(15)
        assert manager.compression_count == 0
        manager.compress(messages)
        assert manager.compression_count == 1
        manager.compress(messages)
        assert manager.compression_count == 2

    def test_summary_contains_middle_content(self, manager: ContextManager):
        messages = _make_messages(15)
        _, result = manager.compress(messages)
        assert "Previous conversation summary" in result.summary

    def test_chars_saved_nonnegative(self, manager: ContextManager):
        messages = _make_messages(15, content_len=5)
        _, result = manager.compress(messages)
        assert result.chars_saved >= 0

    def test_no_compression_count_for_short(self, manager: ContextManager):
        messages = _make_messages(3)
        manager.compress(messages)
        assert manager.compression_count == 0


class TestWindowed:
    def test_short_conversation_unchanged(self, manager: ContextManager):
        messages = _make_messages(5)
        result = manager.windowed(messages, max_turns=10)
        assert len(result) == 5

    def test_truncates_to_max_turns(self, manager: ContextManager):
        messages = _make_messages(20)
        result = manager.windowed(messages, max_turns=10)
        assert len(result) == 10

    def test_keeps_most_recent(self, manager: ContextManager):
        messages = _make_messages(20)
        result = manager.windowed(messages, max_turns=5)
        assert result[-1]["content"] == messages[-1]["content"]
        assert result[0]["content"] == messages[15]["content"]

    def test_returns_new_list(self, manager: ContextManager):
        messages = _make_messages(5)
        result = manager.windowed(messages)
        assert result is not messages

    def test_exact_max_turns(self, manager: ContextManager):
        messages = _make_messages(10)
        result = manager.windowed(messages, max_turns=10)
        assert len(result) == 10


class TestEstimateTokens:
    def test_empty_messages(self, manager: ContextManager):
        assert manager.estimate_tokens([]) == 0

    def test_calculates_from_chars(self, manager: ContextManager):
        messages = [{"role": "user", "content": "x" * 400}]
        assert manager.estimate_tokens(messages) == 400 // CHARS_PER_TOKEN

    def test_multiple_messages(self, manager: ContextManager):
        messages = [
            {"role": "user", "content": "x" * 100},
            {"role": "assistant", "content": "y" * 200},
        ]
        assert manager.estimate_tokens(messages) == 300 // CHARS_PER_TOKEN


class TestStats:
    def test_initial_stats(self, manager: ContextManager):
        stats = manager.stats()
        assert stats["compressions_done"] == 0
        assert stats["max_tokens"] == 180_000
        assert stats["threshold"] == COMPRESS_THRESHOLD

    def test_stats_after_compression(self, manager: ContextManager):
        messages = _make_messages(15)
        manager.compress(messages)
        stats = manager.stats()
        assert stats["compressions_done"] == 1

    def test_custom_config(self):
        mgr = ContextManager(max_tokens=50_000, threshold=0.7)
        stats = mgr.stats()
        assert stats["max_tokens"] == 50_000
        assert stats["threshold"] == 0.7
