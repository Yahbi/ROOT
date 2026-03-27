"""
Self-Development Engine — ROOT's ability to evolve itself.

Capabilities:
1. Propose code changes to its own codebase
2. Create new skills from experience
3. Identify capability gaps and plan improvements
4. Track evolution history
5. Self-assess performance
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import ROOT_DIR
from backend.core.memory_engine import MemoryEngine
from backend.core.skill_engine import SkillEngine
from backend.models.memory import MemoryEntry, MemoryType

logger = logging.getLogger("root.selfdev")

EVOLUTION_LOG = ROOT_DIR / "data" / "evolution_log.json"


@dataclass(frozen=True)
class EvolutionEntry:
    """Immutable record of a self-improvement action."""
    id: str
    action_type: str          # "skill_created", "knowledge_absorbed", "gap_identified",
                              # "code_proposed", "reflection_insight", "capability_added"
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    impact_score: float = 0.0  # -1.0 to 1.0 (negative = regression)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SelfDevEngine:
    """Drives ROOT's self-improvement and evolution tracking."""

    def __init__(self, memory: MemoryEngine, skills: SkillEngine) -> None:
        self._memory = memory
        self._skills = skills
        self._evolution_log: list[EvolutionEntry] = []
        self._load_log()

    # ── Skill Creation ─────────────────────────────────────────

    def create_skill_from_pattern(
        self,
        name: str,
        category: str,
        description: str,
        content: str,
        tags: Optional[list[str]] = None,
    ) -> EvolutionEntry:
        """Create a new skill and log the evolution."""
        skill = self._skills.create_skill(
            name=name,
            category=category,
            description=description,
            content=content,
            tags=tags,
        )
        entry = EvolutionEntry(
            id=f"evo_{uuid.uuid4().hex[:12]}",
            action_type="skill_created",
            description=f"Created skill: {category}/{name} — {description}",
            details={"skill_path": skill.path, "tags": tags or []},
            impact_score=0.5,
        )
        self._log_evolution(entry)

        # Store in memory too
        self._memory.store(MemoryEntry(
            content=f"Created skill '{name}' in category '{category}': {description}",
            memory_type=MemoryType.SKILL,
            tags=["evolution", "skill-creation", category],
            source="self_dev",
        ))

        return entry

    # ── Knowledge Absorption ───────────────────────────────────

    def absorb_from_file(self, file_path: str, source: str = "file_absorption") -> EvolutionEntry:
        """Read a file and extract knowledge into memory."""
        path = Path(file_path)
        if not path.exists():
            return EvolutionEntry(
                id=f"evo_{uuid.uuid4().hex[:12]}",
                action_type="knowledge_absorbed",
                description=f"Failed to absorb: {file_path} (not found)",
                impact_score=-0.1,
            )

        content = path.read_text(errors="replace")[:10000]
        # Store the content as a fact
        self._memory.store(MemoryEntry(
            content=f"Absorbed from {path.name}: {content[:500]}",
            memory_type=MemoryType.FACT,
            tags=["absorbed", source, path.suffix.lstrip(".")],
            source=source,
            confidence=0.8,
        ))

        entry = EvolutionEntry(
            id=f"evo_{uuid.uuid4().hex[:12]}",
            action_type="knowledge_absorbed",
            description=f"Absorbed knowledge from {path.name} ({len(content)} chars)",
            details={"file": str(path), "chars": len(content)},
            impact_score=0.3,
        )
        self._log_evolution(entry)
        return entry

    # ── Gap Analysis ───────────────────────────────────────────

    def identify_gaps(self) -> list[dict[str, str]]:
        """Identify capability gaps based on memory and skill coverage."""
        skill_categories = set(self._skills.list_categories().keys())
        memory_stats = self._memory.stats()

        gaps = []

        # Check if any memory type is underrepresented
        by_type = memory_stats.get("by_type", {})
        for mt in MemoryType:
            if mt.value not in by_type or by_type[mt.value]["count"] < 3:
                gaps.append({
                    "area": f"memory_{mt.value}",
                    "description": f"Low {mt.value} memories ({by_type.get(mt.value, {}).get('count', 0)})",
                    "suggestion": f"Actively collect more {mt.value} entries",
                })

        # Check for expected skill categories
        expected = {
            "agent-orchestration", "self-improvement", "coding-standards",
            "security", "llm-inference", "swarm-simulation", "trading",
            "multi-platform", "data-analysis", "automation",
        }
        missing_cats = expected - skill_categories
        for cat in missing_cats:
            gaps.append({
                "area": f"skill_{cat}",
                "description": f"No skills in category '{cat}'",
                "suggestion": f"Create skills for {cat} based on experience",
            })

        return gaps

    # ── Self-Assessment ────────────────────────────────────────

    def assess(self) -> dict[str, Any]:
        """Self-assessment of ROOT's current capabilities."""
        memory_stats = self._memory.stats()
        skill_stats = self._skills.stats()
        gaps = self.identify_gaps()

        total_memories = memory_stats.get("total", 0)
        total_skills = skill_stats.get("total", 0)
        total_evolutions = len(self._evolution_log)
        by_type = memory_stats.get("by_type", {})

        # Maturity score — weighted across 5 dimensions
        mem_score = min(1.0, total_memories / 150)        # 150 memories = full
        skill_score = min(1.0, total_skills / 25)         # 25 skills = full
        evo_score = min(1.0, total_evolutions / 30)       # 30 evolutions = full
        gap_score = max(0.0, 1 - len(gaps) / 10)          # 0 gaps = full
        # Diversity: all 8 memory types populated
        populated_types = sum(1 for t in MemoryType if t.value in by_type and by_type[t.value]["count"] >= 3)
        diversity_score = min(1.0, populated_types / 8)

        maturity = min(1.0, (
            mem_score * 0.20 +
            skill_score * 0.20 +
            evo_score * 0.20 +
            gap_score * 0.20 +
            diversity_score * 0.20
        ))

        return {
            "maturity_score": round(maturity, 3),
            "maturity_level": (
                "embryonic" if maturity < 0.2 else
                "nascent" if maturity < 0.4 else
                "developing" if maturity < 0.6 else
                "capable" if maturity < 0.75 else
                "advanced" if maturity < 0.90 else
                "expert" if maturity < 0.95 else
                "mastery"
            ),
            "memories": memory_stats,
            "skills": skill_stats,
            "evolution_count": total_evolutions,
            "capability_gaps": gaps,
            "recent_evolution": [
                {"type": e.action_type, "desc": e.description, "time": e.timestamp}
                for e in self._evolution_log[-5:]
            ],
        }

    # ── Code Proposals ─────────────────────────────────────────

    def propose_improvement(self, area: str, description: str, rationale: str) -> EvolutionEntry:
        """Log a proposed code improvement for ROOT itself."""
        entry = EvolutionEntry(
            id=f"evo_{uuid.uuid4().hex[:12]}",
            action_type="code_proposed",
            description=f"Proposed improvement in {area}: {description}",
            details={"area": area, "rationale": rationale},
            impact_score=0.0,  # No impact until implemented
        )
        self._log_evolution(entry)

        self._memory.store(MemoryEntry(
            content=f"Self-improvement proposal: {description}. Rationale: {rationale}",
            memory_type=MemoryType.GOAL,
            tags=["self-dev", "proposal", area],
            source="self_dev",
            confidence=0.7,
        ))

        return entry

    # ── Evolution Log ──────────────────────────────────────────

    def get_evolution_log(self, limit: int = 50) -> list[EvolutionEntry]:
        return list(reversed(self._evolution_log[-limit:]))

    def get_evolution_stats(self) -> dict[str, Any]:
        """Summarize evolution activity."""
        by_type: dict[str, int] = {}
        total_impact = 0.0
        for e in self._evolution_log:
            by_type[e.action_type] = by_type.get(e.action_type, 0) + 1
            total_impact += e.impact_score
        return {
            "total_entries": len(self._evolution_log),
            "by_type": by_type,
            "net_impact": round(total_impact, 3),
        }

    # ── Persistence ────────────────────────────────────────────

    def _log_evolution(self, entry: EvolutionEntry) -> None:
        """Append to evolution log and persist."""
        self._evolution_log.append(entry)
        self._save_log()

    def _save_log(self) -> None:
        EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "id": e.id,
                "action_type": e.action_type,
                "description": e.description,
                "details": e.details,
                "impact_score": e.impact_score,
                "timestamp": e.timestamp,
            }
            for e in self._evolution_log[-500:]
        ]
        EVOLUTION_LOG.write_text(json.dumps(data, indent=2))

    def _load_log(self) -> None:
        if EVOLUTION_LOG.exists():
            try:
                data = json.loads(EVOLUTION_LOG.read_text())
                self._evolution_log = [
                    EvolutionEntry(
                        id=e["id"],
                        action_type=e["action_type"],
                        description=e["description"],
                        details=e.get("details", {}),
                        impact_score=e.get("impact_score", 0.0),
                        timestamp=e.get("timestamp", ""),
                    )
                    for e in data
                ]
            except Exception as e:
                logger.error("Failed to load evolution log: %s", e)
