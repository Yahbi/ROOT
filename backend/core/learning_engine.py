"""
Learning Engine — ROOT's outcome-based learning system.

The missing link between doing things and getting better at them.
Tracks outcomes of every interaction, routing decision, and experiment,
then feeds those outcomes back into future decisions.

Three feedback loops:
1. INTERACTION SCORING — Did the response satisfy the user?
2. ROUTING LEARNING — Which agents handle which tasks best?
3. EXPERIMENT LEARNING — Which types of experiments yield results?
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.learning")

LEARNING_DB = ROOT_DIR / "data" / "learning.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LearningEngine:
    """Tracks outcomes and adapts ROOT's behavior based on results.

    Four learning subsystems:
    - Interaction outcomes: score every chat, learn what works
    - Routing weights: track agent success rates, prefer better agents
    - Experiment patterns: learn which experiment types yield improvements
    - Experience feedback: past success/failure wisdom informs weight adjustments
    """

    def __init__(self, experience_memory=None) -> None:
        self._conn: Optional[sqlite3.Connection] = None
        self._routing_weights: dict[str, float] = {}  # agent_id → success_weight
        self._experiment_weights: dict[str, float] = {}  # area → success_weight
        self._experience_memory = experience_memory

    def set_experience_memory(self, exp_mem) -> None:
        """Late-bind experience memory for wisdom-informed routing."""
        self._experience_memory = exp_mem

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        """Initialize the learning database."""
        LEARNING_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(LEARNING_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        self._load_weights()
        logger.info("LearningEngine started (db=%s)", LEARNING_DB)

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self, '_conn') and self._conn:
            self._conn.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("LearningEngine not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            -- Every chat interaction and its outcome
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                user_message TEXT NOT NULL,
                route TEXT NOT NULL,
                agents_used TEXT DEFAULT '',
                response_length INTEGER DEFAULT 0,
                agent_findings_count INTEGER DEFAULT 0,
                tools_used_count INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0,
                quality_score REAL DEFAULT 0,
                user_feedback TEXT,
                created_at TEXT NOT NULL
            );

            -- Agent performance on tasks
            CREATE TABLE IF NOT EXISTS agent_outcomes (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                task_description TEXT NOT NULL,
                task_category TEXT DEFAULT 'general',
                status TEXT NOT NULL,
                result_quality REAL DEFAULT 0,
                duration_seconds REAL DEFAULT 0,
                tools_used INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT NOT NULL
            );

            -- Experiment outcome tracking
            CREATE TABLE IF NOT EXISTS experiment_outcomes (
                id TEXT PRIMARY KEY,
                area TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                maturity_before REAL DEFAULT 0,
                maturity_after REAL DEFAULT 0,
                impact REAL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            -- Learned routing preferences
            CREATE TABLE IF NOT EXISTS routing_weights (
                agent_id TEXT NOT NULL,
                task_category TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (agent_id, task_category)
            );

            CREATE INDEX IF NOT EXISTS idx_interactions_created
                ON interactions(created_at);
            CREATE INDEX IF NOT EXISTS idx_agent_outcomes_agent
                ON agent_outcomes(agent_id);
            CREATE INDEX IF NOT EXISTS idx_experiment_area
                ON experiment_outcomes(area);
        """)

    # ── Interaction Scoring ────────────────────────────────────

    def record_interaction(
        self,
        user_message: str,
        route: str,
        agents_used: list[str],
        response_length: int,
        agent_findings_count: int,
        tools_used_count: int,
        duration_seconds: float,
    ) -> str:
        """Record a chat interaction for outcome tracking. Returns interaction ID."""
        interaction_id = f"int_{uuid.uuid4().hex[:12]}"

        # Auto-score based on heuristics
        quality = self._auto_score_interaction(
            route=route,
            agents_used=agents_used,
            response_length=response_length,
            agent_findings_count=agent_findings_count,
            tools_used_count=tools_used_count,
            duration_seconds=duration_seconds,
            user_message=user_message,
        )

        self.conn.execute(
            """INSERT INTO interactions
               (id, user_message, route, agents_used, response_length,
                agent_findings_count, tools_used_count, duration_seconds,
                quality_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                interaction_id,
                user_message[:500],
                route,
                ",".join(agents_used),
                response_length,
                agent_findings_count,
                tools_used_count,
                duration_seconds,
                quality,
                _now_iso(),
            ),
        )
        self.conn.commit()
        return interaction_id

    def record_user_feedback(self, interaction_id: str, feedback: str) -> None:
        """Record explicit user feedback on an interaction."""
        # Positive feedback boosts score, negative lowers it
        sentiment = self._classify_feedback(feedback)
        adjustment = 0.3 if sentiment == "positive" else -0.3 if sentiment == "negative" else 0.0

        self.conn.execute(
            """UPDATE interactions
               SET user_feedback = ?, quality_score = MIN(1.0, MAX(0.0, quality_score + ?))
               WHERE id = ?""",
            (feedback[:500], adjustment, interaction_id),
        )
        self.conn.commit()

        # Update routing weights based on feedback
        row = self.conn.execute(
            "SELECT agents_used, route FROM interactions WHERE id = ?",
            (interaction_id,),
        ).fetchone()
        if row and row["agents_used"]:
            agents = row["agents_used"].split(",")
            for agent_id in agents:
                if agent_id.strip():
                    self._update_routing_weight(
                        agent_id.strip(), "general",
                        success=(sentiment == "positive"),
                    )

    def _auto_score_interaction(
        self,
        route: str,
        agents_used: list[str],
        response_length: int,
        agent_findings_count: int,
        tools_used_count: int,
        duration_seconds: float,
        user_message: str,
    ) -> float:
        """Heuristic quality score for an interaction (0.0 to 1.0)."""
        score = 0.5  # Base score

        # Research tasks should use agents and tools
        msg_lower = user_message.lower()
        is_research = any(w in msg_lower for w in (
            "research", "find", "search", "analyze", "scan", "check", "look",
            "investigate", "compare", "evaluate", "market", "trading",
        ))

        if is_research:
            if agent_findings_count > 0:
                score += 0.2  # Used agents for research = good
            if tools_used_count > 0:
                score += 0.15  # Used tools = good
            if route in ("delegate", "multi"):
                score += 0.1  # Correct routing
            if route == "direct" and not agents_used:
                score -= 0.3  # Bad: research routed as direct
        else:
            # Simple queries: fast, concise = good
            if duration_seconds < 5:
                score += 0.1
            if response_length > 50:
                score += 0.1

        # Penalize very long responses (probably hallucinating)
        if response_length > 5000:
            score -= 0.1

        # Penalize timeouts
        if duration_seconds > 60:
            score -= 0.2

        return max(0.0, min(1.0, score))

    @staticmethod
    def _classify_feedback(feedback: str) -> str:
        """Simple sentiment classification for feedback."""
        lower = feedback.lower()
        positive_words = {"good", "great", "perfect", "thanks", "helpful", "nice", "exactly", "correct", "yes", "love"}
        negative_words = {"bad", "wrong", "no", "incorrect", "useless", "terrible", "fix", "broken", "fail", "didn't"}
        pos = sum(1 for w in positive_words if w in lower)
        neg = sum(1 for w in negative_words if w in lower)
        if pos > neg:
            return "positive"
        if neg > pos:
            return "negative"
        return "neutral"

    # ── Agent Outcome Tracking ─────────────────────────────────

    def record_agent_outcome(
        self,
        agent_id: str,
        task_description: str,
        status: str,
        result_quality: float = 0.5,
        duration_seconds: float = 0,
        tools_used: int = 0,
        error_message: str = "",
        task_category: str = "general",
    ) -> None:
        """Record how well an agent performed a task."""
        self.conn.execute(
            """INSERT INTO agent_outcomes
               (id, agent_id, task_description, task_category, status,
                result_quality, duration_seconds, tools_used, error_message, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"ao_{uuid.uuid4().hex[:12]}",
                agent_id,
                task_description[:500],
                task_category,
                status,
                result_quality,
                duration_seconds,
                tools_used,
                error_message[:500] if error_message else None,
                _now_iso(),
            ),
        )
        self.conn.commit()

        # Update routing weights
        success = status in ("success", "completed") and result_quality >= 0.5
        self._update_routing_weight(agent_id, task_category, success)

        # Record outcome as experience wisdom for future reference
        self._record_as_experience(
            agent_id, task_description, task_category, success, result_quality,
        )

    def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """Get performance statistics for an agent."""
        rows = self.conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status IN ('success','completed') THEN 1 ELSE 0 END) as successes,
                AVG(result_quality) as avg_quality,
                AVG(duration_seconds) as avg_duration
               FROM agent_outcomes WHERE agent_id = ?""",
            (agent_id,),
        ).fetchone()
        if not rows or rows["total"] == 0:
            return {"total": 0, "success_rate": 0, "avg_quality": 0}
        return {
            "total": rows["total"],
            "success_rate": round((rows["successes"] or 0) / rows["total"], 3),
            "avg_quality": round(rows["avg_quality"] or 0, 3),
            "avg_duration": round(rows["avg_duration"] or 0, 2),
        }

    def get_best_agent_for(self, task_category: str) -> Optional[str]:
        """Return the agent with highest weight for a task category."""
        row = self.conn.execute(
            """SELECT agent_id, weight FROM routing_weights
               WHERE task_category = ? ORDER BY weight DESC LIMIT 1""",
            (task_category,),
        ).fetchone()
        if row and row["weight"] > 0.5:
            return row["agent_id"]
        return None

    # ── Experience Memory Feedback ─────────────────────────────

    def _record_as_experience(
        self,
        agent_id: str,
        task_description: str,
        task_category: str,
        success: bool,
        result_quality: float,
    ) -> None:
        """Store agent outcome as experience wisdom for future routing decisions."""
        if not self._experience_memory:
            return
        try:
            exp_type = "success" if success else "failure"
            title = f"Agent {agent_id} {'succeeded' if success else 'failed'} on {task_category}"
            description = (
                f"Agent '{agent_id}' {'succeeded' if success else 'failed'} on "
                f"{task_category} task: {task_description[:200]}. "
                f"Quality: {result_quality:.2f}"
            )
            self._experience_memory.record_experience(
                experience_type=exp_type,
                domain="routing",
                title=title[:200],
                description=description,
                context={"agent_id": agent_id, "category": task_category},
                outcome=f"quality={result_quality:.2f}",
                tags=[agent_id, task_category, "routing_outcome"],
            )
        except Exception as exc:
            logger.debug("Experience recording skipped: %s", exc)

    def get_experience_routing_hints(self, task_category: str) -> list[str]:
        """Query experience memory for routing wisdom on a task category.

        Returns a list of insight strings from past successes/failures
        that can inform which agent to route to.
        """
        if not self._experience_memory:
            return []
        try:
            experiences = self._experience_memory.search_experiences(
                query=f"routing {task_category}",
                limit=5,
            )
            return [
                f"[{e.experience_type.value}] {e.description[:150]}"
                for e in experiences
                if e.description
            ]
        except Exception as exc:
            logger.warning("Experience query failed: %s", exc)
            return []

    # ── Routing Weight Management ──────────────────────────────

    def _update_routing_weight(self, agent_id: str, category: str, success: bool) -> None:
        """Adjust routing weight for an agent based on outcome."""
        row = self.conn.execute(
            "SELECT weight, success_count, failure_count FROM routing_weights WHERE agent_id = ? AND task_category = ?",
            (agent_id, category),
        ).fetchone()

        if row:
            sc = row["success_count"] + (1 if success else 0)
            fc = row["failure_count"] + (0 if success else 1)
            # Bayesian-ish: weight = (successes + 1) / (total + 2)
            new_weight = (sc + 1) / (sc + fc + 2)
            self.conn.execute(
                """UPDATE routing_weights SET weight = ?, success_count = ?, failure_count = ?, updated_at = ?
                   WHERE agent_id = ? AND task_category = ?""",
                (new_weight, sc, fc, _now_iso(), agent_id, category),
            )
        else:
            sc = 1 if success else 0
            fc = 0 if success else 1
            new_weight = (sc + 1) / (sc + fc + 2)
            self.conn.execute(
                """INSERT INTO routing_weights (agent_id, task_category, weight, success_count, failure_count, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (agent_id, category, new_weight, sc, fc, _now_iso()),
            )
        self.conn.commit()

        # Update in-memory cache
        self._routing_weights[f"{agent_id}:{category}"] = new_weight

    def _load_weights(self) -> None:
        """Load routing weights into memory."""
        rows = self.conn.execute("SELECT agent_id, task_category, weight FROM routing_weights").fetchall()
        self._routing_weights = {
            f"{r['agent_id']}:{r['task_category']}": r["weight"] for r in rows
        }
        # Load experiment weights
        rows = self.conn.execute(
            """SELECT area,
                      SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as wins,
                      COUNT(*) as total
               FROM experiment_outcomes GROUP BY area"""
        ).fetchall()
        self._experiment_weights = {
            r["area"]: (r["wins"] + 1) / (r["total"] + 2) for r in rows
        }

    def get_routing_weights(self) -> dict[str, float]:
        """Return all routing weights (agent:category → weight)."""
        return dict(self._routing_weights)

    def get_agent_weight(self, agent_id: str, category: str = "general") -> float:
        """Get routing weight for a specific agent and category."""
        return self._routing_weights.get(f"{agent_id}:{category}", 0.5)

    def boost_routing_weight(self, agent_id: str, category: str, amount: float = 0.05) -> float:
        """Directly boost (or reduce) an agent's routing weight for a category.

        Used by reflection engine to act on insights like 'use researcher more for market tasks'.
        Returns the new weight.
        """
        key = f"{agent_id}:{category}"
        current = self._routing_weights.get(key, 0.5)
        new_weight = max(0.01, min(0.99, current + amount))

        row = self.conn.execute(
            "SELECT success_count, failure_count FROM routing_weights WHERE agent_id = ? AND task_category = ?",
            (agent_id, category),
        ).fetchone()

        if row:
            self.conn.execute(
                "UPDATE routing_weights SET weight = ?, updated_at = ? WHERE agent_id = ? AND task_category = ?",
                (new_weight, _now_iso(), agent_id, category),
            )
        else:
            self.conn.execute(
                "INSERT INTO routing_weights (agent_id, task_category, weight, success_count, failure_count, updated_at) VALUES (?, ?, ?, 0, 0, ?)",
                (agent_id, category, new_weight, _now_iso()),
            )
        self.conn.commit()
        self._routing_weights[key] = new_weight
        return new_weight

    # ── Experiment Outcome Tracking ────────────────────────────

    def record_experiment_outcome(
        self,
        area: str,
        hypothesis: str,
        success: bool,
        maturity_before: float = 0,
        maturity_after: float = 0,
    ) -> None:
        """Record experiment result for future proposal weighting."""
        impact = maturity_after - maturity_before
        self.conn.execute(
            """INSERT INTO experiment_outcomes
               (id, area, hypothesis, success, maturity_before, maturity_after, impact, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"eo_{uuid.uuid4().hex[:12]}",
                area, hypothesis[:500], 1 if success else 0,
                maturity_before, maturity_after, impact, _now_iso(),
            ),
        )
        self.conn.commit()

        # Update experiment area weight
        key = area
        old = self._experiment_weights.get(key, 0.5)
        self._experiment_weights[key] = old * 0.8 + (0.8 if success else 0.2) * 0.2

    def get_experiment_weight(self, area: str) -> float:
        """Get success weight for an experiment area. Higher = more likely to succeed."""
        return self._experiment_weights.get(area, 0.5)

    def get_experiment_stats(self) -> dict[str, Any]:
        """Get experiment outcome statistics by area."""
        rows = self.conn.execute(
            """SELECT area,
                      COUNT(*) as total,
                      SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                      AVG(impact) as avg_impact
               FROM experiment_outcomes GROUP BY area"""
        ).fetchall()
        return {
            r["area"]: {
                "total": r["total"],
                "success_rate": round((r["successes"] or 0) / r["total"], 3),
                "avg_impact": round(r["avg_impact"] or 0, 4),
            }
            for r in rows
        }

    # ── Learning Insights ──────────────────────────────────────

    def get_insights(self) -> dict[str, Any]:
        """Generate actionable insights from accumulated outcome data."""
        insights: dict[str, Any] = {}

        # Interaction quality trend (last 50 vs previous 50)
        recent = self.conn.execute(
            "SELECT AVG(quality_score) as avg FROM interactions ORDER BY created_at DESC LIMIT 50"
        ).fetchone()
        older = self.conn.execute(
            "SELECT AVG(quality_score) as avg FROM interactions ORDER BY created_at DESC LIMIT 50 OFFSET 50"
        ).fetchone()
        if recent and older and recent["avg"] and older["avg"]:
            trend = recent["avg"] - older["avg"]
            insights["quality_trend"] = {
                "recent_avg": round(recent["avg"], 3),
                "older_avg": round(older["avg"], 3),
                "direction": "improving" if trend > 0.05 else "declining" if trend < -0.05 else "stable",
                "delta": round(trend, 3),
            }

        # Best and worst agents
        agent_rows = self.conn.execute(
            """SELECT agent_id,
                      COUNT(*) as total,
                      AVG(result_quality) as avg_q
               FROM agent_outcomes
               GROUP BY agent_id HAVING total >= 3
               ORDER BY avg_q DESC"""
        ).fetchall()
        if agent_rows:
            insights["best_agent"] = {"id": agent_rows[0]["agent_id"], "avg_quality": round(agent_rows[0]["avg_q"], 3)}
            insights["worst_agent"] = {"id": agent_rows[-1]["agent_id"], "avg_quality": round(agent_rows[-1]["avg_q"], 3)}

        # Most effective experiment area
        exp_stats = self.get_experiment_stats()
        if exp_stats:
            best_area = max(exp_stats, key=lambda a: exp_stats[a]["success_rate"])
            insights["best_experiment_area"] = {
                "area": best_area,
                **exp_stats[best_area],
            }

        # Routing failures (direct when should have been delegate)
        bad_routes = self.conn.execute(
            """SELECT COUNT(*) as cnt FROM interactions
               WHERE route = 'direct' AND quality_score < 0.4"""
        ).fetchone()
        insights["misrouted_count"] = bad_routes["cnt"] if bad_routes else 0

        # Experience-informed routing wisdom
        if self._experience_memory:
            try:
                routing_experiences = self._experience_memory.get_experiences(
                    domain="routing", limit=10,
                )
                successes = sum(1 for e in routing_experiences if e.experience_type.value == "success")
                failures = len(routing_experiences) - successes
                insights["experience_routing_wisdom"] = {
                    "total_experiences": len(routing_experiences),
                    "success_patterns": successes,
                    "failure_patterns": failures,
                }
            except Exception:
                logger.debug("Learning pattern analysis failed", exc_info=True)
        return insights

    # ── Overall Stats ──────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Overall learning engine statistics."""
        int_count = self.conn.execute("SELECT COUNT(*) as c FROM interactions").fetchone()
        ao_count = self.conn.execute("SELECT COUNT(*) as c FROM agent_outcomes").fetchone()
        eo_count = self.conn.execute("SELECT COUNT(*) as c FROM experiment_outcomes").fetchone()
        avg_quality = self.conn.execute("SELECT AVG(quality_score) as a FROM interactions").fetchone()

        return {
            "interactions_tracked": int_count["c"] if int_count else 0,
            "agent_outcomes_tracked": ao_count["c"] if ao_count else 0,
            "experiments_tracked": eo_count["c"] if eo_count else 0,
            "avg_interaction_quality": round(avg_quality["a"] or 0, 3) if avg_quality else 0,
            "routing_weights_count": len(self._routing_weights),
            "experiment_areas_tracked": len(self._experiment_weights),
        }
