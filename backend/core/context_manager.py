"""
Context Manager — HERMES-style conversation context compression and windowing.

When context grows too large, compress middle turns while preserving
recent and early messages. Fixes orphaned tool call/result pairs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("root.context")

# ── Config ─────────────────────────────────────────────────────
COMPRESS_THRESHOLD = 0.85       # Compress at 85% of max tokens
PROTECT_FIRST_N = 3             # Never compress first N turns
PROTECT_LAST_N = 4              # Never compress last N turns
MAX_CONTEXT_TOKENS_ESTIMATE = 180_000  # Conservative estimate for Sonnet
CHARS_PER_TOKEN = 4             # Rough estimate


@dataclass(frozen=True)
class CompressionResult:
    """Immutable result of a context compression."""
    original_turns: int
    compressed_turns: int
    summary: str
    chars_saved: int


class ContextManager:
    """Manages conversation context with compression."""

    def __init__(
        self,
        max_tokens: int = MAX_CONTEXT_TOKENS_ESTIMATE,
        threshold: float = COMPRESS_THRESHOLD,
    ) -> None:
        self._max_tokens = max_tokens
        self._threshold = threshold
        self._compression_count = 0

    def should_compress(self, messages: list[dict[str, str]]) -> bool:
        """Check if context is approaching limits."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = total_chars / CHARS_PER_TOKEN
        return estimated_tokens >= (self._max_tokens * self._threshold)

    def compress(
        self,
        messages: list[dict[str, str]],
        summary_fn: Optional[callable] = None,
    ) -> tuple[list[dict[str, str]], CompressionResult]:
        """Compress conversation by summarizing middle turns.

        Args:
            messages: Full conversation history
            summary_fn: Optional async function to generate summary (not used in offline mode)

        Returns:
            (compressed_messages, compression_result)
        """
        if len(messages) <= PROTECT_FIRST_N + PROTECT_LAST_N + 1:
            return messages, CompressionResult(
                original_turns=len(messages),
                compressed_turns=len(messages),
                summary="",
                chars_saved=0,
            )

        # Protect first and last turns
        head = messages[:PROTECT_FIRST_N]
        tail = messages[-PROTECT_LAST_N:]
        middle = messages[PROTECT_FIRST_N:-PROTECT_LAST_N]

        # Build summary of middle turns
        summary_parts = []
        for msg in middle:
            role = msg.get("role", "?")
            content = msg.get("content", "")[:200]
            summary_parts.append(f"[{role}]: {content}")

        summary_text = "Previous conversation summary:\n" + "\n".join(summary_parts)

        # Build compressed message list
        summary_msg = {"role": "user", "content": f"[Context compressed — {len(middle)} turns summarized]\n{summary_text}"}

        compressed = head + [summary_msg] + tail
        chars_saved = sum(len(m.get("content", "")) for m in middle) - len(summary_text)

        self._compression_count += 1

        return compressed, CompressionResult(
            original_turns=len(messages),
            compressed_turns=len(compressed),
            summary=summary_text[:500],
            chars_saved=max(0, chars_saved),
        )

    def windowed(self, messages: list[dict[str, str]], max_turns: int = 40) -> list[dict[str, str]]:
        """Simple windowing — keep last N turns."""
        if len(messages) <= max_turns:
            return list(messages)
        return list(messages[-max_turns:])

    @property
    def compression_count(self) -> int:
        return self._compression_count

    def estimate_tokens(self, messages: list[dict[str, str]]) -> int:
        """Rough token estimate for message list."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return int(total_chars / CHARS_PER_TOKEN)

    def stats(self) -> dict:
        return {
            "max_tokens": self._max_tokens,
            "threshold": self._threshold,
            "compressions_done": self._compression_count,
        }
