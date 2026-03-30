"""
Outcome Evaluator — LLM-based quality assessment for autonomous actions.

Replaces naive heuristics (len(text) > 20) with genuine outcome evaluation.
Uses the fast LLM tier to score whether an autonomous action actually achieved
its stated goal, with a multi-signal heuristic fallback when no LLM is available.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("root.outcome_evaluator")


@dataclass(frozen=True)
class OutcomeScore:
    """Immutable outcome quality assessment."""

    quality: float          # 0.0–1.0 overall quality
    reasoning: str          # Explanation of the score
    success: bool           # quality >= 0.4
    method: str             # "llm" or "heuristic"


# ── Constants ─────────────────────────────────────────────────────

_ACTIONABLE_WORDS = frozenset({
    "recommend", "recommends", "recommended",
    "suggest", "suggests", "suggested",
    "found", "discovered", "created",
    "identified", "implemented", "resolved",
    "generated", "built", "deployed",
    "optimized", "improved", "detected",
})

_ERROR_INDICATORS = frozenset({
    "error", "failed", "exception", "timeout",
    "unavailable", "traceback", "crash", "fatal",
})

_FILLER_PHRASES = (
    "i don't know",
    "unable to",
    "sorry",
    "i cannot",
    "i can't",
    "not sure",
    "no information",
    "no results",
    "could not find",
)

_LLM_EVAL_SYSTEM = (
    "You are an outcome quality evaluator for an autonomous AI system. "
    "Given the INTENT of an action and its RESULT, score the outcome quality "
    "from 0.0 to 1.0. Respond ONLY in this exact format:\n"
    "SCORE: <float>\n"
    "REASONING: <one sentence>\n\n"
    "Scoring guide:\n"
    "- 0.0–0.2: Complete failure, errors, no useful output\n"
    "- 0.2–0.4: Partial result, mostly irrelevant or generic\n"
    "- 0.4–0.6: Acceptable — addresses intent with some useful content\n"
    "- 0.6–0.8: Good — clearly achieves the goal with actionable detail\n"
    "- 0.8–1.0: Excellent — exceeds expectations with novel insights"
)


class OutcomeEvaluator:
    """Evaluates whether an autonomous action achieved its stated goal.

    Prefers LLM-based evaluation (fast tier) for nuanced understanding,
    falls back to a multi-signal heuristic when no LLM is available.
    """

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm

    # ── Public API ────────────────────────────────────────────────

    async def evaluate(
        self,
        intent: str,
        result: str,
        context: str = "",
    ) -> OutcomeScore:
        """Evaluate outcome quality using LLM (fast tier), heuristic fallback.

        Args:
            intent: What the action was trying to accomplish.
            result: The actual output / result text.
            context: Optional additional context about the action.

        Returns:
            OutcomeScore with quality 0.0–1.0, reasoning, and method.
        """
        if self._llm:
            try:
                return await self._evaluate_llm(intent, result, context)
            except Exception as exc:
                logger.warning("LLM evaluation failed, falling back to heuristic: %s", exc)

        return self.evaluate_heuristic(intent, result)

    def evaluate_heuristic(self, intent: str, result: str) -> OutcomeScore:
        """Rule-based fallback evaluation with multiple quality signals.

        Signals:
        - Length-based base score
        - Keyword overlap between intent and result
        - Presence of actionable language
        - Error indicator penalties
        - Generic filler penalties
        """
        if not result or not result.strip():
            return OutcomeScore(
                quality=0.0,
                reasoning="Empty result — no output produced",
                success=False,
                method="heuristic",
            )

        result_stripped = result.strip()
        result_lower = result_stripped.lower()
        intent_lower = intent.lower() if intent else ""

        # ── Base score from length ────────────────────────────────
        length = len(result_stripped)
        if length < 100:
            score = 0.1
        elif length < 500:
            score = 0.3
        else:
            score = 0.5

        reasons: list[str] = [f"length={length} (base {score:.1f})"]

        # ── Keyword overlap between intent and result ─────────────
        intent_words = set(re.findall(r"\b[a-z]{3,}\b", intent_lower))
        result_words = set(re.findall(r"\b[a-z]{3,}\b", result_lower))

        if intent_words:
            overlap = intent_words & result_words
            overlap_ratio = len(overlap) / len(intent_words)
            if overlap_ratio >= 0.3:
                score += 0.2
                reasons.append(f"keyword overlap {overlap_ratio:.0%} (+0.2)")

        # ── Actionable language ───────────────────────────────────
        actionable_found = _ACTIONABLE_WORDS & result_words
        if actionable_found:
            score += 0.1
            reasons.append(f"actionable words: {', '.join(list(actionable_found)[:3])} (+0.1)")

        # ── Error indicators ──────────────────────────────────────
        errors_found = _ERROR_INDICATORS & result_words
        if errors_found:
            score -= 0.3
            reasons.append(f"error indicators: {', '.join(list(errors_found)[:3])} (-0.3)")

        # ── Generic filler ────────────────────────────────────────
        for phrase in _FILLER_PHRASES:
            if phrase in result_lower:
                score -= 0.2
                reasons.append(f"filler phrase '{phrase}' (-0.2)")
                break  # Only penalize once

        # ── Clamp ─────────────────────────────────────────────────
        quality = max(0.0, min(1.0, score))

        return OutcomeScore(
            quality=round(quality, 3),
            reasoning="; ".join(reasons),
            success=quality >= 0.4,
            method="heuristic",
        )

    # ── LLM evaluation ────────────────────────────────────────────

    async def _evaluate_llm(
        self,
        intent: str,
        result: str,
        context: str,
    ) -> OutcomeScore:
        """Use fast-tier LLM to evaluate outcome quality."""
        user_prompt = f"INTENT: {intent[:500]}\n\nRESULT:\n{result[:2000]}"
        if context:
            user_prompt += f"\n\nCONTEXT: {context[:500]}"

        response = await self._llm.complete(
            messages=[{"role": "user", "content": user_prompt}],
            system=_LLM_EVAL_SYSTEM,
            model_tier="fast",
            max_tokens=256,
            temperature=0.1,
        )

        return self._parse_llm_response(response)

    @staticmethod
    def _parse_llm_response(response: str) -> OutcomeScore:
        """Parse structured LLM evaluation response."""
        quality = 0.5
        reasoning = "LLM evaluation"

        # Extract SCORE
        score_match = re.search(r"SCORE:\s*([\d.]+)", response)
        if score_match:
            try:
                quality = float(score_match.group(1))
                quality = max(0.0, min(1.0, quality))
            except ValueError:
                pass

        # Extract REASONING
        reason_match = re.search(r"REASONING:\s*(.+)", response)
        if reason_match:
            reasoning = reason_match.group(1).strip()[:300]

        return OutcomeScore(
            quality=round(quality, 3),
            reasoning=reasoning,
            success=quality >= 0.4,
            method="llm",
        )
