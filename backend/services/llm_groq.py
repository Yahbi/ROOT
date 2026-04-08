"""
Groq LLM Service — ROOT's connection to Groq's free inference API.

Uses the OpenAI-compatible API (same client, custom base_url).
Same interface: complete(), complete_with_tools(), stream().

Free tier: 30 RPM, 14400 requests/day.
Models hosted: Llama, Mixtral, Gemma, and other open-source models.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

from backend.services.llm import LLMUnavailableError, MAX_RETRIES, RETRY_BASE_DELAY

from backend.config import (
    GROQ_API_KEY,
    GROQ_DEFAULT_MODEL,
    GROQ_FAST_MODEL,
    GROQ_THINKING_MODEL,
)

logger = logging.getLogger("root.llm.groq")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

MODEL_TIERS = {
    "fast": GROQ_FAST_MODEL,
    "default": GROQ_DEFAULT_MODEL,
    "thinking": GROQ_THINKING_MODEL,
}


class GroqLLMService:
    """Async wrapper around the Groq API (OpenAI-compatible)."""

    def __init__(self, api_key: Optional[str] = None, cost_tracker=None, economic_router=None) -> None:
        key = api_key or GROQ_API_KEY
        if not key:
            raise ValueError("GROQ_API_KEY is required")
        self._client = AsyncOpenAI(api_key=key, base_url=GROQ_BASE_URL)
        self._cost_tracker = cost_tracker
        self._economic_router = economic_router
        self.provider = "groq"

    def _track_usage(self, response, model: str, model_tier: str, method: str = "complete") -> None:
        """Record token usage from a Groq response."""
        if not self._cost_tracker or not hasattr(response, "usage") or not response.usage:
            return
        try:
            self._cost_tracker.record(
                provider="groq",
                model=model,
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
                model_tier=model_tier,
                method=method,
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

        model = MODEL_TIERS.get(model_tier, GROQ_DEFAULT_MODEL)

        groq_messages: list[dict[str, str]] = []
        if system:
            groq_messages.append({"role": "system", "content": system})
        groq_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": groq_messages,
            "temperature": temperature,
        }

        # Convert tools to OpenAI format if provided
        if tools:
            kwargs["tools"] = _convert_tools_to_openai(tools)

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(**kwargs)
                self._track_usage(response, model, model_tier)
                content = response.choices[0].message.content or ""

                # Cache the response for future identical calls
                if decision and decision.get("cacheable") and content:
                    self._economic_router.record_response(
                        system=system, messages=messages, tier=model_tier,
                        response=content, cache_ttl=decision.get("cache_ttl", 300),
                    )

                return content
            except (ConnectionError, TimeoutError, OSError) as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("Groq transient error (attempt %d/%d), retrying in %.1fs: %s",
                                   attempt + 1, MAX_RETRIES, delay, e)
                    await asyncio.sleep(delay)
                else:
                    logger.error("Groq API error after %d retries: %s", MAX_RETRIES, e)
                    raise LLMUnavailableError(str(e)) from e
            except Exception as e:
                if "server_error" in str(e).lower() or "502" in str(e) or "503" in str(e):
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning("Groq server error (attempt %d/%d), retrying: %s",
                                       attempt + 1, MAX_RETRIES, e)
                        await asyncio.sleep(delay)
                        continue
                logger.error("Groq API error: %s", e)
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
        model = MODEL_TIERS.get(model_tier, GROQ_DEFAULT_MODEL)

        groq_messages: list[dict[str, str]] = []
        if system:
            groq_messages.append({"role": "system", "content": system})
        groq_messages.extend(messages)

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=groq_messages,
                    tools=_convert_tools_to_openai(tools),
                )
                self._track_usage(response, model, model_tier, method="complete_with_tools")

                choice = response.choices[0].message
                text = choice.content or ""
                tool_calls = []

                if choice.tool_calls:
                    for tc in choice.tool_calls:
                        tool_calls.append({
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": json.loads(tc.function.arguments),
                        })

                return text, tool_calls
            except (ConnectionError, TimeoutError, OSError) as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("Groq tool_use transient error (attempt %d/%d), retrying: %s",
                                   attempt + 1, MAX_RETRIES, e)
                    await asyncio.sleep(delay)
                else:
                    raise LLMUnavailableError(str(e)) from e
            except Exception as e:
                logger.error("Groq API error (tool_use): %s", e)
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
        model = MODEL_TIERS.get(model_tier, GROQ_DEFAULT_MODEL)

        groq_messages: list[dict[str, str]] = []
        if system:
            groq_messages.append({"role": "system", "content": system})
        groq_messages.extend(messages)

        try:
            stream = await self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=groq_messages,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error("Groq stream error: %s", e)
            yield f"[Error: {e}]"


def _convert_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic-style tool definitions to OpenAI format."""
    oai_tools = []
    for tool in tools:
        if "function" in tool:
            oai_tools.append(tool)
        else:
            oai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", "unknown"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
    return oai_tools
