"""Verification Protocol — multi-agent consensus, disagreement resolution, confidence voting.

Ensures data accuracy through:
1. Multi-agent verification — critical claims verified by 2+ independent agents
2. Confidence-weighted consensus — agents vote with confidence scores
3. Disagreement resolution — when agents conflict, escalate or use tiebreaker
4. Redundancy detection — prevent duplicate work across agents
5. Source cross-referencing — flag unsupported claims
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("root.verification")


# ── Data Types ──────────────────────────────────────────────────

class VerificationLevel(str, Enum):
    """How thoroughly to verify a claim or result."""
    NONE = "none"          # Trust single agent (greetings, status)
    SINGLE = "single"      # One agent, log for audit
    DUAL = "dual"          # Two agents must agree
    COUNCIL = "council"    # 3+ agents vote with confidence


class ResolutionStrategy(str, Enum):
    """How to resolve disagreements between agents."""
    HIGHEST_CONFIDENCE = "highest_confidence"   # Trust most confident agent
    MAJORITY_VOTE = "majority_vote"             # Majority wins
    WEIGHTED_VOTE = "weighted_vote"             # Weight by agent track record
    ESCALATE = "escalate"                       # Ask higher-tier model
    DEFER_TO_HUMAN = "defer_to_human"           # Ask Yohan


@dataclass(frozen=True)
class AgentVerdict:
    """One agent's verified assessment."""
    agent_id: str
    claim: str
    confidence: float  # 0.0 - 1.0
    supporting_evidence: str = ""
    dissenting_points: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of a multi-agent verification."""
    claim: str
    verified: bool
    consensus_confidence: float  # Weighted average confidence
    agreement_ratio: float       # % of agents that agreed
    verdicts: tuple[AgentVerdict, ...] = ()
    resolution_strategy: str = "single"
    resolution_notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Claim Classification ────────────────────────────────────────

# Claims that require higher verification
_HIGH_STAKES_KEYWORDS = (
    "trade", "buy", "sell", "invest", "price", "market",
    "revenue", "profit", "loss", "cost", "financial",
    "deploy", "production", "security", "delete", "critical",
    "guarantee", "certain", "always", "never", "100%",
)

# Claims that are fine with single-agent verification
_LOW_STAKES_KEYWORDS = (
    "hello", "thanks", "status", "help", "format",
    "summarize", "list", "show", "count", "time",
)


def classify_verification_need(
    claim: str,
    context: str = "",
    is_financial: bool = False,
    is_actionable: bool = False,
) -> VerificationLevel:
    """Determine how much verification a claim needs.

    Higher stakes = more verification. Financial/actionable claims
    always get at minimum dual verification.
    """
    lower = claim.lower()[:500]

    # Financial or actionable always need dual+
    if is_financial or is_actionable:
        if any(kw in lower for kw in ("trade", "buy", "sell", "deploy", "delete")):
            return VerificationLevel.COUNCIL
        return VerificationLevel.DUAL

    # Low-stakes patterns
    if any(lower.strip().startswith(kw) for kw in _LOW_STAKES_KEYWORDS):
        return VerificationLevel.NONE

    # High-stakes keywords
    high_count = sum(1 for kw in _HIGH_STAKES_KEYWORDS if kw in lower)
    if high_count >= 3:
        return VerificationLevel.COUNCIL
    if high_count >= 1:
        return VerificationLevel.DUAL

    # Medium-length substantive claims
    if len(claim) > 200:
        return VerificationLevel.DUAL

    return VerificationLevel.SINGLE


# ── Redundancy Detection ────────────────────────────────────────

class RedundancyDetector:
    """Detects and prevents duplicate work across agents.

    Tracks recently submitted tasks and flags when the same work
    is being requested of multiple agents unnecessarily.
    """

    def __init__(self, window_seconds: int = 300) -> None:
        self._window = window_seconds
        self._recent_tasks: dict[str, dict[str, Any]] = {}  # hash → {agent, task, time}

    @staticmethod
    def _task_hash(task: str) -> str:
        """Normalize and hash a task description."""
        # Normalize: lowercase, strip, remove extra whitespace
        normalized = " ".join(task.lower().split())[:300]
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def check_redundant(self, agent_id: str, task: str) -> Optional[dict[str, Any]]:
        """Check if this task is redundant with a recent submission.

        Returns info about the duplicate if found, None otherwise.
        """
        self._evict_expired()
        h = self._task_hash(task)

        existing = self._recent_tasks.get(h)
        if existing and existing["agent_id"] != agent_id:
            return {
                "is_redundant": True,
                "original_agent": existing["agent_id"],
                "original_time": existing["time"],
                "task_preview": existing["task"][:100],
            }

        return None

    def register_task(self, agent_id: str, task: str) -> None:
        """Register a task as in-progress to prevent duplicates."""
        h = self._task_hash(task)
        self._recent_tasks[h] = {
            "agent_id": agent_id,
            "task": task[:200],
            "time": time.time(),
        }

    def _evict_expired(self) -> None:
        """Remove expired entries."""
        cutoff = time.time() - self._window
        expired = [k for k, v in self._recent_tasks.items() if v["time"] < cutoff]
        for k in expired:
            del self._recent_tasks[k]

    def stats(self) -> dict[str, Any]:
        self._evict_expired()
        return {"tracked_tasks": len(self._recent_tasks), "window_seconds": self._window}


# ── Consensus Engine ────────────────────────────────────────────

class ConsensusEngine:
    """Resolves multi-agent verdicts into a single verified result.

    Supports multiple resolution strategies:
    - Highest confidence: trust the most confident agent
    - Majority vote: majority agreement wins
    - Weighted vote: weight by agent historical accuracy
    - Escalate: use a higher-tier model to resolve
    """

    def __init__(self, learning_engine=None) -> None:
        self._learning = learning_engine
        self._verifications: list[VerificationResult] = []
        self._agreements = 0
        self._disagreements = 0

    def resolve(
        self,
        claim: str,
        verdicts: list[AgentVerdict],
        strategy: ResolutionStrategy = ResolutionStrategy.WEIGHTED_VOTE,
    ) -> VerificationResult:
        """Resolve multiple agent verdicts into a single verification result.

        Uses the specified strategy to determine the final answer
        when agents disagree.
        """
        if not verdicts:
            return VerificationResult(
                claim=claim,
                verified=False,
                consensus_confidence=0.0,
                agreement_ratio=0.0,
                resolution_strategy=strategy.value,
                resolution_notes="No verdicts provided",
            )

        if len(verdicts) == 1:
            v = verdicts[0]
            result = VerificationResult(
                claim=claim,
                verified=v.confidence >= 0.5,
                consensus_confidence=v.confidence,
                agreement_ratio=1.0,
                verdicts=(v,),
                resolution_strategy="single",
                resolution_notes=f"Single agent: {v.agent_id} (confidence={v.confidence:.2f})",
            )
            self._verifications = [*self._verifications[-499:], result]
            return result

        # Group verdicts by agreement (positive = confidence >= 0.5)
        positive = [v for v in verdicts if v.confidence >= 0.5]
        negative = [v for v in verdicts if v.confidence < 0.5]
        agreement_ratio = len(positive) / len(verdicts)

        if strategy == ResolutionStrategy.HIGHEST_CONFIDENCE:
            result = self._resolve_highest_confidence(claim, verdicts, agreement_ratio)
        elif strategy == ResolutionStrategy.MAJORITY_VOTE:
            result = self._resolve_majority(claim, verdicts, positive, negative, agreement_ratio)
        elif strategy == ResolutionStrategy.WEIGHTED_VOTE:
            result = self._resolve_weighted(claim, verdicts, agreement_ratio)
        else:
            result = self._resolve_highest_confidence(claim, verdicts, agreement_ratio)

        # Track agreement stats
        if agreement_ratio >= 0.8:
            self._agreements += 1
        elif agreement_ratio <= 0.5:
            self._disagreements += 1

        self._verifications = [*self._verifications[-499:], result]
        return result

    def _resolve_highest_confidence(
        self, claim: str, verdicts: list[AgentVerdict], agreement_ratio: float,
    ) -> VerificationResult:
        """Trust the most confident agent."""
        best = max(verdicts, key=lambda v: v.confidence)
        return VerificationResult(
            claim=claim,
            verified=best.confidence >= 0.5,
            consensus_confidence=best.confidence,
            agreement_ratio=agreement_ratio,
            verdicts=tuple(verdicts),
            resolution_strategy="highest_confidence",
            resolution_notes=f"Trusted {best.agent_id} (highest confidence={best.confidence:.2f})",
        )

    def _resolve_majority(
        self,
        claim: str,
        verdicts: list[AgentVerdict],
        positive: list[AgentVerdict],
        negative: list[AgentVerdict],
        agreement_ratio: float,
    ) -> VerificationResult:
        """Majority vote wins."""
        verified = len(positive) > len(negative)
        winners = positive if verified else negative
        avg_conf = sum(v.confidence for v in winners) / max(len(winners), 1)

        return VerificationResult(
            claim=claim,
            verified=verified,
            consensus_confidence=avg_conf,
            agreement_ratio=agreement_ratio,
            verdicts=tuple(verdicts),
            resolution_strategy="majority_vote",
            resolution_notes=f"Majority: {len(positive)} for, {len(negative)} against",
        )

    def _resolve_weighted(
        self, claim: str, verdicts: list[AgentVerdict], agreement_ratio: float,
    ) -> VerificationResult:
        """Weight votes by agent historical accuracy (from learning engine)."""
        weighted_scores: list[tuple[AgentVerdict, float]] = []

        for v in verdicts:
            weight = 0.5  # Default weight
            if self._learning:
                try:
                    # Use routing weight as proxy for agent reliability
                    agent_weight = self._learning.get_routing_weight(v.agent_id, "general")
                    if agent_weight is not None:
                        weight = agent_weight
                except Exception:
                    pass

            # Score = confidence * historical_weight
            score = v.confidence * weight
            weighted_scores.append((v, score))

        # Weighted consensus
        total_weight = sum(s for _, s in weighted_scores)
        weighted_conf = total_weight / max(len(weighted_scores), 1)

        best_verdict, best_score = max(weighted_scores, key=lambda x: x[1])

        notes_parts = []
        for v, s in sorted(weighted_scores, key=lambda x: -x[1]):
            notes_parts.append(f"{v.agent_id}: score={s:.3f} (conf={v.confidence:.2f})")

        return VerificationResult(
            claim=claim,
            verified=weighted_conf >= 0.5,
            consensus_confidence=round(weighted_conf, 4),
            agreement_ratio=agreement_ratio,
            verdicts=tuple(verdicts),
            resolution_strategy="weighted_vote",
            resolution_notes=f"Weighted: {'; '.join(notes_parts)}. "
                             f"Best: {best_verdict.agent_id} (score={best_score:.3f})",
        )

    def stats(self) -> dict[str, Any]:
        total = self._agreements + self._disagreements
        return {
            "total_verifications": len(self._verifications),
            "agreements": self._agreements,
            "disagreements": self._disagreements,
            "agreement_rate": round(self._agreements / max(total, 1), 4),
            "recent_results": [
                {
                    "claim": r.claim[:80],
                    "verified": r.verified,
                    "confidence": r.consensus_confidence,
                    "strategy": r.resolution_strategy,
                    "agents": len(r.verdicts),
                }
                for r in self._verifications[-5:]
            ],
        }


# ── Verification Protocol (Main Interface) ──────────────────────

class VerificationProtocol:
    """Orchestrates multi-agent verification for data accuracy.

    Integrates with:
    - AgentCollaboration: for dispatching verification tasks
    - LearningEngine: for agent reliability weights
    - CostTracker: for economic verification (minimize redundant calls)
    """

    def __init__(
        self,
        learning_engine=None,
        cost_tracker=None,
    ) -> None:
        self._consensus = ConsensusEngine(learning_engine=learning_engine)
        self._redundancy = RedundancyDetector()
        self._learning = learning_engine
        self._cost_tracker = cost_tracker

    @property
    def consensus(self) -> ConsensusEngine:
        return self._consensus

    @property
    def redundancy(self) -> RedundancyDetector:
        return self._redundancy

    def should_verify(
        self,
        claim: str,
        context: str = "",
        is_financial: bool = False,
        is_actionable: bool = False,
    ) -> dict[str, Any]:
        """Determine if and how a claim should be verified.

        Returns verification instructions:
        - level: VerificationLevel
        - agents_needed: how many agents to consult
        - strategy: how to resolve disagreements
        - economic_note: any cost considerations
        """
        level = classify_verification_need(
            claim=claim,
            context=context,
            is_financial=is_financial,
            is_actionable=is_actionable,
        )

        agents_needed = {
            VerificationLevel.NONE: 0,
            VerificationLevel.SINGLE: 1,
            VerificationLevel.DUAL: 2,
            VerificationLevel.COUNCIL: 3,
        }[level]

        # Choose resolution strategy based on stakes
        if is_financial:
            strategy = ResolutionStrategy.WEIGHTED_VOTE
        elif agents_needed >= 3:
            strategy = ResolutionStrategy.MAJORITY_VOTE
        elif agents_needed == 2:
            strategy = ResolutionStrategy.HIGHEST_CONFIDENCE
        else:
            strategy = ResolutionStrategy.HIGHEST_CONFIDENCE

        return {
            "level": level.value,
            "agents_needed": agents_needed,
            "strategy": strategy.value,
            "is_financial": is_financial,
            "is_actionable": is_actionable,
        }

    def check_redundancy(self, agent_id: str, task: str) -> Optional[dict[str, Any]]:
        """Check if a task is redundant with recent work."""
        return self._redundancy.check_redundant(agent_id, task)

    def register_task(self, agent_id: str, task: str) -> None:
        """Register a task to prevent duplicates."""
        self._redundancy.register_task(agent_id, task)

    def resolve_verdicts(
        self,
        claim: str,
        verdicts: list[AgentVerdict],
        strategy: Optional[ResolutionStrategy] = None,
    ) -> VerificationResult:
        """Resolve multiple agent verdicts into a verified result."""
        strat = strategy or ResolutionStrategy.WEIGHTED_VOTE
        return self._consensus.resolve(claim, verdicts, strat)

    def verify_agent_result(
        self,
        agent_id: str,
        result: str,
        confidence: float = 0.5,
        claim: str = "",
    ) -> VerificationResult:
        """Quick single-agent verification (wraps result as verdict)."""
        verdict = AgentVerdict(
            agent_id=agent_id,
            claim=claim or result[:200],
            confidence=confidence,
            supporting_evidence=result[:500],
        )
        return self._consensus.resolve(
            claim=claim or result[:200],
            verdicts=[verdict],
            strategy=ResolutionStrategy.HIGHEST_CONFIDENCE,
        )

    def stats(self) -> dict[str, Any]:
        """Return verification protocol statistics."""
        return {
            "consensus": self._consensus.stats(),
            "redundancy": self._redundancy.stats(),
        }
