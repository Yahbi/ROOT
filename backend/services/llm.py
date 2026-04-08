"""
LLM Service — ROOT's connection to Claude models.

Supports three tiers:
- fast: Haiku for quick, cheap responses
- default: Sonnet for general reasoning
- thinking: Opus for deep analysis and reflection
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import anthropic
import httpx

from backend.config import ANTHROPIC_API_KEY, DEFAULT_MODEL, FAST_MODEL, THINKING_MODEL

logger = logging.getLogger("root.llm")

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


class LLMUnavailableError(Exception):
    """Raised when the LLM API is unreachable after retries."""

MODEL_TIERS = {
    "fast": FAST_MODEL,
    "default": DEFAULT_MODEL,
    "thinking": THINKING_MODEL,
}


class LLMService:
    """Async wrapper around the Anthropic API."""

    def __init__(self, api_key: Optional[str] = None, cost_tracker=None, economic_router=None) -> None:
        key = api_key or ANTHROPIC_API_KEY
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        self._client = anthropic.AsyncAnthropic(
            api_key=key,
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0),
        )
        self._cost_tracker = cost_tracker
        self._economic_router = economic_router
        self.provider = "anthropic"

    @staticmethod
    def _build_system_with_cache(system: str) -> list[dict]:
        """Build a system parameter with Anthropic prompt caching enabled.

        Wraps the system string in a content block with cache_control set to
        'ephemeral', which tells Anthropic to cache the system prompt across
        requests.  Cached input tokens cost ~90% less.

        Returns a list of content blocks suitable for the ``system`` kwarg.
        """
        if not system:
            return []
        return [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _track_usage(self, response, model: str, model_tier: str, method: str = "complete") -> None:
        """Record token usage from an Anthropic response."""
        if not self._cost_tracker or not hasattr(response, "usage"):
            return
        try:
            usage = response.usage
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
            if cache_read > 0:
                logger.debug(
                    "Anthropic prompt cache: %d tokens read from cache, %d created (model=%s)",
                    cache_read, cache_creation, model,
                )
            self._cost_tracker.record(
                provider="anthropic",
                model=model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                model_tier=model_tier,
                method=method,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
            )
        except Exception as exc:
            logger.debug("Cost tracking failed: %s", exc)

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """Send a completion request and return the text response."""
        # Economic routing: check cache, optimize tier, enforce budget
        decision = None
        if self._economic_router and not tools:
            decision = self._economic_router.optimize_call(
                system=system, messages=messages,
                requested_tier=model_tier, method="complete",
            )
            if decision.get("cached_response") is not None:
                logger.debug("Cache hit — skipping LLM call (saved $)")
                return decision["cached_response"]
            if not decision.get("allowed", True):
                logger.warning("Budget exceeded — blocking LLM call")
                return ""
            model_tier = decision.get("tier", model_tier)

        model = MODEL_TIERS.get(model_tier, DEFAULT_MODEL)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            # Use cache_control blocks for prompt caching (90% savings on cached input)
            cached_system = self._build_system_with_cache(system)
            kwargs["system"] = cached_system if cached_system else system
        if tools:
            kwargs["tools"] = tools

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.messages.create(**kwargs)
                self._track_usage(response, model, model_tier)
                # Extract text from response blocks
                parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        parts.append(block.text)
                result = "\n".join(parts)

                # Cache the response for future identical calls
                if decision and decision.get("cacheable") and result:
                    self._economic_router.record_response(
                        system=system, messages=messages, tier=model_tier,
                        response=result, cache_ttl=decision.get("cache_ttl", 300),
                    )

                return result
            except (anthropic.APIConnectionError, anthropic.InternalServerError) as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("LLM transient error (attempt %d/%d), retrying in %.1fs: %s",
                                   attempt + 1, MAX_RETRIES, delay, e)
                    await asyncio.sleep(delay)
                else:
                    logger.error("LLM API error after %d retries: %s", MAX_RETRIES, e)
                    raise LLMUnavailableError(str(e)) from e
            except anthropic.APIError as e:
                logger.error("LLM API error (non-retryable): %s", e)
                return ""
        return ""

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Complete with tool use. Returns (text, tool_calls)."""
        model = MODEL_TIERS.get(model_tier, DEFAULT_MODEL)
        # Use cache_control blocks for prompt caching on system prompt
        system_param = self._build_system_with_cache(system) if system else system
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_param if system_param else system,
                    messages=messages,
                    tools=tools,
                )
                self._track_usage(response, model, model_tier, method="complete_with_tools")
                text_parts = []
                tool_calls = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif block.type == "tool_use":
                        tool_calls.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                return "\n".join(text_parts), tool_calls
            except (anthropic.APIConnectionError, anthropic.InternalServerError) as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("LLM tool_use transient error (attempt %d/%d), retrying: %s",
                                   attempt + 1, MAX_RETRIES, e)
                    await asyncio.sleep(delay)
                else:
                    logger.error("LLM tool_use error after %d retries: %s", MAX_RETRIES, e)
                    raise LLMUnavailableError(str(e)) from e
            except anthropic.APIError as e:
                logger.error("LLM API error (tool_use, non-retryable): %s", e)
                return "", []
        return "", []

    async def stream(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """Stream completion tokens. Yields text chunks."""
        model = MODEL_TIERS.get(model_tier, DEFAULT_MODEL)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            cached_system = self._build_system_with_cache(system)
            kwargs["system"] = cached_system if cached_system else system

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIError as e:
            logger.error("LLM stream error: %s", e)
            yield f"[Error: {e}]"
