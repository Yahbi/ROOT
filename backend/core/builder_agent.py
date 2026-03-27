"""
Builder Agent — ROOT's self-improvement engine that runs continuously.

The Builder Agent reviews ROOT's own codebase, identifies improvements,
creates new skills, fixes gaps, and proposes enhancements. It runs as a
background loop, always working to make ROOT better.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.builder")


@dataclass(frozen=True)
class BuildTask:
    """Immutable record of a builder improvement task."""
    id: str
    task_type: str  # "skill_create", "gap_fix", "knowledge_expand", "optimization", "bug_fix"
    description: str
    status: str = "pending"  # pending, working, completed, failed, skipped
    result: Optional[str] = None
    impact_score: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None


class BuilderAgent:
    """Always-on agent that continuously improves ROOT.

    Runs as a background loop:
    1. Analyze current state (gaps, weak areas, missing skills)
    2. Pick the highest-impact improvement
    3. Execute it (create skill, store knowledge, propose code)
    4. Log the evolution
    5. Wait, then repeat
    """

    def __init__(
        self,
        memory=None,
        skills=None,
        self_dev=None,
        llm=None,
        hooks=None,
    ) -> None:
        self._memory = memory
        self._skills = skills
        self._self_dev = self_dev
        self._llm = llm
        self._hooks = hooks
        self._task_history: list[BuildTask] = []
        self._running = False
        self._cycle_count = 0
        self._failure_count: int = 0
        self._last_improvements: list[str] = []

    @property
    def is_running(self) -> bool:
        return self._running

    async def start_loop(self, interval: int = 300) -> None:
        """Run the builder loop. Default: every 5 minutes."""
        self._running = True
        logger.info("Builder Agent started (interval=%ds)", interval)
        while self._running:
            try:
                await self._run_cycle()
                self._failure_count = 0
            except Exception as e:
                self._failure_count = self._failure_count + 1
                logger.error("Builder cycle error: %s", e)
                if self._failure_count >= 5:
                    logger.critical(
                        "Builder agent: %d consecutive failures — backing off 300s",
                        self._failure_count,
                    )
                    self._failure_count = 0
                    await asyncio.sleep(300)
                    continue
            await asyncio.sleep(interval)

    def stop(self) -> None:
        self._running = False
        logger.info("Builder Agent stopped")

    async def _run_cycle(self) -> None:
        """Single improvement cycle."""
        self._cycle_count += 1
        logger.info("Builder cycle #%d starting", self._cycle_count)

        # 1. Identify what needs improvement
        improvements = self._identify_improvements()
        if not improvements:
            logger.info("Builder: no improvements needed this cycle")
            return

        # 2. Pick top improvement
        task = improvements[0]
        working_task = BuildTask(
            id=task.id, task_type=task.task_type,
            description=task.description, status="working",
        )
        self._task_history.append(working_task)

        # 3. Execute it
        result = await self._execute_improvement(task)

        # 4. Log completion
        completed = BuildTask(
            id=task.id, task_type=task.task_type,
            description=task.description,
            status="completed" if result else "failed",
            result=result,
            impact_score=0.3 if result else -0.1,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        # Replace the working entry immutably
        if self._task_history:
            self._task_history = self._task_history[:-1]
        self._task_history.append(completed)
        # Bound task history
        if len(self._task_history) > 200:
            self._task_history = self._task_history[-200:]

        if result:
            self._last_improvements.append(f"[{task.task_type}] {task.description}")
            if len(self._last_improvements) > 20:
                self._last_improvements = self._last_improvements[-20:]
            logger.info("Builder completed: %s", task.description)

    def _identify_improvements(self) -> list[BuildTask]:
        """Scan for areas that need improvement.

        Even at 100% maturity, always finds something to improve:
        gaps → memory health → low-confidence consolidation → knowledge expansion.
        """
        tasks: list[BuildTask] = []

        if not self._self_dev:
            return tasks

        # Check for capability gaps
        gaps = self._self_dev.identify_gaps()
        for gap in gaps[:3]:
            area = gap.get("area", "unknown")
            suggestion = gap.get("suggestion", "")

            if area.startswith("skill_"):
                category = area.replace("skill_", "")
                tasks.append(BuildTask(
                    id=f"build_{uuid.uuid4().hex[:8]}",
                    task_type="skill_create",
                    description=f"Create skill for '{category}': {suggestion}",
                ))
            elif area.startswith("memory_"):
                mem_type = area.replace("memory_", "")
                tasks.append(BuildTask(
                    id=f"build_{uuid.uuid4().hex[:8]}",
                    task_type="knowledge_expand",
                    description=f"Expand {mem_type} knowledge: {suggestion}",
                ))

        # Check memory health
        if self._memory:
            stats = self._memory.stats()
            total = stats.get("total", 0)
            if total < 50:
                tasks.append(BuildTask(
                    id=f"build_{uuid.uuid4().hex[:8]}",
                    task_type="knowledge_expand",
                    description="Memory count low — bootstrap more knowledge",
                ))

        # Check for stale assessments
        if self._self_dev:
            assessment = self._self_dev.assess()
            score = assessment.get("maturity_score", 0)
            if score < 0.6:
                tasks.append(BuildTask(
                    id=f"build_{uuid.uuid4().hex[:8]}",
                    task_type="optimization",
                    description=f"Maturity low ({score:.0%}) — create skills and absorb knowledge",
                ))

        # ── Always-on improvements (even at 100% maturity) ─────────
        if not tasks:
            tasks.extend(self._always_on_improvements())

        return tasks

    def _always_on_improvements(self) -> list[BuildTask]:
        """Generate improvements even when no gaps exist.

        Ensures the builder is never idle — there's always something to improve.
        """
        tasks: list[BuildTask] = []
        cycle = self._cycle_count

        # Rotate improvement types across cycles to avoid repetition
        phase = cycle % 4

        if phase == 0 and self._memory:
            # Consolidate low-confidence memories
            from backend.models.memory import MemoryQuery
            low_conf = self._memory.search(
                MemoryQuery(query="", limit=30, min_confidence=0.0)
            )
            weak = [m for m in low_conf if m.confidence < 0.5]
            if weak:
                tasks.append(BuildTask(
                    id=f"build_{uuid.uuid4().hex[:8]}",
                    task_type="knowledge_expand",
                    description=f"Consolidate {len(weak)} weak memories — strengthen or supersede",
                ))
            else:
                tasks.append(BuildTask(
                    id=f"build_{uuid.uuid4().hex[:8]}",
                    task_type="knowledge_expand",
                    description="Expand knowledge: latest AI, trading, and automation insights",
                ))

        elif phase == 1:
            # Create skills from recent evolution patterns
            tasks.append(BuildTask(
                id=f"build_{uuid.uuid4().hex[:8]}",
                task_type="skill_create",
                description="Create skill from recent successful patterns and interactions",
            ))

        elif phase == 2 and self._memory:
            # Expand knowledge in an underrepresented domain
            stats = self._memory.stats()
            by_type = stats.get("by_type", {})
            weakest_type = min(
                by_type.items(),
                key=lambda kv: kv[1].get("count", 0),
                default=("observation", {"count": 0}),
            )
            tasks.append(BuildTask(
                id=f"build_{uuid.uuid4().hex[:8]}",
                task_type="knowledge_expand",
                description=f"Expand '{weakest_type[0]}' memories (only {weakest_type[1].get('count', 0)} entries)",
            ))

        elif phase == 3:
            # Review and improve existing skills
            tasks.append(BuildTask(
                id=f"build_{uuid.uuid4().hex[:8]}",
                task_type="optimization",
                description="Review skill library for outdated content or merge opportunities",
            ))

        return tasks

    async def _execute_improvement(self, task: BuildTask) -> Optional[str]:
        """Execute a single improvement task."""
        if task.task_type == "skill_create":
            return await self._create_skill_from_gap(task)
        if task.task_type == "knowledge_expand":
            return await self._expand_knowledge(task)
        if task.task_type == "optimization":
            return await self._optimize(task)
        return None

    async def _create_skill_from_gap(self, task: BuildTask) -> Optional[str]:
        """Use LLM (or templates) to create a new skill."""
        # Extract category from description
        category = "general"
        if "'" in task.description:
            start = task.description.index("'") + 1
            end = task.description.index("'", start)
            category = task.description[start:end]

        if self._llm:
            prompt = f"""Create a skill document for ROOT's skill library.
Category: {category}
Context: {task.description}

Write a practical skill in markdown with clear steps that ROOT can follow.
Include: title, when to use, step-by-step procedure, examples, and common pitfalls."""

            content = await self._llm.complete(
                system="You are ROOT's skill creator. Write practical, actionable skill documents.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                max_tokens=2000,
                method="builder",
            )
            if content and self._self_dev:
                name = category.replace(" ", "-").lower()
                self._self_dev.create_skill_from_pattern(
                    name=f"auto-{name}",
                    category=category,
                    description=f"Auto-generated skill for {category}",
                    content=content,
                    tags=["auto-generated", "builder-agent", category],
                )
                return f"Created skill: {category}/auto-{name}"
        else:
            # Offline: create template skill
            templates = {
                "data-analysis": "# Data Analysis\n\n## Steps\n1. Identify data source\n2. Clean and validate\n3. Analyze patterns\n4. Generate insights\n5. Present findings",
                "automation": "# Task Automation\n\n## Steps\n1. Identify repetitive task\n2. Define trigger conditions\n3. Write automation logic\n4. Test with sample data\n5. Deploy and monitor",
                "web-scraping": "# Web Scraping\n\n## Steps\n1. Identify target URL\n2. Analyze page structure\n3. Use httpx + BeautifulSoup\n4. Handle pagination\n5. Store results",
                "api-integration": "# API Integration\n\n## Steps\n1. Read API documentation\n2. Get authentication credentials\n3. Test endpoints with httpx\n4. Handle rate limits\n5. Parse and store responses",
                "prompt-engineering": "# Prompt Engineering\n\n## Steps\n1. Define the task clearly\n2. Provide context and examples\n3. Set output format\n4. Test with variations\n5. Iterate based on results",
            }
            template = templates.get(category, f"# {category}\n\n## Steps\n1. Analyze the problem\n2. Research solutions\n3. Implement\n4. Test\n5. Document")

            if self._self_dev:
                name = category.replace(" ", "-").lower()
                self._self_dev.create_skill_from_pattern(
                    name=f"auto-{name}",
                    category=category,
                    description=f"Auto-generated skill for {category}",
                    content=template,
                    tags=["auto-generated", "builder-agent", category],
                )
                return f"Created template skill: {category}/auto-{name}"

        return None

    async def _expand_knowledge(self, task: BuildTask) -> Optional[str]:
        """Expand ROOT's knowledge through memory creation."""
        if not self._memory:
            return None

        if self._llm:
            prompt = f"""Generate 3 useful knowledge entries for ROOT's memory about: {task.description}

Each entry should be a practical fact, insight, or best practice.
Return JSON array: [{{"content": "...", "type": "fact|learning|observation", "tags": ["..."]}}]"""

            result = await self._llm.complete(
                system="Generate useful knowledge entries. Return only JSON.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                max_tokens=1000,
                method="builder",
            )
            try:
                text = result.strip()
                if "```" in text:
                    start = text.index("```") + 3
                    if text[start:start + 4] == "json":
                        start += 4
                    end = text.index("```", start)
                    text = text[start:end].strip()
                entries = json.loads(text)
                if isinstance(entries, list):
                    from backend.models.memory import MemoryEntry, MemoryType
                    stored = 0
                    for e in entries[:5]:
                        try:
                            mt = MemoryType(e.get("type", "fact"))
                        except ValueError:
                            mt = MemoryType.FACT
                        self._memory.store(MemoryEntry(
                            content=e["content"],
                            memory_type=mt,
                            tags=e.get("tags", []) + ["builder-agent"],
                            source="builder_agent",
                            confidence=0.8,
                        ))
                        stored += 1
                    return f"Stored {stored} knowledge entries"
            except Exception as exc:
                logger.warning("Failed to parse knowledge entries JSON: %s", exc)

        # Offline fallback: log the intent
        if self._self_dev:
            self._self_dev.propose_improvement(
                area="knowledge",
                description=task.description,
                rationale="Identified by Builder Agent during improvement cycle",
            )
            return "Proposed knowledge expansion"

        return None

    async def _optimize(self, task: BuildTask) -> Optional[str]:
        """General optimization — creates skills for weakest areas."""
        if not self._self_dev:
            return None

        assessment = self._self_dev.assess()
        gaps = assessment.get("capability_gaps", [])

        created = 0
        for gap in gaps[:2]:
            area = gap.get("area", "")
            if area.startswith("skill_"):
                sub = BuildTask(
                    id=f"build_{uuid.uuid4().hex[:8]}",
                    task_type="skill_create",
                    description=gap.get("suggestion", f"Fill gap: {area}"),
                )
                result = await self._create_skill_from_gap(sub)
                if result:
                    created += 1

        return f"Optimized: created {created} skills to fill gaps" if created else None

    # ── Manual trigger ──

    async def run_once(self) -> list[BuildTask]:
        """Run a single improvement cycle manually. Returns completed tasks."""
        before = len(self._task_history)
        await self._run_cycle()
        return self._task_history[before:]

    # ── Status ──

    def get_history(self, limit: int = 30) -> list[BuildTask]:
        return list(reversed(self._task_history[-limit:]))

    def stats(self) -> dict[str, Any]:
        completed = sum(1 for t in self._task_history if t.status == "completed")
        failed = sum(1 for t in self._task_history if t.status == "failed")
        return {
            "running": self._running,
            "cycles": self._cycle_count,
            "total_tasks": len(self._task_history),
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / max(completed + failed, 1) * 100, 1),
            "recent_improvements": self._last_improvements[-5:],
        }
