"""Economic Router — smart model tier selection, LLM response caching, and cost budgets.

Ensures ROOT operates economically by:
1. Dynamically selecting the cheapest model tier that meets task requirements
2. Caching identical LLM calls to avoid redundant spend
3. Enforcing daily/weekly cost budgets with graceful degradation
4. Tracking savings from cache hits and tier downgrades
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.economic_router")


# ── Task Complexity Classification ──────────────────────────────

@dataclass(frozen=True)
class TaskProfile:
    """Immutable classification of an LLM task's complexity."""
    complexity: str  # "trivial", "simple", "moderate", "complex", "critical"
    recommended_tier: str  # "fast", "default", "thinking"
    cacheable: bool = True
    cache_ttl_seconds: int = 300  # 5 min default


# Keywords indicating task complexity levels
_TRIVIAL_PATTERNS = (
    "hello", "hi", "hey", "thanks", "thank you", "yes", "no", "ok",
    "good morning", "good night", "how are you", "status", "help",
    "what time", "clear", "list", "count", "show",
)

_SIMPLE_PATTERNS = (
    "summarize", "format", "translate", "convert", "extract",
    "classify", "categorize", "tag", "label", "score",
    "draft", "rewrite", "shorten", "expand",
)

_COMPLEX_PATTERNS = (
    "analyze", "compare", "evaluate", "design", "architect",
    "strategy", "plan", "optimize", "debug", "refactor",
    "research", "investigate", "deep dive", "comprehensive",
)

_CRITICAL_PATTERNS = (
    "trade", "execute", "deploy", "financial", "risk assessment",
    "security audit", "architecture decision", "production",
    "critical", "emergency", "urgent",
)

# Methods that are inherently lightweight
_LIGHTWEIGHT_METHODS = ("routing", "classification", "extraction", "scoring")

# Methods that should never be downgraded
_PROTECTED_METHODS = ("thinking", "reflection", "deep_analysis")


def classify_task(
    prompt: str,
    method: str = "complete",
    requested_tier: str = "default",
    token_estimate: int = 0,
) -> TaskProfile:
    """Classify a task and recommend the most economical tier.

    Returns a TaskProfile with the cheapest tier that meets requirements.
    Never upgrades beyond the requested tier — only downgrades.
    """
    lower = prompt.lower()[:500]  # Only scan first 500 chars

    # Protected methods keep their tier
    if method in _PROTECTED_METHODS or requested_tier == "thinking":
        return TaskProfile(
            complexity="critical",
            recommended_tier=requested_tier,
            cacheable=False,
            cache_ttl_seconds=0,
        )

    # Trivial → always fast
    if any(lower.strip().startswith(p) or lower.strip() == p for p in _TRIVIAL_PATTERNS):
        return TaskProfile(
            complexity="trivial",
            recommended_tier="fast",
            cacheable=True,
            cache_ttl_seconds=600,
        )

    # Lightweight method types → fast
    if method in _LIGHTWEIGHT_METHODS:
        return TaskProfile(
            complexity="simple",
            recommended_tier="fast",
            cacheable=True,
            cache_ttl_seconds=300,
        )

    # Short prompts (< 100 chars) without complex keywords → fast
    if len(prompt) < 100 and not any(p in lower for p in _COMPLEX_PATTERNS + _CRITICAL_PATTERNS):
        return TaskProfile(
            complexity="simple",
            recommended_tier="fast",
            cacheable=True,
            cache_ttl_seconds=300,
        )

    # Critical patterns → keep requested tier, don't cache
    if any(p in lower for p in _CRITICAL_PATTERNS):
        return TaskProfile(
            complexity="critical",
            recommended_tier=requested_tier,
            cacheable=False,
            cache_ttl_seconds=0,
        )

    # Complex patterns → keep default, cache briefly
    if any(p in lower for p in _COMPLEX_PATTERNS):
        return TaskProfile(
            complexity="complex",
            recommended_tier="default" if requested_tier != "thinking" else "thinking",
            cacheable=True,
            cache_ttl_seconds=120,
        )

    # Simple patterns → downgrade to fast if currently default
    if any(p in lower for p in _SIMPLE_PATTERNS):
        tier = "fast" if requested_tier == "default" else requested_tier
        return TaskProfile(
            complexity="simple",
            recommended_tier=tier,
            cacheable=True,
            cache_ttl_seconds=300,
        )

    # Default: moderate complexity
    # If requested tier is "default" and prompt is under 300 chars → try fast
    if requested_tier == "default" and len(prompt) < 300:
        return TaskProfile(
            complexity="moderate",
            recommended_tier="fast",
            cacheable=True,
            cache_ttl_seconds=180,
        )

    return TaskProfile(
        complexity="moderate",
        recommended_tier=requested_tier,
        cacheable=True,
        cache_ttl_seconds=180,
    )


# ── LRU Response Cache ──────────────────────────────────────────

@dataclass(frozen=True)
class CacheEntry:
    """Immutable cached LLM response."""
    response: str
    model_tier: str
    created_at: float
    ttl_seconds: int
    estimated_cost_saved: float = 0.0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class ResponseCache:
    """LRU cache for LLM responses to avoid redundant calls.

    Key = hash(system + messages + tier). Respects TTL per entry.
    Thread-safe via OrderedDict (GIL-protected for simple ops).
    """

    def __init__(self, max_size: int = 500) -> None:
        self._max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._total_saved_usd = 0.0

    @staticmethod
    def _make_key(system: str, messages: list[dict], tier: str) -> str:
        """Create a deterministic cache key from request parameters."""
        # Hash the content for a compact key
        content = f"{system}|{tier}|"
        for msg in messages[-5:]:  # Only last 5 messages (recent context)
            content += f"{msg.get('role', '')}:{msg.get('content', '')[:200]}|"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, system: str, messages: list[dict], tier: str) -> Optional[str]:
        """Look up a cached response. Returns None on miss or expiry."""
        key = self._make_key(system, messages, tier)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        self._total_saved_usd += entry.estimated_cost_saved
        return entry.response

    def put(
        self,
        system: str,
        messages: list[dict],
        tier: str,
        response: str,
        ttl_seconds: int = 300,
        estimated_cost: float = 0.0,
    ) -> None:
        """Store a response in the cache."""
        key = self._make_key(system, messages, tier)

        # Evict oldest if full
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = CacheEntry(
            response=response,
            model_tier=tier,
            created_at=time.time(),
            ttl_seconds=ttl_seconds,
            estimated_cost_saved=estimated_cost,
        )

    def invalidate(self, system: str, messages: list[dict], tier: str) -> None:
        """Remove a specific cache entry."""
        key = self._make_key(system, messages, tier)
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1), 4),
            "total_saved_usd": round(self._total_saved_usd, 4),
        }


# ── Cost Budget ──────────────────────────────────────────────────

@dataclass(frozen=True)
class BudgetConfig:
    """Immutable budget configuration."""
    daily_limit_usd: float = 150.0
    weekly_limit_usd: float = 750.0
    monthly_limit_usd: float = 2000.0
    warning_threshold: float = 0.85  # Warn at 85% of budget
    hard_cap: bool = False  # If True, block calls when over budget


class CostBudget:
    """Enforces spending limits and tracks budget utilization.

    Uses the CostTracker's summary() for actual spend data.
    """

    def __init__(self, config: Optional[BudgetConfig] = None) -> None:
        self._config = config or BudgetConfig()
        self._warnings_sent: set[str] = set()

    @property
    def config(self) -> BudgetConfig:
        return self._config

    def check_budget(self, cost_tracker) -> dict[str, Any]:
        """Check current spend against budget limits.

        Returns budget status with utilization percentages.
        """
        if cost_tracker is None:
            return {"status": "no_tracker", "allowed": True}

        try:
            summary = cost_tracker.summary()
        except Exception:
            return {"status": "error", "allowed": True}

        daily_spend = summary.get("daily", {}).get("cost_usd", 0)
        weekly_spend = summary.get("weekly", {}).get("cost_usd", 0)
        monthly_spend = summary.get("monthly", {}).get("cost_usd", 0)

        daily_util = daily_spend / max(self._config.daily_limit_usd, 0.01)
        weekly_util = weekly_spend / max(self._config.weekly_limit_usd, 0.01)
        monthly_util = monthly_spend / max(self._config.monthly_limit_usd, 0.01)

        max_util = max(daily_util, weekly_util, monthly_util)

        warnings: list[str] = []
        if daily_util >= self._config.warning_threshold:
            warnings.append(f"Daily spend ${daily_spend:.2f} / ${self._config.daily_limit_usd:.2f} ({daily_util:.0%})")
        if weekly_util >= self._config.warning_threshold:
            warnings.append(f"Weekly spend ${weekly_spend:.2f} / ${self._config.weekly_limit_usd:.2f} ({weekly_util:.0%})")
        if monthly_util >= self._config.warning_threshold:
            warnings.append(f"Monthly spend ${monthly_spend:.2f} / ${self._config.monthly_limit_usd:.2f} ({monthly_util:.0%})")

        over_budget = max_util >= 1.0
        allowed = not (self._config.hard_cap and over_budget)

        # Log warnings (deduplicated per period)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for w in warnings:
            key = f"{today}:{w[:20]}"
            if key not in self._warnings_sent:
                self._warnings_sent.add(key)
                logger.warning("Budget warning: %s", w)

        return {
            "status": "over_budget" if over_budget else "warning" if warnings else "ok",
            "allowed": allowed,
            "utilization": round(max_util, 4),
            "daily": {"spend": round(daily_spend, 4), "limit": self._config.daily_limit_usd, "util": round(daily_util, 4)},
            "weekly": {"spend": round(weekly_spend, 4), "limit": self._config.weekly_limit_usd, "util": round(weekly_util, 4)},
            "monthly": {"spend": round(monthly_spend, 4), "limit": self._config.monthly_limit_usd, "util": round(monthly_util, 4)},
            "warnings": warnings,
        }

    def recommend_tier(self, requested_tier: str, cost_tracker) -> str:
        """Recommend a tier based on budget pressure.

        Under budget pressure, automatically downgrades expensive tiers.
        """
        budget = self.check_budget(cost_tracker)
        util = budget.get("utilization", 0)

        if util < 0.5:
            return requested_tier  # Under 50% — use what's requested

        if util < 0.8:
            # 50-80% — downgrade thinking to default
            if requested_tier == "thinking":
                logger.info("Budget pressure (%.0f%%) — downgrading thinking → default", util * 100)
                return "default"
            return requested_tier

        # 80%+ — aggressive downgrades
        if requested_tier == "thinking":
            logger.warning("Budget pressure (%.0f%%) — downgrading thinking → default", util * 100)
            return "default"
        if requested_tier == "default":
            logger.warning("Budget pressure (%.0f%%) — downgrading default → fast", util * 100)
            return "fast"

        return requested_tier


# ── Economic Router (Main Interface) ────────────────────────────

class EconomicRouter:
    """Orchestrates smart model selection, caching, and budget enforcement.

    Sits between the Brain/agents and the LLM service to ensure
    every call is as economical as possible without sacrificing accuracy.
    """

    def __init__(
        self,
        cost_tracker=None,
        budget_config: Optional[BudgetConfig] = None,
        cache_max_size: int = 500,
    ) -> None:
        self._cost_tracker = cost_tracker
        self._cache = ResponseCache(max_size=cache_max_size)
        self._budget = CostBudget(config=budget_config)
        self._total_calls = 0
        self._tier_downgrades = 0
        self._cache_hits = 0
        self._budget_blocks = 0

    @property
    def cache(self) -> ResponseCache:
        return self._cache

    @property
    def budget(self) -> CostBudget:
        return self._budget

    def optimize_call(
        self,
        system: str,
        messages: list[dict],
        requested_tier: str = "default",
        method: str = "complete",
        caller_agent: str = "root",
    ) -> dict[str, Any]:
        """Determine the optimal way to handle an LLM call.

        Returns a decision dict:
        - tier: the model tier to use
        - cached_response: if available (skip the LLM call entirely)
        - allowed: whether the call should proceed (budget check)
        - cache_ttl: how long to cache the response
        - savings_reason: why a cheaper option was chosen
        """
        self._total_calls += 1

        # 1. Build prompt text for classification
        prompt_text = system + " " + " ".join(
            msg.get("content", "")[:200] for msg in messages[-3:]
        )

        # 2. Classify task complexity
        profile = classify_task(
            prompt=prompt_text,
            method=method,
            requested_tier=requested_tier,
        )

        # 3. Apply budget pressure
        budget_tier = self._budget.recommend_tier(profile.recommended_tier, self._cost_tracker)

        # Track downgrades
        final_tier = budget_tier
        savings_reason = None

        if final_tier != requested_tier:
            self._tier_downgrades += 1
            savings_reason = f"Downgraded {requested_tier}→{final_tier} (complexity={profile.complexity})"
            logger.info("Economic routing: %s [agent=%s]", savings_reason, caller_agent)

        # 4. Check cache (only for cacheable tasks)
        cached = None
        if profile.cacheable:
            cached = self._cache.get(system, messages, final_tier)
            if cached is not None:
                self._cache_hits += 1
                savings_reason = f"Cache hit (saved ~{profile.cache_ttl_seconds}s LLM call)"

        # 5. Budget gate
        budget_status = self._budget.check_budget(self._cost_tracker)
        allowed = budget_status.get("allowed", True)
        if not allowed:
            self._budget_blocks += 1

        return {
            "tier": final_tier,
            "original_tier": requested_tier,
            "cached_response": cached,
            "allowed": allowed,
            "cacheable": profile.cacheable,
            "cache_ttl": profile.cache_ttl_seconds,
            "complexity": profile.complexity,
            "savings_reason": savings_reason,
            "budget_status": budget_status.get("status", "ok"),
        }

    def record_response(
        self,
        system: str,
        messages: list[dict],
        tier: str,
        response: str,
        cache_ttl: int = 300,
        estimated_cost: float = 0.0,
    ) -> None:
        """Store a response in the cache after a successful LLM call."""
        if cache_ttl > 0:
            self._cache.put(
                system=system,
                messages=messages,
                tier=tier,
                response=response,
                ttl_seconds=cache_ttl,
                estimated_cost=estimated_cost,
            )

    def stats(self) -> dict[str, Any]:
        """Return economic routing statistics."""
        return {
            "total_calls": self._total_calls,
            "tier_downgrades": self._tier_downgrades,
            "cache_hits": self._cache_hits,
            "budget_blocks": self._budget_blocks,
            "downgrade_rate": round(self._tier_downgrades / max(self._total_calls, 1), 4),
            "cache": self._cache.stats(),
            "budget": self._budget.check_budget(self._cost_tracker),
        }
