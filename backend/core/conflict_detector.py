"""
Conflict Detector — identifies contradictions in autonomous actions.

When ROOT operates autonomously — generating directives, pursuing goals,
placing trades — actions can contradict each other.  For example, one
directive may say "increase exposure to crypto" while another says
"reduce risk across all positions".

The ConflictDetector catches these by:
1. Computing semantic similarity between actions (via EmbeddingService or
   keyword overlap fallback)
2. Checking for opposing intent indicators (buy/sell, increase/decrease, etc.)
3. Classifying conflict type (direct contradiction, resource competition,
   goal misalignment)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("root.conflict_detector")


# ── Data Models (immutable) ─────────────────────────────────────


@dataclass(frozen=True)
class Conflict:
    """An immutable conflict detected between two actions."""

    action_a: str
    action_b: str
    similarity: float
    conflict_type: str  # "direct_contradiction", "resource_competition", "goal_misalignment"
    description: str


# ── Conflict Detector ───────────────────────────────────────────


class ConflictDetector:
    """Detects contradictions between autonomous actions.

    Uses semantic similarity (via EmbeddingService) combined with
    opposing-keyword heuristics to identify when new actions conflict
    with existing ones.

    Parameters
    ----------
    embedding_service:
        Optional EmbeddingService for computing semantic similarity.
        Falls back to keyword overlap when not available.
    similarity_threshold:
        Minimum cosine similarity to consider two actions as related.
        Only related actions are checked for contradiction.
    """

    # Opposing verb/adjective pairs that signal contradiction
    _OPPOSING_PAIRS: tuple[tuple[str, str], ...] = (
        ("increase", "decrease"),
        ("buy", "sell"),
        ("expand", "reduce"),
        ("start", "stop"),
        ("enable", "disable"),
        ("more", "less"),
        ("aggressive", "conservative"),
        ("long", "short"),
        ("raise", "lower"),
        ("accelerate", "decelerate"),
        ("open", "close"),
        ("add", "remove"),
        ("grow", "shrink"),
        ("bullish", "bearish"),
        ("risk-on", "risk-off"),
        ("allocate", "deallocate"),
        ("upgrade", "downgrade"),
        ("maximize", "minimize"),
    )

    # Flatten for quick lookup: word -> set of its opposites
    _OPPOSITE_MAP: dict[str, set[str]] = {}

    def __init__(
        self,
        embedding_service=None,
        similarity_threshold: float = 0.8,
    ) -> None:
        self._embedding_service = embedding_service
        self._similarity_threshold = similarity_threshold

        # Stats
        self._checks_performed = 0
        self._conflicts_found = 0

        # Build opposite lookup on first init
        if not ConflictDetector._OPPOSITE_MAP:
            for a, b in ConflictDetector._OPPOSING_PAIRS:
                ConflictDetector._OPPOSITE_MAP.setdefault(a, set()).add(b)
                ConflictDetector._OPPOSITE_MAP.setdefault(b, set()).add(a)

    # ── Public API ───────────────────────────────────────────────

    async def detect_conflicts(
        self,
        new_action: str,
        existing_actions: list[str],
    ) -> list[Conflict]:
        """Detect conflicts between a new action and existing actions.

        Parameters
        ----------
        new_action:
            The proposed action to check.
        existing_actions:
            List of currently active actions to compare against.

        Returns
        -------
        List of Conflict objects for each detected contradiction.
        """
        if not existing_actions or not new_action.strip():
            return []

        self._checks_performed += 1
        conflicts: list[Conflict] = []

        # Compute similarity scores
        similarities = await self._compute_similarities(new_action, existing_actions)

        for existing, similarity in zip(existing_actions, similarities):
            # Only check highly similar (related) actions for contradiction
            if similarity < self._similarity_threshold:
                continue

            conflict_type = self._classify_conflict(new_action, existing)
            if conflict_type:
                conflict = Conflict(
                    action_a=new_action,
                    action_b=existing,
                    similarity=round(similarity, 4),
                    conflict_type=conflict_type,
                    description=self._describe_conflict(
                        new_action, existing, conflict_type,
                    ),
                )
                conflicts.append(conflict)
                self._conflicts_found += 1

        if conflicts:
            logger.warning(
                "Detected %d conflict(s) for action: '%s'",
                len(conflicts), _truncate(new_action, 80),
            )

        return conflicts

    def has_contradiction(self, action_a: str, action_b: str) -> bool:
        """Quick synchronous check for direct contradiction between two actions.

        Returns True if the actions reference the same subject AND have
        opposing verbs/adjectives.
        """
        tokens_a = self._tokenize(action_a)
        tokens_b = self._tokenize(action_b)

        if not tokens_a or not tokens_b:
            return False

        # Check for shared subject (nouns/entities overlap)
        subjects_a = self._extract_subjects(tokens_a)
        subjects_b = self._extract_subjects(tokens_b)
        shared_subjects = subjects_a & subjects_b

        if not shared_subjects:
            return False

        # Check for opposing verbs/adjectives
        for token_a in tokens_a:
            opposites = self._OPPOSITE_MAP.get(token_a)
            if opposites and opposites & set(tokens_b):
                return True

        return False

    def stats(self) -> dict:
        """Detector statistics."""
        return {
            "checks_performed": self._checks_performed,
            "conflicts_found": self._conflicts_found,
            "has_embedding_service": self._embedding_service is not None,
            "similarity_threshold": self._similarity_threshold,
            "opposing_pairs": len(self._OPPOSING_PAIRS),
        }

    # ── Similarity Computation ───────────────────────────────────

    async def _compute_similarities(
        self,
        new_action: str,
        existing_actions: list[str],
    ) -> list[float]:
        """Compute similarity between new_action and each existing action.

        Uses EmbeddingService cosine similarity when available, falls back
        to keyword overlap (Jaccard similarity).
        """
        if self._embedding_service:
            try:
                return await self._compute_embedding_similarities(
                    new_action, existing_actions,
                )
            except Exception as exc:
                logger.warning(
                    "Embedding similarity failed, falling back to keywords: %s", exc,
                )

        # Keyword overlap fallback
        return self._compute_keyword_similarities(new_action, existing_actions)

    async def _compute_embedding_similarities(
        self,
        new_action: str,
        existing_actions: list[str],
    ) -> list[float]:
        """Compute cosine similarities using embedding vectors."""
        import numpy as np

        all_texts = [new_action] + existing_actions
        vectors = await self._embedding_service.embed_batch(all_texts)

        new_vec = vectors[0]
        similarities: list[float] = []

        for i in range(1, len(vectors)):
            existing_vec = vectors[i]
            # Cosine similarity (vectors may already be normalized)
            dot = float(np.dot(new_vec, existing_vec))
            norm_a = float(np.linalg.norm(new_vec))
            norm_b = float(np.linalg.norm(existing_vec))
            if norm_a > 0 and norm_b > 0:
                sim = dot / (norm_a * norm_b)
            else:
                sim = 0.0
            similarities.append(max(0.0, min(1.0, sim)))

        return similarities

    def _compute_keyword_similarities(
        self,
        new_action: str,
        existing_actions: list[str],
    ) -> list[float]:
        """Compute Jaccard similarity based on keyword overlap."""
        tokens_new = set(self._tokenize(new_action))
        if not tokens_new:
            return [0.0] * len(existing_actions)

        similarities: list[float] = []
        for existing in existing_actions:
            tokens_existing = set(self._tokenize(existing))
            if not tokens_existing:
                similarities.append(0.0)
                continue
            intersection = tokens_new & tokens_existing
            union = tokens_new | tokens_existing
            sim = len(intersection) / len(union) if union else 0.0
            similarities.append(sim)

        return similarities

    # ── Conflict Classification ──────────────────────────────────

    def _classify_conflict(self, action_a: str, action_b: str) -> Optional[str]:
        """Classify the type of conflict between two related actions.

        Returns None if no conflict is detected.
        """
        tokens_a = self._tokenize(action_a)
        tokens_b = self._tokenize(action_b)

        # Direct contradiction: same subject, opposing verbs
        if self.has_contradiction(action_a, action_b):
            return "direct_contradiction"

        # Resource competition: actions competing for the same resource
        resource_keywords = {
            "budget", "capital", "funds", "allocation", "position",
            "bandwidth", "capacity", "time", "resources", "compute",
            "memory", "storage", "portfolio",
        }
        subjects_a = self._extract_subjects(tokens_a)
        subjects_b = self._extract_subjects(tokens_b)
        shared = subjects_a & subjects_b
        if shared & resource_keywords:
            # Both actions target the same resource
            action_verbs_a = set(tokens_a) & self._all_action_words()
            action_verbs_b = set(tokens_b) & self._all_action_words()
            if action_verbs_a and action_verbs_b:
                return "resource_competition"

        # Goal misalignment: similar topic but different strategic direction
        direction_words_a = self._extract_direction(tokens_a)
        direction_words_b = self._extract_direction(tokens_b)
        if direction_words_a and direction_words_b and direction_words_a != direction_words_b:
            return "goal_misalignment"

        return None

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase tokenization with minimal cleanup."""
        cleaned = re.sub(r"[^a-z0-9\s\-]", " ", text.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return [t for t in cleaned.split() if len(t) >= 2]

    @staticmethod
    def _extract_subjects(tokens: list[str]) -> set[str]:
        """Extract likely subject words (nouns/entities) from tokens.

        Simple heuristic: words longer than 3 chars that aren't common
        verbs, adjectives, or stopwords.
        """
        stopwords = {
            "the", "this", "that", "with", "from", "into", "for", "and",
            "but", "not", "all", "our", "should", "would", "could", "will",
            "have", "been", "being", "more", "less", "very", "also", "just",
            "than", "then", "when", "what", "which", "where", "about",
            "across", "after", "before", "between", "through", "during",
            "each", "every", "some", "any", "other",
        }
        return {t for t in tokens if len(t) > 3 and t not in stopwords}

    @classmethod
    def _all_action_words(cls) -> set[str]:
        """All words from opposing pairs (verbs/adjectives that indicate action)."""
        words: set[str] = set()
        for a, b in cls._OPPOSING_PAIRS:
            words.add(a)
            words.add(b)
        return words

    @staticmethod
    def _extract_direction(tokens: list[str]) -> set[str]:
        """Extract directional intent words from tokens."""
        direction_words = {
            "increase", "decrease", "grow", "shrink", "expand", "reduce",
            "aggressive", "conservative", "bullish", "bearish",
            "risk-on", "risk-off", "maximize", "minimize",
            "accelerate", "decelerate", "upgrade", "downgrade",
        }
        return set(tokens) & direction_words

    @staticmethod
    def _describe_conflict(
        action_a: str,
        action_b: str,
        conflict_type: str,
    ) -> str:
        """Generate a human-readable description of the conflict."""
        type_descriptions = {
            "direct_contradiction": (
                "These actions directly contradict each other — "
                "they target the same subject with opposing intent."
            ),
            "resource_competition": (
                "These actions compete for the same resource — "
                "executing both may cause over-allocation or contention."
            ),
            "goal_misalignment": (
                "These actions push in different strategic directions — "
                "they may undermine each other's goals."
            ),
        }
        base = type_descriptions.get(conflict_type, "Potential conflict detected.")
        return (
            f"{base}\n"
            f"  Action A: {_truncate(action_a, 120)}\n"
            f"  Action B: {_truncate(action_b, 120)}"
        )


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis indicator."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."
