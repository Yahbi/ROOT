"""
Multi-model parallel evaluation engine.

Inspired by G0DM0D3's ULTRAPLINIAN. Races multiple LLM providers/models
on the same prompt and picks the best response based on quality scoring.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RaceCandidate:
    provider: str
    response: str
    score: float
    elapsed_ms: int
    error: str = ""


@dataclass(frozen=True)
class RaceResult:
    winner: RaceCandidate
    candidates: tuple[RaceCandidate, ...]
    total_elapsed_ms: int
    providers_tried: int


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------
_ACTIONABLE_VERBS = re.compile(
    r"\b(buy|sell|implement|create|deploy|execute|build|launch|ship|trade|"
    r"invest|allocate|rebalance|hedge|short|long|acquire|divest)\b",
    re.IGNORECASE,
)

_HEDGING_PHRASES = re.compile(
    r"\b(I think|I believe|perhaps|maybe|might|could potentially|"
    r"it's possible that|in my opinion|it seems|it appears|"
    r"I'm not sure|arguably|to some extent)\b",
    re.IGNORECASE,
)


class ModelRacing:
    """Race multiple LLM providers in parallel and return the best response."""

    def __init__(self, llm_router: Any = None) -> None:
        self._llm_router = llm_router
        self._total_races = 0
        self._provider_wins: dict[str, int] = {}
        self._avg_scores: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def race(
        self,
        system: str,
        messages: list[dict],
        providers: list[str] | None = None,
        timeout: float = 30.0,
    ) -> RaceResult:
        """Fire all providers in parallel and pick the best response."""
        if providers is None:
            providers = self._available_providers()

        if not providers:
            raise ValueError("No providers available for racing")

        race_start = time.perf_counter()

        tasks = [
            self._call_provider(provider, system, messages)
            for provider in providers
        ]

        raw_results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout,
        )

        candidates: list[RaceCandidate] = []
        for provider, result in zip(providers, raw_results):
            if isinstance(result, BaseException):
                candidates.append(
                    RaceCandidate(
                        provider=provider,
                        response="",
                        score=0.0,
                        elapsed_ms=0,
                        error=str(result),
                    )
                )
            else:
                response_text, elapsed_ms = result
                score = self.score_response(response_text, elapsed_ms)
                candidates.append(
                    RaceCandidate(
                        provider=provider,
                        response=response_text,
                        score=score,
                        elapsed_ms=elapsed_ms,
                    )
                )

        # Rank by score descending
        ranked = tuple(sorted(candidates, key=lambda c: c.score, reverse=True))
        winner = ranked[0]

        total_elapsed_ms = int((time.perf_counter() - race_start) * 1000)

        # Update stats
        self._total_races += 1
        self._provider_wins[winner.provider] = (
            self._provider_wins.get(winner.provider, 0) + 1
        )
        for c in ranked:
            self._avg_scores.setdefault(c.provider, []).append(c.score)

        return RaceResult(
            winner=winner,
            candidates=ranked,
            total_elapsed_ms=total_elapsed_ms,
            providers_tried=len(providers),
        )

    def score_response(self, response: str, elapsed_ms: int) -> float:
        """Score a response on length, actionability, directness, and speed.

        Weights: length=0.3, actionable=0.3, directness=0.2, speed=0.2
        """
        # Length score: longer responses up to 500 chars get full credit
        length_score = min(len(response) / 500, 1.0) * 0.3

        # Actionable content: presence of action verbs
        action_matches = _ACTIONABLE_VERBS.findall(response)
        actionable_score = min(len(action_matches) / 3, 1.0) * 0.3

        # Directness: penalize hedging language
        hedge_matches = _HEDGING_PHRASES.findall(response)
        hedge_penalty = min(len(hedge_matches) / 5, 1.0)
        directness_score = (1.0 - hedge_penalty) * 0.2

        # Speed: faster is better, 10s = zero credit
        speed_score = max(1.0 - elapsed_ms / 10000, 0) * 0.2

        return length_score + actionable_score + directness_score + speed_score

    def stats(self) -> dict:
        """Return racing statistics."""
        avg_by_provider = {}
        for provider, scores in self._avg_scores.items():
            avg_by_provider[provider] = (
                sum(scores) / len(scores) if scores else 0.0
            )

        return {
            "total_races": self._total_races,
            "provider_wins": dict(self._provider_wins),
            "avg_scores_by_provider": avg_by_provider,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _available_providers(self) -> list[str]:
        """Get available providers from the LLM router."""
        if self._llm_router is None:
            return []
        if hasattr(self._llm_router, "available_providers"):
            return self._llm_router.available_providers()
        if hasattr(self._llm_router, "providers"):
            return list(self._llm_router.providers.keys())
        return []

    async def _call_provider(
        self, provider: str, system: str, messages: list[dict]
    ) -> tuple[str, int]:
        """Call a single provider and return (response_text, elapsed_ms)."""
        start = time.perf_counter()

        if self._llm_router is None:
            raise RuntimeError("No LLM router configured")

        if hasattr(self._llm_router, "chat"):
            response = await self._llm_router.chat(
                system=system, messages=messages, provider=provider
            )
        elif hasattr(self._llm_router, "generate"):
            response = await self._llm_router.generate(
                system=system, messages=messages, provider=provider
            )
        else:
            raise RuntimeError(
                f"LLM router has no chat() or generate() method"
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Normalize response to string
        if isinstance(response, str):
            text = response
        elif hasattr(response, "content"):
            text = response.content
        elif hasattr(response, "text"):
            text = response.text
        elif isinstance(response, dict):
            text = response.get("content", response.get("text", str(response)))
        else:
            text = str(response)

        return text, elapsed_ms
