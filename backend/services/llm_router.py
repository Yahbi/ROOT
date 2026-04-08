"""
Multi-Provider LLM Router — cascading failover across all providers.

When one provider hits rate limits, errors, or is unavailable, automatically
falls through to the next. Priority order is configurable, defaults to:
    Anthropic → OpenAI → DeepSeek → Ollama (local, free)

The router also implements:
- Provider health tracking (circuit breaker per provider)
- Automatic tier mapping across providers
- Cost-aware routing (prefer cheaper providers for low-complexity tasks)
- Background tasks always route to cheapest available provider
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.services.llm import LLMUnavailableError

logger = logging.getLogger("root.llm.router")

# How long to cool down a provider after consecutive failures
CIRCUIT_OPEN_SECONDS = 120  # 2 minutes
MAX_FAILURES_BEFORE_OPEN = 3

# Task types that should prefer cheap/free providers
BACKGROUND_METHODS = frozenset({
    "routing", "classification", "extraction", "scoring",
    "proactive", "reflection", "consolidation", "health_check",
    "builder", "goal_assessment", "digest", "network_propagation",
})


@dataclass(frozen=True)
class ProviderCost:
    """Cost per million tokens for a provider's tiers."""
    fast_input: float = 0.0
    fast_output: float = 0.0
    default_input: float = 0.0
    default_output: float = 0.0
    thinking_input: float = 0.0
    thinking_output: float = 0.0


# Approximate costs per 1M tokens (March 2026)
PROVIDER_COSTS = {
    "ollama": ProviderCost(),  # Free
    "deepseek": ProviderCost(
        fast_input=0.14, fast_output=0.28,
        default_input=0.14, default_output=0.28,
        thinking_input=0.55, thinking_output=2.19,
    ),
    "openai": ProviderCost(
        fast_input=0.15, fast_output=0.60,
        default_input=2.50, default_output=10.00,
        thinking_input=2.50, thinking_output=10.00,
    ),
    "anthropic": ProviderCost(
        fast_input=0.80, fast_output=4.00,
        default_input=3.00, default_output=15.00,
        thinking_input=15.00, thinking_output=75.00,
    ),
}


class ProviderHealth:
    """Circuit breaker for a single LLM provider.

    Uses exponential backoff: each consecutive failure doubles the cooldown,
    capped at 1 hour. Quota errors (insufficient_quota) disable the provider
    for 24 hours since they won't resolve quickly.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._failures = 0
        self._last_failure: float = 0
        self._circuit_open = False
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._last_success: float = 0
        self._rate_limited_until: float = 0
        self._disabled_until: float = 0  # Hard disable (quota exhausted)
        self._backoff_seconds: float = CIRCUIT_OPEN_SECONDS  # Grows exponentially

    @property
    def is_available(self) -> bool:
        """Check if provider is available (circuit closed or cooldown elapsed)."""
        now = time.time()
        if self._disabled_until > now:
            return False
        if self._rate_limited_until > now:
            return False
        if not self._circuit_open:
            return True
        # Check if exponential backoff cooldown has elapsed (half-open)
        if now - self._last_failure > self._backoff_seconds:
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._circuit_open = False
        self._backoff_seconds = CIRCUIT_OPEN_SECONDS  # Reset backoff on success
        self._total_calls += 1
        self._total_successes += 1
        self._last_success = time.time()

    def record_failure(self, is_rate_limit: bool = False, is_quota: bool = False) -> None:
        self._failures += 1
        self._total_calls += 1
        self._total_failures += 1
        self._last_failure = time.time()

        if is_quota:
            # Quota exhausted — disable for 24 hours (won't fix itself soon)
            self._disabled_until = time.time() + 86400
            self._circuit_open = True
            logger.warning(
                "Provider %s DISABLED for 24h (quota exhausted, %d total failures)",
                self.name, self._total_failures,
            )
            return

        if is_rate_limit:
            # Rate limit — back off 60s minimum, or current backoff if higher
            backoff = max(60.0, self._backoff_seconds)
            self._rate_limited_until = time.time() + backoff
            logger.warning("Provider %s rate-limited, backing off %.0fs", self.name, backoff)

        if self._failures >= MAX_FAILURES_BEFORE_OPEN:
            if self._circuit_open:
                # Already open — escalate backoff: 2min → 4min → 8min → ... → 1hr max
                self._backoff_seconds = min(self._backoff_seconds * 2, 3600)
            else:
                # First time opening — use base cooldown
                self._circuit_open = True
                self._backoff_seconds = CIRCUIT_OPEN_SECONDS
            logger.warning(
                "Provider %s circuit OPEN after %d failures (backoff=%.0fs)",
                self.name, self._failures, self._backoff_seconds,
            )

    def stats(self) -> dict[str, Any]:
        now = time.time()
        return {
            "name": self.name,
            "available": self.is_available,
            "circuit_open": self._circuit_open,
            "consecutive_failures": self._failures,
            "total_calls": self._total_calls,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "backoff_seconds": self._backoff_seconds if self._circuit_open else None,
            "disabled_until": self._disabled_until if self._disabled_until > now else None,
            "rate_limited_until": self._rate_limited_until if self._rate_limited_until > now else None,
        }


class MultiProviderLLMRouter:
    """Routes LLM calls across multiple providers with automatic failover.

    Each provider is a service instance (LLMService, OpenAILLMService,
    DeepSeekLLMService, OllamaLLMService) — all share the same interface.
    """

    def __init__(
        self,
        providers: Optional[dict[str, Any]] = None,
        priority: Optional[list[str]] = None,
        background_priority: Optional[list[str]] = None,
    ) -> None:
        self._providers: dict[str, Any] = providers or {}
        self._priority = priority or ["anthropic", "openai", "deepseek", "ollama"]
        # Background tasks prefer cheap/free providers
        self._background_priority = background_priority or ["ollama", "deepseek", "openai", "anthropic"]
        self._health: dict[str, ProviderHealth] = {
            name: ProviderHealth(name) for name in self._providers
        }
        self._total_calls = 0
        self._failovers = 0
        # Chat priority: when user chat is active, background LLM calls wait
        self._chat_active = asyncio.Event()
        self._chat_active.set()  # Not chatting → all calls proceed

    @property
    def provider(self) -> str:
        """Return the name of the first available provider."""
        for name in self._priority:
            if name in self._providers and self._health.get(name, ProviderHealth(name)).is_available:
                return name
        return "offline"

    def add_provider(self, name: str, service: Any) -> None:
        """Register a provider."""
        self._providers[name] = service
        self._health[name] = ProviderHealth(name)
        logger.info("LLM router: registered provider '%s'", name)

    def remove_provider(self, name: str) -> None:
        """Unregister a provider."""
        self._providers.pop(name, None)
        self._health.pop(name, None)

    def chat_started(self) -> None:
        """Signal that user chat is active — background LLM calls should wait."""
        self._chat_active.clear()
        logger.debug("LLM router: chat priority ACTIVE — background calls paused")

    def chat_finished(self) -> None:
        """Signal that user chat is done — background LLM calls can resume."""
        self._chat_active.set()
        logger.debug("LLM router: chat priority RELEASED — background calls resumed")

    def _get_priority(self, method: str = "complete") -> list[str]:
        """Get provider priority order based on task type."""
        if method in BACKGROUND_METHODS:
            return self._background_priority
        return self._priority

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Detect rate limit errors across providers."""
        msg = str(error).lower()
        return any(phrase in msg for phrase in (
            "rate_limit", "rate limit", "429", "too many requests",
            "quota exceeded", "tokens per min", "requests per min",
        ))

    def _is_quota_error(self, error: Exception) -> bool:
        """Detect permanent quota/billing errors (won't resolve with a retry)."""
        msg = str(error).lower()
        return any(phrase in msg for phrase in (
            "insufficient_quota", "billing", "exceeded your current quota",
            "account is not active", "payment required",
        ))

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None,
        method: str = "complete",
        background: bool = False,
    ) -> str:
        """Route completion across providers with failover.

        Parameters
        ----------
        background:
            When ``True``, prefer cheap/free providers regardless of *method*.
            Equivalent to setting *method* to a background method for routing
            purposes.  Also waits for active chat to finish before proceeding.
        """
        is_background = background or method in BACKGROUND_METHODS
        # Background calls wait while user chat is active (Ollama is single-threaded)
        if is_background:
            await self._chat_active.wait()
        self._total_calls += 1
        priority = self._background_priority if is_background else self._get_priority(method)
        if is_background and method not in BACKGROUND_METHODS:
            logger.debug(
                "Background routing: using cheap provider order for method=%s (tier=%s)",
                method, model_tier,
            )
        last_error = None

        for provider_name in priority:
            service = self._providers.get(provider_name)
            if not service:
                continue
            health = self._health.get(provider_name)
            if health and not health.is_available:
                continue

            try:
                result = await service.complete(
                    messages=messages,
                    system=system,
                    model_tier=model_tier,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                )
                if health:
                    health.record_success()
                return result
            except LLMUnavailableError as e:
                last_error = e
                is_quota = self._is_quota_error(e)
                is_rl = not is_quota and self._is_rate_limit_error(e)
                if health:
                    health.record_failure(is_rate_limit=is_rl, is_quota=is_quota)
                self._failovers += 1
                logger.warning("Provider %s failed%s, trying next: %s",
                               provider_name, " (QUOTA EXHAUSTED)" if is_quota else " (rate-limited)" if is_rl else "", e)
            except Exception as e:
                last_error = e
                is_quota = self._is_quota_error(e)
                is_rl = not is_quota and self._is_rate_limit_error(e)
                if health:
                    health.record_failure(is_rate_limit=is_rl, is_quota=is_quota)
                self._failovers += 1
                logger.warning("Provider %s error%s, trying next: %s",
                               provider_name, " (QUOTA EXHAUSTED)" if is_quota else " (rate-limited)" if is_rl else "", e)

        # All providers failed
        logger.error("All LLM providers failed. Last error: %s", last_error)
        return ""

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        method: str = "complete_with_tools",
        background: bool = False,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Route tool-use completion across providers.

        Parameters
        ----------
        background:
            When ``True``, prefer cheap/free providers regardless of *method*.
        """
        is_background = background or method in BACKGROUND_METHODS
        # Background calls wait while user chat is active
        if is_background:
            await self._chat_active.wait()
        self._total_calls += 1
        priority = self._background_priority if is_background else self._get_priority(method)
        if is_background and method not in BACKGROUND_METHODS:
            logger.debug(
                "Background routing (tools): using cheap provider order for method=%s",
                method,
            )
        last_error = None

        for provider_name in priority:
            service = self._providers.get(provider_name)
            if not service:
                continue
            health = self._health.get(provider_name)
            if health and not health.is_available:
                continue

            try:
                result = await service.complete_with_tools(
                    messages=messages, tools=tools,
                    system=system, model_tier=model_tier,
                    max_tokens=max_tokens,
                )
                if health:
                    health.record_success()
                return result
            except Exception as e:
                last_error = e
                is_quota = self._is_quota_error(e)
                is_rl = not is_quota and self._is_rate_limit_error(e)
                if health:
                    health.record_failure(is_rate_limit=is_rl, is_quota=is_quota)
                self._failovers += 1
                logger.warning("Provider %s tool_use failed%s, trying next: %s",
                               provider_name, " (QUOTA)" if is_quota else "", e)

        logger.error("All providers failed for tool_use. Last error: %s", last_error)
        return "", []

    async def stream(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """Stream from first available provider."""
        priority = self._get_priority("stream")

        for provider_name in priority:
            service = self._providers.get(provider_name)
            if not service:
                continue
            health = self._health.get(provider_name)
            if health and not health.is_available:
                continue

            try:
                async for chunk in service.stream(
                    messages=messages, system=system,
                    model_tier=model_tier, max_tokens=max_tokens,
                    temperature=temperature,
                ):
                    yield chunk
                if health:
                    health.record_success()
                return
            except Exception as e:
                is_quota = self._is_quota_error(e)
                is_rl = not is_quota and self._is_rate_limit_error(e)
                if health:
                    health.record_failure(is_rate_limit=is_rl, is_quota=is_quota)
                logger.warning("Provider %s stream failed%s, trying next: %s",
                               provider_name, " (QUOTA)" if is_quota else "", e)

        yield "[All LLM providers unavailable]"

    def stats(self) -> dict[str, Any]:
        """Return router statistics."""
        return {
            "total_calls": self._total_calls,
            "failovers": self._failovers,
            "failover_rate": round(self._failovers / max(self._total_calls, 1), 4),
            "active_provider": self.provider,
            "providers": {
                name: self._health[name].stats()
                for name in self._priority
                if name in self._health
            },
            "priority": self._priority,
            "background_priority": self._background_priority,
            "registered": list(self._providers.keys()),
        }
