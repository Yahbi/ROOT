"""
OpenAI LLM Service — ROOT's connection to GPT models.

Drop-in replacement for the Anthropic LLM service.
Same interface: complete(), complete_with_tools(), stream().

New features (v1.1):
- Response streaming with optional token usage emission
- Per-request token counting returned as metadata
- Model fallback chain: thinking → default → fast on failure
- Built-in request cache (5 min TTL) for identical prompts
- Health check that pings the provider
- Structured output mode (JSON schema enforcement)
- Per-model-tier rate limiting (tokens per minute)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI

from backend.services.llm import (
    LLMUnavailableError,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    _PromptCache,
    _TierRateLimiter,
    _FALLBACK_CHAIN,
)

from backend.config import (
    OPENAI_API_KEY,
    OPENAI_DEFAULT_MODEL,
    OPENAI_FAST_MODEL,
    OPENAI_THINKING_MODEL,
)

logger = logging.getLogger("root.llm.openai")

MODEL_TIERS = {
    "fast": OPENAI_FAST_MODEL,
    "default": OPENAI_DEFAULT_MODEL,
    "thinking": OPENAI_THINKING_MODEL,
}

# Per-tier RPM limits for OpenAI (conservative defaults)
_OPENAI_TIER_RPM_LIMITS: dict[str, int] = {
    "thinking": 10,
    "default":  60,
    "fast":     120,
}

# Module-level shared instances
_oai_rate_limiter = _TierRateLimiter(_OPENAI_TIER_RPM_LIMITS)
_oai_prompt_cache = _PromptCache(ttl=300, max_size=512)


class OpenAILLMService:
    """Async wrapper around the OpenAI API — same interface as LLMService."""

    def __init__(self, api_key: Optional[str] = None, cost_tracker=None, economic_router=None) -> None:
        key = api_key or OPENAI_API_KEY
        if not key:
            raise ValueError("OPENAI_API_KEY is required")
        self._client = AsyncOpenAI(api_key=key)
        self._cost_tracker = cost_tracker
        self._economic_router = economic_router
        self.provider = "openai"
        # Expose shared cache/limiter for stats and testing
        self.prompt_cache = _oai_prompt_cache
        self.rate_limiter = _oai_rate_limiter

    def _track_usage(
        self,
        response,
        model: str,
        model_tier: str,
        method: str = "complete",
    ) -> dict[str, Any]:
        """Record token usage from an OpenAI response.

        Returns a dict with input_tokens, output_tokens, and metadata.
        """
        token_info: dict[str, Any] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "model": model,
            "tier": model_tier,
        }
        if not hasattr(response, "usage") or not response.usage:
            return token_info
        try:
            token_info["input_tokens"] = response.usage.prompt_tokens or 0
            token_info["output_tokens"] = response.usage.completion_tokens or 0
            if self._cost_tracker:
                self._cost_tracker.record(
                    provider="openai",
                    model=model,
                    input_tokens=token_info["input_tokens"],
                    output_tokens=token_info["output_tokens"],
                    model_tier=model_tier,
                    method=method,
                )
        except Exception as exc:
            logger.debug("Cost tracking failed: %s", exc)
        return token_info

    def _build_messages(self, system: str, messages: list[dict]) -> list[dict]:
        """Prepend system message for OpenAI format."""
        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.extend(messages)
        return oai_messages

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None,
        use_cache: bool = True,
        fallback: bool = True,
    ) -> str:
        """Send a completion request and return the text response.

        Parameters
        ----------
        use_cache:
            When True (default), check the 5-minute prompt cache before
            calling the API. Disabled automatically when tools are provided.
        fallback:
            When True (default), try cheaper model tiers if the requested
            tier fails (thinking → default → fast).
        """
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

        # Built-in prompt cache (5 min TTL) — skip for tool calls
        if use_cache and not tools:
            cached = await _oai_prompt_cache.get(system, messages, model_tier)
            if cached is not None:
                logger.debug("Prompt cache hit (tier=%s)", model_tier)
                return cached

        # Apply per-tier rate limiting
        await _oai_rate_limiter.acquire(model_tier)

        # Determine fallback chain
        tiers_to_try = _FALLBACK_CHAIN.get(model_tier, [model_tier]) if fallback else [model_tier]

        result = ""
        for attempt_tier in tiers_to_try:
            model = MODEL_TIERS.get(attempt_tier, OPENAI_DEFAULT_MODEL)

            if attempt_tier != model_tier:
                logger.info("OpenAI: Falling back to tier=%s (model=%s)", attempt_tier, model)

            oai_messages = self._build_messages(system, messages)
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": oai_messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = _convert_tools_to_openai(tools)

            for attempt in range(MAX_RETRIES):
                try:
                    response = await self._client.chat.completions.create(**kwargs)
                    self._track_usage(response, model, attempt_tier)
                    content = response.choices[0].message.content or ""

                    # Cache the response in built-in cache
                    if use_cache and not tools and content:
                        await _oai_prompt_cache.set(system, messages, model_tier, content)

                    # Cache the response in economic router
                    if decision and decision.get("cacheable") and content:
                        self._economic_router.record_response(
                            system=system, messages=messages, tier=model_tier,
                            response=content, cache_ttl=decision.get("cache_ttl", 300),
                        )

                    return content
                except (ConnectionError, TimeoutError, OSError) as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning("OpenAI transient error (attempt %d/%d), retrying in %.1fs: %s",
                                       attempt + 1, MAX_RETRIES, delay, e)
                        await asyncio.sleep(delay)
                    else:
                        logger.warning("OpenAI error after %d retries on tier=%s: %s — trying fallback",
                                       MAX_RETRIES, attempt_tier, e)
                        break
                except Exception as e:
                    err_str = str(e).lower()
                    # Retryable server errors
                    if "server_error" in err_str or "502" in str(e) or "503" in str(e):
                        if attempt < MAX_RETRIES - 1:
                            delay = RETRY_BASE_DELAY * (2 ** attempt)
                            logger.warning("OpenAI server error (attempt %d/%d), retrying: %s",
                                           attempt + 1, MAX_RETRIES, e)
                            await asyncio.sleep(delay)
                            continue
                    # Rate limit / quota errors — try next tier
                    if "429" in str(e) or "quota" in err_str or "rate" in err_str:
                        logger.warning("OpenAI rate-limited on tier=%s, trying fallback: %s", attempt_tier, e)
                        break
                    logger.error("OpenAI API error: %s", e)
                    return ""

        if not result:
            raise LLMUnavailableError(f"All OpenAI tiers exhausted for model_tier={model_tier}")
        return result

    async def complete_with_metadata(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[str, dict[str, Any]]:
        """Like complete(), but also returns token usage metadata.

        Returns
        -------
        (text, metadata) where metadata contains:
            input_tokens, output_tokens, model, tier
        """
        await _oai_rate_limiter.acquire(model_tier)

        tiers_to_try = _FALLBACK_CHAIN.get(model_tier, [model_tier])
        for attempt_tier in tiers_to_try:
            model = MODEL_TIERS.get(attempt_tier, OPENAI_DEFAULT_MODEL)
            oai_messages = self._build_messages(system, messages)
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": oai_messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = _convert_tools_to_openai(tools)

            for attempt in range(MAX_RETRIES):
                try:
                    response = await self._client.chat.completions.create(**kwargs)
                    token_info = self._track_usage(response, model, attempt_tier)
                    content = response.choices[0].message.content or ""
                    return content, token_info
                except (ConnectionError, TimeoutError, OSError) as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        logger.warning("Tier=%s failed, trying fallback: %s", attempt_tier, e)
                        break
                except Exception as e:
                    logger.error("OpenAI API error: %s", e)
                    return "", {"error": str(e)}

        raise LLMUnavailableError(f"All OpenAI tiers exhausted for model_tier={model_tier}")

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        json_schema: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Return a structured JSON response, optionally validated against a schema.

        Uses OpenAI's response_format=json_object for guaranteed JSON output
        where available, with retry fallback.
        """
        schema_desc = ""
        if json_schema:
            schema_desc = f"\n\nYour response MUST conform to this JSON schema:\n{json.dumps(json_schema, indent=2)}"

        json_system = (
            system
            + "\n\nYou must respond with valid JSON only. Do not include markdown fences, "
            "explanations, or any text outside the JSON object."
            + schema_desc
        ).strip()

        model = MODEL_TIERS.get(model_tier, OPENAI_DEFAULT_MODEL)
        oai_messages = self._build_messages(json_system, messages)

        last_error: Optional[str] = None
        working_messages = list(oai_messages)

        for retry in range(3):
            if retry > 0 and last_error:
                working_messages = list(oai_messages) + [
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response was not valid JSON: {last_error}. "
                            "Please respond with ONLY a valid JSON object."
                        ),
                    }
                ]

            await _oai_rate_limiter.acquire(model_tier)
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=working_messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning("OpenAI JSON parse failed (retry %d/3): %s", retry + 1, e)
            except Exception as e:
                err_str = str(e).lower()
                # response_format not supported by this model — fall back to text mode
                if "response_format" in err_str or "json_object" in err_str:
                    logger.info("OpenAI model doesn't support json_object mode, using text fallback")
                    return await self._complete_json_text_fallback(
                        messages, system, model_tier, max_tokens, temperature, json_schema
                    )
                logger.error("OpenAI complete_json error: %s", e)
                return {}

        logger.error("complete_json failed after 3 retries. Last error: %s", last_error)
        return {}

    async def _complete_json_text_fallback(
        self,
        messages: list[dict],
        system: str,
        model_tier: str,
        max_tokens: int,
        temperature: float,
        json_schema: Optional[dict],
    ) -> dict[str, Any]:
        """Fallback JSON completion without response_format parameter."""
        schema_desc = ""
        if json_schema:
            schema_desc = f"\n\nYour response MUST conform to this JSON schema:\n{json.dumps(json_schema, indent=2)}"
        json_system = (
            system + "\n\nRespond with valid JSON only." + schema_desc
        ).strip()

        try:
            raw = await self.complete(
                messages=messages,
                system=json_system,
                model_tier=model_tier,
                max_tokens=max_tokens,
                temperature=temperature,
                use_cache=False,
            )
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
            return json.loads(text)
        except Exception as e:
            logger.error("JSON text fallback failed: %s", e)
            return {}

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Complete with tool use. Returns (text, tool_calls)."""
        model = MODEL_TIERS.get(model_tier, OPENAI_DEFAULT_MODEL)
        oai_messages = self._build_messages(system, messages)

        # Apply per-tier rate limiting
        await _oai_rate_limiter.acquire(model_tier)

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=oai_messages,
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
                    logger.warning("OpenAI tool_use transient error (attempt %d/%d), retrying: %s",
                                   attempt + 1, MAX_RETRIES, e)
                    await asyncio.sleep(delay)
                else:
                    raise LLMUnavailableError(str(e)) from e
            except Exception as e:
                err_str = str(e).lower()
                if "429" in str(e) or "quota" in err_str or "rate" in err_str:
                    logger.error("OpenAI API error (tool_use): %s", e)
                    raise LLMUnavailableError(str(e)) from e
                logger.error("OpenAI API error (tool_use): %s", e)
                return "", []
        return "", []

    async def stream(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        emit_usage: bool = False,
    ) -> AsyncIterator[str]:
        """Stream completion tokens. Yields text chunks.

        Parameters
        ----------
        emit_usage:
            When True, yields a final sentinel JSON chunk with token counts:
            ``__usage__:{"input_tokens": N, "output_tokens": N, "model": "..."}``
        """
        model = MODEL_TIERS.get(model_tier, OPENAI_DEFAULT_MODEL)
        oai_messages = self._build_messages(system, messages)

        # Apply per-tier rate limiting
        await _oai_rate_limiter.acquire(model_tier)

        input_tokens = 0
        output_tokens = 0

        try:
            stream = await self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=oai_messages,
                temperature=temperature,
                stream=True,
                stream_options={"include_usage": True} if emit_usage else {},
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                # Capture usage from final chunk (OpenAI includes it at end)
                if emit_usage and hasattr(chunk, "usage") and chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens or 0
                    output_tokens = chunk.usage.completion_tokens or 0

            if emit_usage:
                usage_info = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model": model,
                    "tier": model_tier,
                }
                if self._cost_tracker and (input_tokens or output_tokens):
                    try:
                        self._cost_tracker.record(
                            provider="openai",
                            model=model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            model_tier=model_tier,
                            method="stream",
                        )
                    except Exception:
                        pass
                yield f"__usage__:{json.dumps(usage_info)}"
        except Exception as e:
            logger.error("OpenAI stream error: %s", e)
            yield f"[Error: {e}]"

    async def health_check(self) -> dict[str, Any]:
        """Ping the OpenAI API with a minimal request.

        Returns a dict with:
            ok (bool), latency_ms (float), model (str), error (str or None)
        """
        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=OPENAI_FAST_MODEL,  # Cheapest model for health checks
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
            latency_ms = (time.monotonic() - start) * 1000
            ok = bool(response.choices and response.choices[0].message.content)
            return {
                "ok": ok,
                "latency_ms": round(latency_ms, 1),
                "model": OPENAI_FAST_MODEL,
                "provider": "openai",
                "error": None,
            }
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            logger.warning("OpenAI health check failed: %s", e)
            return {
                "ok": False,
                "latency_ms": round(latency_ms, 1),
                "model": OPENAI_FAST_MODEL,
                "provider": "openai",
                "error": str(e),
            }

    def rate_limit_stats(self) -> dict[str, Any]:
        """Return current rate limiter statistics per tier."""
        return _oai_rate_limiter.stats()

    def cache_stats(self) -> dict[str, Any]:
        """Return prompt cache statistics."""
        return _oai_prompt_cache.stats()


def _convert_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic-style tool definitions to OpenAI format."""
    oai_tools = []
    for tool in tools:
        if "function" in tool:
            # Already OpenAI format
            oai_tools.append(tool)
        else:
            # Anthropic format: {name, description, input_schema}
            oai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", "unknown"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
    return oai_tools
