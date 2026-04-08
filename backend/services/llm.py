"""
LLM Service — ROOT's connection to Claude models.

Supports three tiers:
- fast: Haiku for quick, cheap responses
- default: Sonnet for general reasoning
- thinking: Opus for deep analysis and reflection

New features (v1.1):
- Response streaming with token counts yielded at end
- Per-request token counting returned as metadata
- Model fallback chain: Opus → Sonnet → Haiku on failure
- Built-in request cache (5 min TTL) for identical prompts
- Health check that pings the provider
- Structured output mode (JSON schema enforcement)
- Per-model-tier rate limiting (tokens per minute)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import defaultdict
from typing import Any, AsyncIterator, Optional

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

# Fallback chain within Anthropic: thinking → default → fast
_FALLBACK_CHAIN: dict[str, list[str]] = {
    "thinking": ["thinking", "default", "fast"],
    "default":  ["default", "fast"],
    "fast":     ["fast"],
}

# ── Per-tier rate limiting (requests per minute) ──────────────────
# Thinking (Opus) is the most expensive, so it gets the tightest cap.
_TIER_RPM_LIMITS: dict[str, int] = {
    "thinking": 5,
    "default":  60,
    "fast":     120,
}


class _TierRateLimiter:
    """Token-bucket rate limiter per model tier (requests per minute)."""

    def __init__(self, limits: dict[str, int]) -> None:
        # Timestamps of recent requests per tier
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._limits = limits
        self._lock = asyncio.Lock()

    async def acquire(self, tier: str) -> None:
        """Wait until the tier is within its RPM limit."""
        rpm = self._limits.get(tier, 60)
        window_seconds = 60.0

        async with self._lock:
            now = time.monotonic()
            window = self._windows[tier]
            # Drop timestamps older than 1 minute
            cutoff = now - window_seconds
            self._windows[tier] = [t for t in window if t > cutoff]

            if len(self._windows[tier]) >= rpm:
                # Wait until the oldest request exits the window
                oldest = self._windows[tier][0]
                wait_time = window_seconds - (now - oldest)
                if wait_time > 0:
                    logger.debug(
                        "Rate limit hit for tier=%s (%d/%d rpm). Waiting %.1fs.",
                        tier, len(self._windows[tier]), rpm, wait_time,
                    )
                    await asyncio.sleep(wait_time)
                # Re-prune after sleep
                now = time.monotonic()
                self._windows[tier] = [
                    t for t in self._windows[tier]
                    if t > now - window_seconds
                ]

            self._windows[tier].append(time.monotonic())

    def stats(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            tier: {
                "rpm_limit": self._limits.get(tier, 60),
                "current_usage": sum(1 for t in self._windows[tier] if t > now - 60),
            }
            for tier in self._limits
        }


# ── Simple prompt response cache (5 min TTL) ─────────────────────

class _PromptCache:
    """Thread-safe async LRU cache for prompt→response pairs."""

    def __init__(self, ttl: int = 300, max_size: int = 512) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._store: dict[str, tuple[str, float]] = {}  # key → (value, expires_at)
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(system: str, messages: list[dict], model_tier: str) -> str:
        payload = json.dumps({"s": system, "m": messages, "t": model_tier}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    async def get(self, system: str, messages: list[dict], model_tier: str) -> Optional[str]:
        key = self._make_key(system, messages, model_tier)
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    async def set(self, system: str, messages: list[dict], model_tier: str, value: str) -> None:
        if not value:
            return
        key = self._make_key(system, messages, model_tier)
        expires_at = time.monotonic() + self._ttl
        async with self._lock:
            self._store[key] = (value, expires_at)
            # Evict oldest entries if over size
            if len(self._store) > self._max_size:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1), 4),
            "size": len(self._store),
            "ttl_seconds": self._ttl,
        }


# Shared instances — created once, reused across LLMService instances
_rate_limiter = _TierRateLimiter(_TIER_RPM_LIMITS)
_prompt_cache = _PromptCache(ttl=300, max_size=512)


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
        # Expose shared cache/limiter for stats and testing
        self.prompt_cache = _prompt_cache
        self.rate_limiter = _rate_limiter

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

    def _track_usage(self, response, model: str, model_tier: str, method: str = "complete") -> dict[str, Any]:
        """Record token usage from an Anthropic response.

        Returns a dict with input_tokens, output_tokens, and cost_usd.
        """
        token_info: dict[str, Any] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "model": model,
            "tier": model_tier,
        }
        if not hasattr(response, "usage"):
            return token_info

        try:
            usage = response.usage
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
            token_info["input_tokens"] = usage.input_tokens
            token_info["output_tokens"] = usage.output_tokens
            token_info["cache_read_tokens"] = cache_read
            token_info["cache_creation_tokens"] = cache_creation
            if cache_read > 0:
                logger.debug(
                    "Anthropic prompt cache: %d tokens read from cache, %d created (model=%s)",
                    cache_read, cache_creation, model,
                )
            if self._cost_tracker:
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

        return token_info

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
            tier fails (Opus → Sonnet → Haiku).
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
            cached = await _prompt_cache.get(system, messages, model_tier)
            if cached is not None:
                logger.debug("Prompt cache hit (tier=%s)", model_tier)
                return cached

        # Apply per-tier rate limiting
        await _rate_limiter.acquire(model_tier)

        # Determine fallback chain
        tiers_to_try = _FALLBACK_CHAIN.get(model_tier, [model_tier]) if fallback else [model_tier]

        result = ""
        for attempt_tier in tiers_to_try:
            model = MODEL_TIERS.get(attempt_tier, DEFAULT_MODEL)
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
                "temperature": temperature,
            }
            if system:
                cached_system = self._build_system_with_cache(system)
                kwargs["system"] = cached_system if cached_system else system
            if tools:
                kwargs["tools"] = tools

            if attempt_tier != model_tier:
                logger.info("Falling back to tier=%s (model=%s)", attempt_tier, model)

            for attempt in range(MAX_RETRIES):
                try:
                    response = await self._client.messages.create(**kwargs)
                    self._track_usage(response, model, attempt_tier)
                    # Extract text from response blocks
                    parts = []
                    for block in response.content:
                        if hasattr(block, "text"):
                            parts.append(block.text)
                    result = "\n".join(parts)

                    # Cache response in built-in cache
                    if use_cache and not tools and result:
                        await _prompt_cache.set(system, messages, model_tier, result)

                    # Cache the response in economic router
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
                        logger.warning(
                            "LLM API error after %d retries on tier=%s: %s — trying fallback",
                            MAX_RETRIES, attempt_tier, e,
                        )
                        break  # Try next tier in fallback chain
                except anthropic.RateLimitError as e:
                    logger.warning("Rate limited on tier=%s: %s — trying fallback", attempt_tier, e)
                    break  # Try next tier
                except anthropic.APIError as e:
                    logger.error("LLM API error (non-retryable): %s", e)
                    return ""

        if not result:
            raise LLMUnavailableError(f"All tiers exhausted for model_tier={model_tier}")
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
            input_tokens, output_tokens, cost_usd, model, tier
        """
        # Apply per-tier rate limiting
        await _rate_limiter.acquire(model_tier)

        tiers_to_try = _FALLBACK_CHAIN.get(model_tier, [model_tier])
        for attempt_tier in tiers_to_try:
            model = MODEL_TIERS.get(attempt_tier, DEFAULT_MODEL)
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
                "temperature": temperature,
            }
            if system:
                cached_system = self._build_system_with_cache(system)
                kwargs["system"] = cached_system if cached_system else system
            if tools:
                kwargs["tools"] = tools

            for attempt in range(MAX_RETRIES):
                try:
                    response = await self._client.messages.create(**kwargs)
                    token_info = self._track_usage(response, model, attempt_tier)
                    parts = [block.text for block in response.content if hasattr(block, "text")]
                    text = "\n".join(parts)
                    return text, token_info
                except (anthropic.APIConnectionError, anthropic.InternalServerError) as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        logger.warning("Tier=%s failed, trying fallback: %s", attempt_tier, e)
                        break
                except anthropic.APIError as e:
                    logger.error("LLM API error: %s", e)
                    return "", {"error": str(e)}

        raise LLMUnavailableError(f"All tiers exhausted for model_tier={model_tier}")

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

        Enforces JSON output by:
        1. Appending a JSON instruction to the system prompt.
        2. Attempting to parse the response as JSON.
        3. Retrying up to 2 times on parse failure with corrective instruction.

        Parameters
        ----------
        json_schema:
            Optional JSON Schema dict. When provided, a description of the
            schema is added to the system prompt.  Full runtime validation
            is not performed — the LLM is instructed to match the schema.
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

        last_error: Optional[str] = None
        working_messages = list(messages)

        for retry in range(3):
            if retry > 0 and last_error:
                # Provide corrective guidance
                working_messages = list(messages) + [
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response was not valid JSON: {last_error}. "
                            "Please respond with ONLY a valid JSON object."
                        ),
                    }
                ]

            try:
                raw = await self.complete(
                    messages=working_messages,
                    system=json_system,
                    model_tier=model_tier,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    use_cache=False,  # JSON responses shouldn't be cached due to schema specificity
                )
                # Strip markdown fences if present
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
                parsed = json.loads(text)
                return parsed
            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning("JSON parse failed (retry %d/3): %s", retry + 1, e)

        logger.error("complete_json failed after 3 retries. Last error: %s", last_error)
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
        model = MODEL_TIERS.get(model_tier, DEFAULT_MODEL)
        # Use cache_control blocks for prompt caching on system prompt
        system_param = self._build_system_with_cache(system) if system else system

        # Apply per-tier rate limiting
        await _rate_limiter.acquire(model_tier)

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
        emit_usage: bool = False,
    ) -> AsyncIterator[str]:
        """Stream completion tokens. Yields text chunks.

        Parameters
        ----------
        emit_usage:
            When True, yields a final sentinel JSON chunk with token counts:
            ``__usage__:{"input_tokens": N, "output_tokens": N, "model": "..."}``
        """
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

        # Apply per-tier rate limiting
        await _rate_limiter.acquire(model_tier)

        try:
            async with self._client.messages.stream(**kwargs) as stream_ctx:
                async for text in stream_ctx.text_stream:
                    yield text
                if emit_usage:
                    try:
                        final_msg = await stream_ctx.get_final_message()
                        usage = final_msg.usage
                        usage_info = {
                            "input_tokens": usage.input_tokens,
                            "output_tokens": usage.output_tokens,
                            "model": model,
                            "tier": model_tier,
                        }
                        self._track_usage(final_msg, model, model_tier, method="stream")
                        yield f"__usage__:{json.dumps(usage_info)}"
                    except Exception as exc:
                        logger.debug("Could not emit stream usage: %s", exc)
        except anthropic.APIError as e:
            logger.error("LLM stream error: %s", e)
            yield f"[Error: {e}]"

    async def health_check(self) -> dict[str, Any]:
        """Ping the Anthropic API with a minimal request.

        Returns a dict with:
            ok (bool), latency_ms (float), model (str), error (str or None)
        """
        start = time.monotonic()
        try:
            response = await self._client.messages.create(
                model=FAST_MODEL,  # Use cheapest model for health checks
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
            latency_ms = (time.monotonic() - start) * 1000
            ok = len(response.content) > 0
            return {
                "ok": ok,
                "latency_ms": round(latency_ms, 1),
                "model": FAST_MODEL,
                "provider": "anthropic",
                "error": None,
            }
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            logger.warning("Anthropic health check failed: %s", e)
            return {
                "ok": False,
                "latency_ms": round(latency_ms, 1),
                "model": FAST_MODEL,
                "provider": "anthropic",
                "error": str(e),
            }

    def rate_limit_stats(self) -> dict[str, Any]:
        """Return current rate limiter statistics per tier."""
        return _rate_limiter.stats()

    def cache_stats(self) -> dict[str, Any]:
        """Return prompt cache statistics."""
        return _prompt_cache.stats()
