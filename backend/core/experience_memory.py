"""
Experience Memory — layered memory system for the ASTRA-ROOT civilization.

Three memory layers:
- Short-term: Active task context (in-memory, auto-expires)
- Long-term: Persistent knowledge base (SQLite, existing MemoryEngine)
- Experience: Success patterns, failures, strategies, lessons learned (SQLite)

Experience memory is the system's wisdom — it learns from outcomes
and informs future decisions.

Extended capabilities:
- Pattern recognition: detect recurring success/failure patterns
- Relevance-scored search: TF-IDF-style scoring across title/description/tags
- Experience clustering: group experiences by topic/domain similarity
- Wisdom extraction: synthesize experiences into actionable wisdom
- Experience aging: old experiences receive lower effective weight
- Cross-domain learning: apply lessons from one domain to another
- Visualization data: aggregated data ready for frontend charts
"""

from __future__ import annotations

import json
import math
import sqlite3
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from backend.config import DATA_DIR

EXPERIENCE_DB = DATA_DIR / "experience.db"


class ExperienceType(str, Enum):
    SUCCESS = "success"          # What worked
    FAILURE = "failure"          # What didn't work (and why)
    STRATEGY = "strategy"        # Reusable strategy pattern
    LESSON = "lesson"            # Generalized lesson learned


@dataclass(frozen=True)
class Experience:
    """Immutable experience record."""
    id: str
    experience_type: ExperienceType
    domain: str                  # e.g., "trading", "automation", "research"
    title: str
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    outcome: Optional[str] = None
    confidence: float = 1.0      # How reliable this lesson is (0-1)
    times_applied: int = 0       # How often this experience was used
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ShortTermEntry:
    """In-memory short-term context entry."""
    id: str
    content: str
    task_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_seconds: int = 3600      # Auto-expire after 1 hour


@dataclass(frozen=True)
class ScoredExperience:
    """Experience with a relevance score attached (for ranked search results)."""
    experience: Experience
    score: float


@dataclass(frozen=True)
class ExperiencePattern:
    """A recurring pattern detected across multiple experiences."""
    pattern_id: str
    pattern_type: str          # "recurring_success", "recurring_failure", "mixed"
    domain: str
    title: str                 # Synthesized pattern title
    description: str           # What the pattern means
    occurrence_count: int      # How many experiences match
    avg_confidence: float
    example_ids: list[str]     # Representative experience IDs
    keywords: list[str]        # Key terms driving the pattern


@dataclass(frozen=True)
class ExperienceCluster:
    """A cluster of topically related experiences."""
    cluster_id: str
    label: str                 # Human-readable cluster label
    domain: str
    keywords: list[str]
    experience_ids: list[str]
    size: int
    dominant_type: str         # Most common experience_type in cluster
    avg_confidence: float


@dataclass(frozen=True)
class Wisdom:
    """Actionable wisdom synthesized from multiple experiences."""
    wisdom_id: str
    domain: str
    insight: str               # The actionable wisdom statement
    source_types: list[str]    # Which experience types contributed
    supporting_count: int      # Number of experiences that support this
    confidence: float          # Weighted confidence of the wisdom
    keywords: list[str]
    cross_domain_applicable: bool  # Can be applied to other domains
    related_domains: list[str]


class ExperienceMemory:
    """Three-layer memory system: short-term, long-term (via MemoryEngine), experience."""

    MAX_SHORT_TERM = 100

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or EXPERIENCE_DB)
        self._conn: Optional[sqlite3.Connection] = None
        self._short_term: dict[str, ShortTermEntry] = {}

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("ExperienceMemory not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiences (
                id TEXT PRIMARY KEY,
                experience_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                context TEXT DEFAULT '{}',
                outcome TEXT,
                confidence REAL DEFAULT 1.0,
                times_applied INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                tags TEXT DEFAULT '',
                last_accessed TEXT,
                source_domain TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_exp_type ON experiences(experience_type);
            CREATE INDEX IF NOT EXISTS idx_exp_domain ON experiences(domain);
            CREATE INDEX IF NOT EXISTS idx_exp_confidence ON experiences(confidence);
            CREATE INDEX IF NOT EXISTS idx_exp_created ON experiences(created_at);
            CREATE INDEX IF NOT EXISTS idx_exp_source_domain ON experiences(source_domain);
        """)
        # Migrate existing databases that lack the new columns (safe no-op if columns exist)
        for col, col_type, default in [
            ("last_accessed", "TEXT", "NULL"),
            ("source_domain", "TEXT", "NULL"),
        ]:
            try:
                self.conn.execute(f"ALTER TABLE experiences ADD COLUMN {col} {col_type} DEFAULT {default}")
                self.conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

    # ── Short-Term Memory ──────────────────────────────────────

    def store_short_term(self, content: str, task_id: Optional[str] = None,
                         ttl_seconds: int = 3600) -> ShortTermEntry:
        """Store active task context in short-term memory."""
        entry = ShortTermEntry(
            id=f"stm_{uuid.uuid4().hex[:12]}",
            content=content,
            task_id=task_id,
            ttl_seconds=ttl_seconds,
        )
        self._short_term[entry.id] = entry
        self._enforce_short_term_limit()
        return entry

    def get_short_term(self, task_id: Optional[str] = None) -> list[ShortTermEntry]:
        """Get active short-term entries, optionally filtered by task."""
        now = datetime.now(timezone.utc)
        active: list[ShortTermEntry] = []
        expired: list[str] = []

        for entry_id, entry in self._short_term.items():
            created = datetime.fromisoformat(entry.created_at)
            age = (now - created).total_seconds()
            if age > entry.ttl_seconds:
                expired.append(entry_id)
            elif task_id is None or entry.task_id == task_id:
                active.append(entry)

        for eid in expired:
            self._short_term.pop(eid, None)

        return active

    def clear_short_term(self, task_id: Optional[str] = None) -> int:
        """Clear short-term entries. If task_id given, only clear that task's context."""
        if task_id is None:
            count = len(self._short_term)
            self._short_term.clear()
            return count
        to_remove = [k for k, v in self._short_term.items() if v.task_id == task_id]
        for k in to_remove:
            self._short_term.pop(k)
        return len(to_remove)

    def _enforce_short_term_limit(self) -> None:
        if len(self._short_term) <= self.MAX_SHORT_TERM:
            return
        sorted_entries = sorted(self._short_term.values(),
                                key=lambda e: e.created_at)
        excess = len(self._short_term) - self.MAX_SHORT_TERM
        for entry in sorted_entries[:excess]:
            self._short_term.pop(entry.id, None)

    # ── Experience Memory (Long-Lived Wisdom) ──────────────────

    def record_experience(
        self,
        experience_type: str,
        domain: str,
        title: str,
        description: str,
        context: Optional[dict] = None,
        outcome: Optional[str] = None,
        confidence: float = 1.0,
        tags: Optional[list[str]] = None,
        source_domain: Optional[str] = None,
    ) -> Experience:
        """Record a new experience (success, failure, strategy, or lesson).

        Args:
            source_domain: If this experience was cross-domain-transferred from
                another domain, record the originating domain here.
        """
        exp_type = ExperienceType(experience_type)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

        exp_id = f"exp_{uuid.uuid4().hex[:12]}"
        ctx_str = json.dumps(context or {})
        tags_str = ",".join(tags or [])
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO experiences
               (id, experience_type, domain, title, description, context,
                outcome, confidence, times_applied, created_at, tags,
                last_accessed, source_domain)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, NULL, ?)""",
            (exp_id, exp_type.value, domain, title, description,
             ctx_str, outcome, confidence, now, tags_str, source_domain),
        )
        self.conn.commit()

        return Experience(
            id=exp_id, experience_type=exp_type, domain=domain,
            title=title, description=description,
            context=context or {}, outcome=outcome,
            confidence=confidence, created_at=now,
            tags=tags or [],
        )

    def record_success(self, domain: str, title: str, description: str,
                        **kwargs) -> Experience:
        """Convenience: record a success pattern."""
        return self.record_experience("success", domain, title, description, **kwargs)

    def record_failure(self, domain: str, title: str, description: str,
                        **kwargs) -> Experience:
        """Convenience: record a failure with lessons."""
        return self.record_experience("failure", domain, title, description, **kwargs)

    def record_strategy(self, domain: str, title: str, description: str,
                         **kwargs) -> Experience:
        """Convenience: record a reusable strategy."""
        return self.record_experience("strategy", domain, title, description, **kwargs)

    def record_lesson(self, domain: str, title: str, description: str,
                       **kwargs) -> Experience:
        """Convenience: record a generalized lesson."""
        return self.record_experience("lesson", domain, title, description, **kwargs)

    def get_experiences(
        self,
        domain: Optional[str] = None,
        experience_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> list[Experience]:
        """Query experiences with optional filters."""
        sql = "SELECT * FROM experiences WHERE confidence >= ?"
        params: list[Any] = [min_confidence]

        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        if experience_type:
            sql += " AND experience_type = ?"
            params.append(experience_type)

        sql += " ORDER BY confidence DESC, times_applied DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def get_successes(self, domain: Optional[str] = None, limit: int = 10) -> list[Experience]:
        return self.get_experiences(domain=domain, experience_type="success", limit=limit)

    def get_failures(self, domain: Optional[str] = None, limit: int = 10) -> list[Experience]:
        return self.get_experiences(domain=domain, experience_type="failure", limit=limit)

    def get_strategies(self, domain: Optional[str] = None, limit: int = 10) -> list[Experience]:
        return self.get_experiences(domain=domain, experience_type="strategy", limit=limit)

    def get_lessons(self, domain: Optional[str] = None, limit: int = 10) -> list[Experience]:
        return self.get_experiences(domain=domain, experience_type="lesson", limit=limit)

    def apply_experience(self, experience_id: str) -> None:
        """Mark an experience as applied (increment usage counter)."""
        self.conn.execute(
            "UPDATE experiences SET times_applied = times_applied + 1 WHERE id = ?",
            (experience_id,),
        )
        self.conn.commit()

    def strengthen(self, experience_id: str, boost: float = 0.05) -> None:
        """Strengthen an experience's confidence."""
        self.conn.execute(
            "UPDATE experiences SET confidence = MIN(1.0, confidence + ?) WHERE id = ?",
            (boost, experience_id),
        )
        self.conn.commit()

    def weaken(self, experience_id: str, penalty: float = 0.1) -> None:
        """Weaken an experience's confidence."""
        self.conn.execute(
            "UPDATE experiences SET confidence = MAX(0.0, confidence - ?) WHERE id = ?",
            (penalty, experience_id),
        )
        self.conn.commit()

    def search_experiences(self, query: str, limit: int = 10) -> list[Experience]:
        """Keyword search across experiences (legacy, unscored).

        Prefer search_experiences_scored() for relevance-ranked results.
        """
        pattern = f"%{query}%"
        rows = self.conn.execute(
            """SELECT * FROM experiences
               WHERE title LIKE ? OR description LIKE ? OR tags LIKE ?
               ORDER BY confidence DESC LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_experience(r) for r in rows]

    # ── Feature 1: Relevance-Scored Search ────────────────────────

    def search_experiences_scored(
        self,
        query: str,
        limit: int = 10,
        domain: Optional[str] = None,
        age_penalty: bool = True,
    ) -> list[ScoredExperience]:
        """Search experiences with TF-IDF-style relevance scoring.

        Score components:
        - Term frequency: how often query tokens appear in title/description/tags
        - Title boost: matches in title score 2x
        - Confidence weight: multiplied by experience confidence
        - Times-applied boost: frequently used experiences score higher
        - Age penalty (optional): experiences older than 90 days get reduced score
        """
        tokens = [t.lower() for t in query.split() if len(t) > 1]
        if not tokens:
            return []

        sql = "SELECT * FROM experiences WHERE 1=1"
        params: list[Any] = []
        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        sql += " LIMIT 500"

        rows = self.conn.execute(sql, params).fetchall()
        scored: list[ScoredExperience] = []
        now = datetime.now(timezone.utc)

        for row in rows:
            exp = self._row_to_experience(row)
            title_lower = exp.title.lower()
            desc_lower = exp.description.lower()
            tags_lower = " ".join(exp.tags).lower()

            tf = 0.0
            for token in tokens:
                tf += title_lower.count(token) * 2.0   # title boost
                tf += desc_lower.count(token) * 1.0
                tf += tags_lower.count(token) * 1.5    # tags boost

            if tf == 0.0:
                continue

            # IDF approximation: rarer tokens score higher — use log(1 + tf)
            relevance = math.log1p(tf)

            # Confidence weighting
            relevance *= (0.5 + exp.confidence * 0.5)

            # Times-applied boost (log scale, capped)
            relevance *= (1.0 + math.log1p(exp.times_applied) * 0.1)

            # Age penalty: exponential decay — half-life ~180 days
            if age_penalty:
                try:
                    created = datetime.fromisoformat(exp.created_at)
                    age_days = (now - created).total_seconds() / 86400
                    decay = math.exp(-age_days / 180.0)
                    relevance *= (0.5 + decay * 0.5)
                except (ValueError, TypeError):
                    pass

            scored.append(ScoredExperience(experience=exp, score=round(relevance, 4)))

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:limit]

    def stats(self) -> dict[str, Any]:
        """Experience memory statistics."""
        rows = self.conn.execute(
            """SELECT experience_type, COUNT(*) as cnt, AVG(confidence) as avg_conf
               FROM experiences GROUP BY experience_type"""
        ).fetchall()
        total = self.conn.execute("SELECT COUNT(*) as c FROM experiences").fetchone()
        return {
            "total_experiences": total["c"] if total else 0,
            "short_term_entries": len(self._short_term),
            "by_type": {
                r["experience_type"]: {
                    "count": r["cnt"],
                    "avg_confidence": round(r["avg_conf"], 3),
                }
                for r in rows
            },
        }

    # ── Feature 2: Pattern Recognition ────────────────────────────

    def detect_patterns(
        self,
        domain: Optional[str] = None,
        min_occurrences: int = 2,
        window_days: int = 180,
    ) -> list[ExperiencePattern]:
        """Detect recurring success/failure patterns in experiences.

        Patterns are found by clustering keyword co-occurrences within the
        same domain and experience type. A pattern requires at least
        ``min_occurrences`` experiences sharing common keywords.

        Args:
            domain: Restrict pattern search to a specific domain.
            min_occurrences: Minimum number of experiences to form a pattern.
            window_days: Only consider experiences within this many days.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        sql = "SELECT * FROM experiences WHERE created_at >= ?"
        params: list[Any] = [cutoff]
        if domain:
            sql += " AND domain = ?"
            params.append(domain)

        rows = self.conn.execute(sql, params).fetchall()
        experiences = [self._row_to_experience(r) for r in rows]

        # Group by (domain, experience_type) — then find shared keywords
        groups: dict[tuple[str, str], list[Experience]] = defaultdict(list)
        for exp in experiences:
            groups[(exp.domain, exp.experience_type.value)].append(exp)

        patterns: list[ExperiencePattern] = []
        for (grp_domain, exp_type), exps in groups.items():
            if len(exps) < min_occurrences:
                continue

            # Extract keywords from each experience
            keyword_sets: list[Counter] = []
            for exp in exps:
                text = f"{exp.title} {exp.description} {' '.join(exp.tags)}"
                words = [
                    w.lower() for w in text.split()
                    if len(w) >= 4 and w.isalpha()
                ]
                keyword_sets.append(Counter(words))

            # Find keywords that appear in >= min_occurrences experiences
            keyword_doc_freq: Counter = Counter()
            for ks in keyword_sets:
                for kw in ks:
                    keyword_doc_freq[kw] += 1

            recurring_keywords = [
                kw for kw, freq in keyword_doc_freq.most_common(20)
                if freq >= min_occurrences
            ]
            if not recurring_keywords:
                continue

            # Find which experiences share >= 2 of the top keywords
            top_keywords = set(recurring_keywords[:5])
            matched_exps = [
                exp for exp, ks in zip(exps, keyword_sets)
                if len(top_keywords & set(ks.keys())) >= min(2, len(top_keywords))
            ]
            if len(matched_exps) < min_occurrences:
                matched_exps = exps  # fall back to all in group

            # Classify pattern type
            types_in_group = {exp.experience_type.value for exp in matched_exps}
            if types_in_group == {"success"}:
                pattern_type = "recurring_success"
                pattern_title = f"Recurring success: {recurring_keywords[0] if recurring_keywords else exp_type}"
            elif "failure" in types_in_group and "success" not in types_in_group:
                pattern_type = "recurring_failure"
                pattern_title = f"Recurring failure: {recurring_keywords[0] if recurring_keywords else exp_type}"
            else:
                pattern_type = "mixed"
                pattern_title = f"Mixed outcomes: {recurring_keywords[0] if recurring_keywords else exp_type}"

            avg_conf = sum(e.confidence for e in matched_exps) / len(matched_exps)
            pattern_desc = (
                f"{len(matched_exps)} experiences in '{grp_domain}' share keywords: "
                f"{', '.join(recurring_keywords[:5])}. "
                f"Pattern type: {pattern_type}."
            )

            patterns.append(ExperiencePattern(
                pattern_id=f"pat_{uuid.uuid4().hex[:8]}",
                pattern_type=pattern_type,
                domain=grp_domain,
                title=pattern_title,
                description=pattern_desc,
                occurrence_count=len(matched_exps),
                avg_confidence=round(avg_conf, 3),
                example_ids=[e.id for e in matched_exps[:3]],
                keywords=recurring_keywords[:10],
            ))

        patterns.sort(key=lambda p: p.occurrence_count, reverse=True)
        return patterns

    # ── Feature 3: Experience Clustering ──────────────────────────

    def cluster_experiences(
        self,
        domain: Optional[str] = None,
        max_clusters: int = 10,
    ) -> list[ExperienceCluster]:
        """Cluster experiences by topic/domain similarity.

        Uses keyword overlap to group experiences into topic clusters.
        Each cluster has a label derived from its most frequent keywords.
        """
        sql = "SELECT * FROM experiences WHERE 1=1"
        params: list[Any] = []
        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        sql += " ORDER BY confidence DESC LIMIT 500"

        rows = self.conn.execute(sql, params).fetchall()
        experiences = [self._row_to_experience(r) for r in rows]

        if not experiences:
            return []

        # Build keyword fingerprint for each experience
        def get_keywords(exp: Experience) -> list[str]:
            text = f"{exp.title} {exp.description} {' '.join(exp.tags)}"
            return [
                w.lower() for w in text.split()
                if len(w) >= 4 and w.isalpha()
            ]

        exp_keywords = [(exp, set(get_keywords(exp))) for exp in experiences]

        # Simple greedy clustering: start from highest-confidence unassigned experience
        clusters: list[list[Experience]] = []
        assigned: set[str] = set()

        for seed_exp, seed_kw in exp_keywords:
            if seed_exp.id in assigned or not seed_kw:
                continue
            cluster = [seed_exp]
            assigned.add(seed_exp.id)

            for other_exp, other_kw in exp_keywords:
                if other_exp.id in assigned or not other_kw:
                    continue
                # Jaccard similarity
                intersection = len(seed_kw & other_kw)
                union = len(seed_kw | other_kw)
                similarity = intersection / union if union > 0 else 0.0
                if similarity >= 0.15:  # tunable threshold
                    cluster.append(other_exp)
                    assigned.add(other_exp.id)

            if len(cluster) >= 1:
                clusters.append(cluster)
            if len(clusters) >= max_clusters:
                break

        result: list[ExperienceCluster] = []
        for cluster_exps in clusters:
            # Dominant type
            type_counter: Counter = Counter(e.experience_type.value for e in cluster_exps)
            dominant_type = type_counter.most_common(1)[0][0]

            # Top keywords
            all_words: Counter = Counter()
            for exp in cluster_exps:
                for kw in get_keywords(exp):
                    all_words[kw] += 1
            top_keywords = [kw for kw, _ in all_words.most_common(8)]

            # Cluster label — most specific domain + top keywords
            cluster_domain = cluster_exps[0].domain
            label_parts = top_keywords[:3]
            label = f"{cluster_domain}: {', '.join(label_parts)}" if label_parts else cluster_domain

            avg_conf = sum(e.confidence for e in cluster_exps) / len(cluster_exps)

            result.append(ExperienceCluster(
                cluster_id=f"cl_{uuid.uuid4().hex[:8]}",
                label=label,
                domain=cluster_domain,
                keywords=top_keywords,
                experience_ids=[e.id for e in cluster_exps],
                size=len(cluster_exps),
                dominant_type=dominant_type,
                avg_confidence=round(avg_conf, 3),
            ))

        result.sort(key=lambda c: c.size, reverse=True)
        return result

    # ── Feature 4: Wisdom Extraction ──────────────────────────────

    def extract_wisdom(
        self,
        domain: Optional[str] = None,
        min_support: int = 2,
        min_confidence: float = 0.5,
    ) -> list[Wisdom]:
        """Synthesize experiences into actionable wisdom statements.

        Wisdom is extracted by:
        1. Grouping experiences by domain.
        2. Finding keywords common to multiple high-confidence experiences.
        3. Synthesizing a directional insight (do X / avoid Y).
        4. Marking cross-domain applicability when keyword themes recur
           across multiple domains.

        Args:
            min_support: Minimum number of experiences needed to generate wisdom.
            min_confidence: Only include experiences above this confidence.
        """
        sql = "SELECT * FROM experiences WHERE confidence >= ?"
        params: list[Any] = [min_confidence]
        if domain:
            sql += " AND domain = ?"
            params.append(domain)

        rows = self.conn.execute(sql, params).fetchall()
        experiences = [self._row_to_experience(r) for r in rows]

        # Collect keyword fingerprints per experience
        def exp_keywords(exp: Experience) -> list[str]:
            text = f"{exp.title} {exp.description} {' '.join(exp.tags)}"
            return [w.lower() for w in text.split() if len(w) >= 4 and w.isalpha()]

        # Group by domain
        by_domain: dict[str, list[Experience]] = defaultdict(list)
        for exp in experiences:
            by_domain[exp.domain].append(exp)

        # Build cross-domain keyword frequency for cross-domain detection
        cross_kw_counter: Counter = Counter()
        for exps in by_domain.values():
            for exp in exps:
                for kw in set(exp_keywords(exp)):
                    cross_kw_counter[kw] += 1
        cross_domain_kws = {kw for kw, c in cross_kw_counter.items() if c >= min_support * 2}

        wisdoms: list[Wisdom] = []

        for dom, exps in by_domain.items():
            if len(exps) < min_support:
                continue

            successes = [e for e in exps if e.experience_type in (ExperienceType.SUCCESS, ExperienceType.STRATEGY)]
            failures = [e for e in exps if e.experience_type == ExperienceType.FAILURE]
            lessons = [e for e in exps if e.experience_type == ExperienceType.LESSON]

            # --- Success wisdom ---
            if len(successes) >= min_support:
                kw_counter: Counter = Counter()
                for exp in successes:
                    for kw in exp_keywords(exp):
                        kw_counter[kw] += 1
                top_kws = [kw for kw, c in kw_counter.most_common(6) if c >= min_support]
                if top_kws:
                    avg_conf = sum(e.confidence for e in successes) / len(successes)
                    is_cross = bool(set(top_kws[:3]) & cross_domain_kws)
                    wisdoms.append(Wisdom(
                        wisdom_id=f"wis_{uuid.uuid4().hex[:8]}",
                        domain=dom,
                        insight=(
                            f"In '{dom}', approaches involving "
                            f"{', '.join(top_kws[:3])} consistently produce successful outcomes "
                            f"({len(successes)} supporting experiences)."
                        ),
                        source_types=["success", "strategy"],
                        supporting_count=len(successes),
                        confidence=round(avg_conf, 3),
                        keywords=top_kws,
                        cross_domain_applicable=is_cross,
                        related_domains=[],
                    ))

            # --- Failure wisdom ---
            if len(failures) >= min_support:
                kw_counter = Counter()
                for exp in failures:
                    for kw in exp_keywords(exp):
                        kw_counter[kw] += 1
                top_kws = [kw for kw, c in kw_counter.most_common(6) if c >= min_support]
                if top_kws:
                    avg_conf = sum(e.confidence for e in failures) / len(failures)
                    is_cross = bool(set(top_kws[:3]) & cross_domain_kws)
                    wisdoms.append(Wisdom(
                        wisdom_id=f"wis_{uuid.uuid4().hex[:8]}",
                        domain=dom,
                        insight=(
                            f"In '{dom}', situations involving "
                            f"{', '.join(top_kws[:3])} frequently lead to failures — "
                            f"avoid or mitigate these conditions "
                            f"({len(failures)} supporting experiences)."
                        ),
                        source_types=["failure"],
                        supporting_count=len(failures),
                        confidence=round(avg_conf, 3),
                        keywords=top_kws,
                        cross_domain_applicable=is_cross,
                        related_domains=[],
                    ))

            # --- Lesson wisdom ---
            if len(lessons) >= min_support:
                kw_counter = Counter()
                for exp in lessons:
                    for kw in exp_keywords(exp):
                        kw_counter[kw] += 1
                top_kws = [kw for kw, c in kw_counter.most_common(6) if c >= min_support]
                if top_kws:
                    avg_conf = sum(e.confidence for e in lessons) / len(lessons)
                    is_cross = bool(set(top_kws[:3]) & cross_domain_kws)
                    wisdoms.append(Wisdom(
                        wisdom_id=f"wis_{uuid.uuid4().hex[:8]}",
                        domain=dom,
                        insight=(
                            f"Lessons from '{dom}' emphasize: "
                            f"{', '.join(top_kws[:3])} are critical success factors "
                            f"({len(lessons)} lessons recorded)."
                        ),
                        source_types=["lesson"],
                        supporting_count=len(lessons),
                        confidence=round(avg_conf, 3),
                        keywords=top_kws,
                        cross_domain_applicable=is_cross,
                        related_domains=[],
                    ))

        wisdoms.sort(key=lambda w: (w.supporting_count, w.confidence), reverse=True)
        return wisdoms

    # ── Feature 5: Experience Aging ───────────────────────────────

    def apply_age_decay(
        self,
        half_life_days: int = 180,
        min_confidence: float = 0.1,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Apply time-based confidence decay to old experiences.

        Uses an exponential decay model:
            new_confidence = confidence * e^(-age_days / half_life_days)
        Experiences with very high times_applied are protected from full decay.

        Args:
            half_life_days: Number of days after which confidence halves.
            min_confidence: Confidence floor — never decays below this.
            dry_run: If True, return what would change without persisting.

        Returns:
            Dict with decay stats: total_processed, total_decayed, avg_delta.
        """
        rows = self.conn.execute(
            "SELECT id, confidence, times_applied, created_at FROM experiences"
        ).fetchall()

        now = datetime.now(timezone.utc)
        total_decayed = 0
        total_delta = 0.0
        updates: list[tuple[float, str]] = []

        for row in rows:
            try:
                created = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                continue

            age_days = (now - created).total_seconds() / 86400
            if age_days < 1:
                continue  # Too fresh to decay

            # Protection factor: frequently-applied experiences decay slower
            protection = 1.0 + math.log1p(row["times_applied"]) * 0.2
            effective_half_life = half_life_days * protection

            decay_factor = math.exp(-age_days / effective_half_life)
            new_confidence = max(min_confidence, row["confidence"] * decay_factor)
            delta = row["confidence"] - new_confidence

            if delta > 0.001:  # Only update if change is meaningful
                updates.append((new_confidence, row["id"]))
                total_decayed += 1
                total_delta += delta

        if not dry_run and updates:
            self.conn.executemany(
                "UPDATE experiences SET confidence = ? WHERE id = ?",
                updates,
            )
            self.conn.commit()

        return {
            "total_processed": len(rows),
            "total_decayed": total_decayed,
            "avg_confidence_delta": round(total_delta / max(total_decayed, 1), 4),
            "dry_run": dry_run,
        }

    def get_aged_experiences(self, older_than_days: int = 90) -> list[Experience]:
        """Return experiences older than the given threshold (for review/archiving)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        rows = self.conn.execute(
            "SELECT * FROM experiences WHERE created_at < ? ORDER BY created_at ASC",
            (cutoff,),
        ).fetchall()
        return [self._row_to_experience(r) for r in rows]

    # ── Feature 6: Cross-Domain Learning ──────────────────────────

    def transfer_lesson(
        self,
        source_domain: str,
        target_domain: str,
        min_confidence: float = 0.6,
        max_transfer: int = 5,
    ) -> list[Experience]:
        """Apply lessons from source_domain to target_domain.

        Finds high-confidence lessons/strategies in source_domain and
        records adapted copies in target_domain with slightly reduced
        confidence (to reflect uncertainty of cross-domain transfer).

        Returns the list of newly created cross-domain experiences.
        """
        # Get high-confidence lessons/strategies from source domain
        candidates = self.conn.execute(
            """SELECT * FROM experiences
               WHERE domain = ?
               AND experience_type IN ('lesson', 'strategy')
               AND confidence >= ?
               AND (source_domain IS NULL OR source_domain != ?)
               ORDER BY confidence DESC, times_applied DESC
               LIMIT ?""",
            (source_domain, min_confidence, target_domain, max_transfer * 2),
        ).fetchall()

        # Check which source titles have NOT already been transferred to target.
        # Stored adapted titles have the "[From <source>] " prefix, so we strip
        # it to compare against the original source title.
        already_transferred: set[str] = set()
        existing = self.conn.execute(
            "SELECT title FROM experiences WHERE domain = ? AND source_domain = ?",
            (target_domain, source_domain),
        ).fetchall()
        prefix = f"[from {source_domain}] "
        for row in existing:
            stored_title = row["title"].lower()
            if stored_title.startswith(prefix):
                stored_title = stored_title[len(prefix):]
            already_transferred.add(stored_title)

        created: list[Experience] = []
        for row in candidates:
            if len(created) >= max_transfer:
                break
            orig = self._row_to_experience(row)
            if orig.title.lower() in already_transferred:
                continue

            # Adapt the lesson for the new domain
            adapted_title = f"[From {source_domain}] {orig.title}"
            adapted_desc = (
                f"Cross-domain lesson transferred from '{source_domain}': "
                f"{orig.description}"
            )
            adapted_tags = orig.tags + [f"from:{source_domain}", "cross-domain"]
            # Reduce confidence by 15% to reflect transfer uncertainty
            transfer_confidence = round(max(0.1, orig.confidence * 0.85), 3)

            new_exp = self.record_experience(
                experience_type=orig.experience_type.value,
                domain=target_domain,
                title=adapted_title,
                description=adapted_desc,
                context=orig.context,
                outcome=orig.outcome,
                confidence=transfer_confidence,
                tags=adapted_tags,
                source_domain=source_domain,
            )
            created.append(new_exp)

        return created

    def find_cross_domain_lessons(
        self,
        target_domain: str,
        limit: int = 10,
    ) -> list[Experience]:
        """Find all cross-domain experiences that have been applied to target_domain."""
        rows = self.conn.execute(
            """SELECT * FROM experiences
               WHERE domain = ? AND source_domain IS NOT NULL
               ORDER BY confidence DESC, times_applied DESC
               LIMIT ?""",
            (target_domain, limit),
        ).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def get_domain_connections(self) -> dict[str, list[str]]:
        """Map which domains have shared cross-domain lessons.

        Returns a dict: {source_domain: [target_domain, ...]} for all
        cross-domain transfers on record.
        """
        rows = self.conn.execute(
            """SELECT DISTINCT domain, source_domain FROM experiences
               WHERE source_domain IS NOT NULL"""
        ).fetchall()
        connections: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            connections[row["source_domain"]].append(row["domain"])
        return dict(connections)

    # ── Feature 7: Visualization Data ─────────────────────────────

    def get_visualization_data(self) -> dict[str, Any]:
        """Return aggregated data structures suitable for frontend charts.

        Provides:
        - experience_timeline: experience counts per week (last 12 weeks)
        - domain_breakdown: pie chart data by domain
        - type_distribution: bar chart data by experience_type
        - confidence_histogram: confidence distribution (buckets: 0-0.2, 0.2-0.4, ...)
        - top_domains_by_confidence: ranked domains by average confidence
        - activity_heatmap: daily experience creation counts (last 30 days)
        - cross_domain_graph: nodes (domains) + edges (transfers) for graph viz
        """
        now = datetime.now(timezone.utc)

        # 1. Experience timeline (last 12 weeks)
        weekly_counts: dict[str, int] = {}
        for week_offset in range(12):
            week_start = now - timedelta(weeks=week_offset + 1)
            week_end = now - timedelta(weeks=week_offset)
            label = week_start.strftime("%Y-W%W")
            count = self.conn.execute(
                "SELECT COUNT(*) as c FROM experiences WHERE created_at >= ? AND created_at < ?",
                (week_start.isoformat(), week_end.isoformat()),
            ).fetchone()["c"]
            weekly_counts[label] = count
        timeline = [
            {"week": k, "count": v}
            for k, v in sorted(weekly_counts.items())
        ]

        # 2. Domain breakdown
        domain_rows = self.conn.execute(
            "SELECT domain, COUNT(*) as cnt FROM experiences GROUP BY domain ORDER BY cnt DESC"
        ).fetchall()
        domain_breakdown = [{"domain": r["domain"], "count": r["cnt"]} for r in domain_rows]

        # 3. Type distribution
        type_rows = self.conn.execute(
            "SELECT experience_type, COUNT(*) as cnt, AVG(confidence) as avg_conf FROM experiences GROUP BY experience_type"
        ).fetchall()
        type_distribution = [
            {
                "type": r["experience_type"],
                "count": r["cnt"],
                "avg_confidence": round(r["avg_conf"], 3),
            }
            for r in type_rows
        ]

        # 4. Confidence histogram (6 buckets: 0-0.2, 0.2-0.4, ..., 0.8-1.0+)
        confidence_buckets = []
        bucket_edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        for i in range(len(bucket_edges) - 1):
            lo, hi = bucket_edges[i], bucket_edges[i + 1]
            # Include upper bound in last bucket
            op = "<=" if hi == 1.0 else "<"
            count = self.conn.execute(
                f"SELECT COUNT(*) as c FROM experiences WHERE confidence >= ? AND confidence {op} ?",
                (lo, hi),
            ).fetchone()["c"]
            confidence_buckets.append({
                "range": f"{lo:.1f}-{hi:.1f}",
                "count": count,
            })

        # 5. Top domains by average confidence
        top_domains = self.conn.execute(
            """SELECT domain, AVG(confidence) as avg_conf, COUNT(*) as cnt
               FROM experiences GROUP BY domain
               HAVING cnt >= 1
               ORDER BY avg_conf DESC LIMIT 10"""
        ).fetchall()
        top_domains_by_confidence = [
            {"domain": r["domain"], "avg_confidence": round(r["avg_conf"], 3), "count": r["cnt"]}
            for r in top_domains
        ]

        # 6. Activity heatmap (last 30 days)
        activity_heatmap = []
        for day_offset in range(30):
            day = now - timedelta(days=day_offset)
            day_str = day.strftime("%Y-%m-%d")
            day_start = day_str + "T00:00:00"
            day_end = day_str + "T23:59:59"
            count = self.conn.execute(
                "SELECT COUNT(*) as c FROM experiences WHERE created_at >= ? AND created_at <= ?",
                (day_start, day_end),
            ).fetchone()["c"]
            activity_heatmap.append({"date": day_str, "count": count})
        activity_heatmap.reverse()  # Oldest first

        # 7. Cross-domain graph
        connections = self.get_domain_connections()
        all_domains = set()
        edges = []
        for src, targets in connections.items():
            all_domains.add(src)
            for tgt in targets:
                all_domains.add(tgt)
                edges.append({"source": src, "target": tgt})
        # Add isolated domains (no cross-domain links)
        for row in domain_rows:
            all_domains.add(row["domain"])
        cross_domain_graph = {
            "nodes": [{"id": d} for d in sorted(all_domains)],
            "edges": edges,
        }

        return {
            "experience_timeline": timeline,
            "domain_breakdown": domain_breakdown,
            "type_distribution": type_distribution,
            "confidence_histogram": confidence_buckets,
            "top_domains_by_confidence": top_domains_by_confidence,
            "activity_heatmap": activity_heatmap,
            "cross_domain_graph": cross_domain_graph,
        }

    @staticmethod
    def _row_to_experience(row: sqlite3.Row) -> Experience:
        tags = [t.strip() for t in row["tags"].split(",") if t.strip()]
        try:
            context = json.loads(row["context"]) if row["context"] else {}
        except json.JSONDecodeError:
            context = {}
        return Experience(
            id=row["id"],
            experience_type=ExperienceType(row["experience_type"]),
            domain=row["domain"],
            title=row["title"],
            description=row["description"],
            context=context,
            outcome=row["outcome"],
            confidence=row["confidence"],
            times_applied=row["times_applied"],
            created_at=row["created_at"],
            tags=tags,
        )
