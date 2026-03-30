"""
Planning Engine — chain-of-thought planning with dependency DAG support for ROOT.

Accepts a high-level goal, leverages experience memory for past outcomes,
uses LLM chain-of-thought reasoning to decompose the goal into a DAG of
subtasks with explicit dependencies, and produces an ExecutionPlan with
parallel execution layers derived from topological sort (Kahn's algorithm).

Supports replanning when a task fails — generates alternative paths
without re-running already-completed work.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.planning")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models (immutable) ─────────────────────────────────────


@dataclass(frozen=True)
class PlanTask:
    """A single task node in the execution DAG."""
    id: str
    title: str
    description: str
    agent_id: str  # which agent should execute
    depends_on: tuple[str, ...] = ()  # task IDs this depends on
    priority: int = 5
    estimated_seconds: int = 60


@dataclass(frozen=True)
class ExecutionPlan:
    """Complete execution plan with parallel layers."""
    id: str
    goal: str
    tasks: tuple[PlanTask, ...]
    layers: tuple[tuple[str, ...], ...]  # task IDs grouped by execution layer
    created_at: str
    reasoning: str = ""


# ── Agent Assignment Heuristic ──────────────────────────────────

_AGENT_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("research", "analysis", "investigate", "explore", "survey"), "researcher"),
    (("code", "build", "implement", "develop", "program", "engineer"), "coder"),
    (("trade", "market", "financial", "portfolio", "invest", "economic"), "swarm"),
    (("predict", "forecast", "probability", "scenario", "future"), "miro"),
    (("write", "content", "document", "blog", "article", "draft", "report"), "writer"),
    (("security", "audit", "vulnerability", "compliance", "protect"), "guardian"),
    (("design", "architect", "blueprint", "plan", "structure"), "builder"),
    (("analyze", "evaluate", "assess", "review", "compare"), "analyst"),
)

_VALID_AGENTS = frozenset({
    "researcher", "coder", "analyst", "writer",
    "swarm", "miro", "builder", "guardian",
})


def _infer_agent(title: str, description: str) -> str:
    """Assign an agent based on keyword matching in title and description."""
    text = f"{title} {description}".lower()
    for keywords, agent in _AGENT_KEYWORDS:
        if any(kw in text for kw in keywords):
            return agent
    return "researcher"


# ── Planning Engine ─────────────────────────────────────────────


class PlanningEngine:
    """Chain-of-thought planning with dependency DAG and parallel layers."""

    MAX_TASKS = 15
    MAX_EXPERIENCE_RESULTS = 5

    def __init__(
        self,
        llm=None,
        experience_memory=None,
        memory=None,
    ) -> None:
        self._llm = llm
        self._experience_memory = experience_memory
        self._memory = memory

    # ── Main Planning ───────────────────────────────────────────

    async def plan(self, goal: str, context: str = "") -> ExecutionPlan:
        """Generate an ExecutionPlan for the given goal.

        1. Search experience memory for similar past goals and outcomes
        2. Ask LLM to reason step-by-step about what needs to happen
        3. Generate a DAG of subtasks with explicit dependencies
        4. Assign agents based on task types
        5. Return an ExecutionPlan with parallel execution layers
        """
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        logger.info("Planning started: %s — '%s'", plan_id, goal[:100])

        # Step 1: Gather experience context
        experience_context = self._gather_experience(goal)

        # Step 2-4: LLM chain-of-thought decomposition
        tasks, reasoning = await self._llm_decompose(goal, context, experience_context)

        if not tasks:
            # Fallback: single research task
            logger.warning("LLM returned no tasks for plan %s, creating fallback", plan_id)
            tasks = [PlanTask(
                id="task_0",
                title=f"Research: {goal[:60]}",
                description=f"Investigate and execute the goal: {goal}",
                agent_id="researcher",
                priority=3,
                estimated_seconds=120,
            )]
            reasoning = "Fallback plan — LLM did not produce a valid decomposition."

        # Step 5: Topological sort for parallel layers
        layers = self.topological_sort(list(tasks))
        layer_ids = tuple(
            tuple(t.id for t in layer) for layer in layers
        )

        plan = ExecutionPlan(
            id=plan_id,
            goal=goal,
            tasks=tuple(tasks),
            layers=layer_ids,
            created_at=_now_iso(),
            reasoning=reasoning,
        )
        logger.info(
            "Plan %s ready: %d tasks, %d layers",
            plan_id, len(tasks), len(layers),
        )
        return plan

    # ── Replanning ──────────────────────────────────────────────

    async def replan(
        self,
        plan: ExecutionPlan,
        failed_task_id: str,
        failure_reason: str,
    ) -> ExecutionPlan:
        """Generate an alternative path when a task fails.

        Keeps completed tasks, replans only the failed task and its dependents.
        """
        new_plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        logger.info(
            "Replanning %s (failed: %s): %s",
            plan.id, failed_task_id, failure_reason[:100],
        )

        # Identify the failed task
        failed_task: Optional[PlanTask] = None
        task_map: dict[str, PlanTask] = {}
        for t in plan.tasks:
            task_map[t.id] = t
            if t.id == failed_task_id:
                failed_task = t

        if failed_task is None:
            raise ValueError(f"Task {failed_task_id} not found in plan {plan.id}")

        # Find all tasks that depend (transitively) on the failed task
        dependents = self._find_dependents(failed_task_id, list(plan.tasks))

        # Build context about what already succeeded
        completed_ids = {
            t.id for t in plan.tasks
            if t.id != failed_task_id and t.id not in dependents
        }
        completed_info = "\n".join(
            f"- [DONE] {task_map[tid].title}" for tid in completed_ids
        )

        failed_info = (
            f"Task '{failed_task.title}' failed: {failure_reason}\n"
            f"Dependent tasks that need replanning: "
            f"{', '.join(task_map[d].title for d in dependents if d in task_map)}"
        )

        prompt = (
            f"A plan to achieve this goal partially failed. Replan the failed portion.\n\n"
            f"GOAL: {plan.goal}\n\n"
            f"COMPLETED TASKS:\n{completed_info or '(none)'}\n\n"
            f"FAILURE:\n{failed_info}\n\n"
            f"Generate replacement tasks that achieve the same outcome via "
            f"an alternative approach. Completed tasks are available as dependencies.\n\n"
            f"Completed task IDs available: {', '.join(sorted(completed_ids)) or '(none)'}\n\n"
            "Return ONLY valid JSON (no markdown):\n"
            '[\n'
            '  {"id": "task_N", "title": "...", "description": "...", '
            '"agent_id": "researcher|coder|analyst|writer|swarm|miro|builder|guardian", '
            '"depends_on": ["task_id"], "priority": 5}\n'
            ']\n'
        )

        try:
            response = await self._llm.complete(
                system=(
                    "You are a replanning engine for an AI task system. "
                    "Generate alternative tasks that bypass the failure. "
                    "Return ONLY a JSON array of task objects."
                ),
                messages=[{"role": "user", "content": prompt}],
                model_tier="default",
                max_tokens=2000,
                temperature=0.7,
            )

            raw = self._extract_json(response)
            task_dicts = json.loads(raw)
            if isinstance(task_dicts, dict):
                task_dicts = task_dicts.get("tasks", [task_dicts])

            new_tasks = self._parse_tasks(task_dicts, id_offset=len(plan.tasks))
            reasoning = f"Replanned after failure of '{failed_task.title}': {failure_reason}"

        except Exception as exc:
            logger.error("Replan LLM failed: %s", exc)
            # Fallback: retry the failed task with researcher
            new_tasks = [PlanTask(
                id=f"task_{len(plan.tasks)}",
                title=f"Retry: {failed_task.title}",
                description=(
                    f"Alternative approach to: {failed_task.description}\n"
                    f"Previous failure: {failure_reason}"
                ),
                agent_id="researcher",
                depends_on=tuple(
                    d for d in failed_task.depends_on if d in completed_ids
                ),
                priority=max(1, failed_task.priority - 1),
                estimated_seconds=failed_task.estimated_seconds,
            )]
            reasoning = f"Fallback replan — LLM unavailable. Retrying with researcher."

        # Merge: keep completed tasks, add new tasks
        kept_tasks = tuple(t for t in plan.tasks if t.id in completed_ids)
        all_tasks = kept_tasks + tuple(new_tasks)

        layers = self.topological_sort(list(all_tasks))
        layer_ids = tuple(tuple(t.id for t in layer) for layer in layers)

        new_plan = ExecutionPlan(
            id=new_plan_id,
            goal=plan.goal,
            tasks=all_tasks,
            layers=layer_ids,
            created_at=_now_iso(),
            reasoning=reasoning,
        )
        logger.info(
            "Replan %s ready: %d tasks (%d kept, %d new), %d layers",
            new_plan_id, len(all_tasks), len(kept_tasks), len(new_tasks), len(layers),
        )
        return new_plan

    # ── Topological Sort (Kahn's Algorithm) ─────────────────────

    def topological_sort(self, tasks: list[PlanTask]) -> list[list[PlanTask]]:
        """Return layers of tasks that can run in parallel.

        Each layer's tasks have all dependencies satisfied by previous layers.
        Uses Kahn's algorithm. If cycles are detected, breaks them by removing
        the lowest-priority dependency edge.
        """
        if not tasks:
            return []

        task_map: dict[str, PlanTask] = {t.id: t for t in tasks}
        valid_ids = set(task_map.keys())

        # Build adjacency: in-degree count and adjacency list
        in_degree: dict[str, int] = {t.id: 0 for t in tasks}
        dependents: dict[str, list[str]] = {t.id: [] for t in tasks}

        for t in tasks:
            for dep_id in t.depends_on:
                if dep_id in valid_ids:
                    in_degree[t.id] += 1
                    dependents[dep_id].append(t.id)

        # Kahn's algorithm with cycle breaking
        layers: list[list[PlanTask]] = []
        remaining = set(valid_ids)

        while remaining:
            # Find all nodes with zero in-degree among remaining
            zero_in = [
                tid for tid in remaining
                if in_degree[tid] == 0
            ]

            if not zero_in:
                # Cycle detected — break by removing lowest-priority dependency
                self._break_cycle(remaining, in_degree, dependents, task_map)
                continue

            # Sort by priority (lower number = higher priority) for determinism
            zero_in.sort(key=lambda tid: (task_map[tid].priority, tid))

            layer = [task_map[tid] for tid in zero_in]
            layers.append(layer)

            for tid in zero_in:
                remaining.discard(tid)
                for dep_tid in dependents[tid]:
                    if dep_tid in remaining:
                        in_degree[dep_tid] -= 1

        return layers

    # ── Private Helpers ─────────────────────────────────────────

    def _break_cycle(
        self,
        remaining: set[str],
        in_degree: dict[str, int],
        dependents: dict[str, list[str]],
        task_map: dict[str, PlanTask],
    ) -> None:
        """Break a cycle by zeroing in-degree of the lowest-priority remaining node."""
        # Find the node in the cycle with the lowest priority (highest number)
        cycle_nodes = sorted(
            remaining,
            key=lambda tid: (-task_map[tid].priority, tid),
        )
        victim = cycle_nodes[0]
        logger.warning(
            "Cycle detected in task DAG — breaking dependency for '%s' (priority=%d)",
            task_map[victim].title, task_map[victim].priority,
        )
        in_degree[victim] = 0

    def _gather_experience(self, goal: str) -> str:
        """Search experience memory for similar past goals."""
        if not self._experience_memory:
            return ""

        try:
            # Extract key terms from the goal for search
            experiences = self._experience_memory.search_experiences(
                goal, limit=self.MAX_EXPERIENCE_RESULTS,
            )
            if not experiences:
                return ""

            lines = ["Relevant past experiences:"]
            for exp in experiences:
                outcome_str = f" → {exp.outcome}" if exp.outcome else ""
                lines.append(
                    f"- [{exp.experience_type}] {exp.title}: "
                    f"{exp.description[:150]}{outcome_str} "
                    f"(confidence={exp.confidence:.2f})"
                )
            return "\n".join(lines)

        except Exception as exc:
            logger.debug("Experience memory search failed: %s", exc)
            return ""

    async def _llm_decompose(
        self,
        goal: str,
        context: str,
        experience_context: str,
    ) -> tuple[list[PlanTask], str]:
        """Use LLM chain-of-thought to decompose goal into tasks."""
        if not self._llm:
            logger.warning("No LLM available — returning empty decomposition")
            return [], ""

        context_block = ""
        if context:
            context_block = f"\nADDITIONAL CONTEXT:\n{context}\n"
        if experience_context:
            context_block += f"\n{experience_context}\n"

        prompt = (
            f"Plan how to achieve this goal step by step.\n\n"
            f"GOAL: {goal}\n"
            f"{context_block}\n"
            f"Think through what needs to happen, then produce a JSON array of tasks.\n\n"
            f"AVAILABLE AGENT IDS:\n"
            f"- researcher: research, analysis, investigation\n"
            f"- coder: coding, building, implementation\n"
            f"- analyst: data analysis, business intelligence\n"
            f"- writer: content creation, documentation\n"
            f"- swarm: trading, market analysis, financial decisions\n"
            f"- miro: predictions, forecasting, scenario analysis\n"
            f"- builder: architecture, design, system planning\n"
            f"- guardian: security audits, compliance, protection\n\n"
            f"Return ONLY valid JSON (no markdown) with this structure:\n"
            "{\n"
            '  "reasoning": "Step-by-step thinking about the approach...",\n'
            '  "tasks": [\n'
            '    {"id": "task_0", "title": "...", "description": "...", '
            '"agent_id": "researcher", "depends_on": [], "priority": 5, '
            '"estimated_seconds": 60}\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Use task IDs like task_0, task_1, etc.\n"
            "- depends_on lists task IDs that must complete first\n"
            "- priority: 1=critical, 5=normal, 9=background\n"
            f"- Maximum {self.MAX_TASKS} tasks\n"
            "- Make tasks concrete and actionable\n"
        )

        try:
            response = await self._llm.complete(
                system=(
                    "You are a planning engine for an AI task execution system. "
                    "Decompose goals into a dependency graph of concrete tasks. "
                    "Think step by step, then output structured JSON. "
                    "Return ONLY valid JSON — no markdown fences or commentary."
                ),
                messages=[{"role": "user", "content": prompt}],
                model_tier="default",
                max_tokens=3000,
                temperature=0.5,
            )

            raw = self._extract_json(response)
            data = json.loads(raw)

            # Handle different response shapes
            if isinstance(data, list):
                task_dicts = data
                reasoning = ""
            elif isinstance(data, dict):
                task_dicts = data.get("tasks", [])
                reasoning = data.get("reasoning", "")
            else:
                logger.warning("Unexpected LLM response type: %s", type(data))
                return [], ""

            tasks = self._parse_tasks(task_dicts[:self.MAX_TASKS])
            return tasks, reasoning

        except json.JSONDecodeError as exc:
            logger.error("Plan LLM returned invalid JSON: %s", exc)
            return [], ""
        except Exception as exc:
            logger.error("Plan LLM decomposition failed: %s", exc)
            return [], ""

    def _parse_tasks(
        self,
        task_dicts: list[dict[str, Any]],
        id_offset: int = 0,
    ) -> list[PlanTask]:
        """Parse raw dicts from LLM into PlanTask instances."""
        tasks: list[PlanTask] = []
        for i, td in enumerate(task_dicts):
            task_id = td.get("id", f"task_{i + id_offset}")
            agent_id = td.get("agent_id", "")

            # Validate or infer agent
            if agent_id not in _VALID_AGENTS:
                agent_id = _infer_agent(
                    td.get("title", ""),
                    td.get("description", ""),
                )

            depends_on = td.get("depends_on", [])
            if not isinstance(depends_on, (list, tuple)):
                depends_on = []
            depends_on = tuple(str(d) for d in depends_on)

            priority = td.get("priority", 5)
            if not isinstance(priority, int) or not (1 <= priority <= 9):
                priority = 5

            estimated = td.get("estimated_seconds", 60)
            if not isinstance(estimated, int) or estimated < 1:
                estimated = 60

            tasks.append(PlanTask(
                id=task_id,
                title=td.get("title", f"Task {i + id_offset}"),
                description=td.get("description", ""),
                agent_id=agent_id,
                depends_on=depends_on,
                priority=priority,
                estimated_seconds=estimated,
            ))
        return tasks

    def _find_dependents(
        self,
        task_id: str,
        tasks: list[PlanTask],
    ) -> set[str]:
        """Find all tasks that transitively depend on the given task."""
        dependents: set[str] = set()
        queue: deque[str] = deque([task_id])

        # Build reverse map: task_id -> set of tasks that depend on it
        reverse: dict[str, list[str]] = {}
        for t in tasks:
            for dep in t.depends_on:
                reverse.setdefault(dep, []).append(t.id)

        while queue:
            current = queue.popleft()
            for child in reverse.get(current, []):
                if child not in dependents:
                    dependents.add(child)
                    queue.append(child)

        return dependents

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown fences and extract JSON from LLM response."""
        text = text.strip()
        # Remove markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        # Try to find JSON object or array
        for start_char, end_char in (("{", "}"), ("[", "]")):
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end > start:
                return text[start:end + 1]
        return text
