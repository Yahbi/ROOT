"""
Autonomous Task Executor — goal decomposition + multi-step execution.

Accepts a high-level goal, uses LLM to decompose it into ordered subtasks,
executes each subtask through the appropriate agent, self-corrects on failure,
and synthesizes a final result.

Flow:
1. SUBMIT   — User provides a goal string
2. DECOMPOSE — LLM breaks goal into subtasks with agent assignments
3. EXECUTE   — Subtasks run via agent collaboration (respecting dependencies)
4. CORRECT   — Failed subtasks retry with LLM-proposed alternatives
5. FINALIZE  — Results synthesized, stored in memory, outcomes recorded
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.task_executor")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models (immutable) ──────────────────────────────────────


@dataclass(frozen=True)
class SubtaskState:
    """One step in a decomposed task."""
    id: str
    index: int
    description: str
    agent_id: str
    tools_hint: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    risk_level: str = "low"
    status: str = "pending"  # pending | running | completed | failed | skipped | cancelled
    result: Optional[str] = None
    error: Optional[str] = None
    attempt: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass(frozen=True)
class TaskPlan:
    """LLM-generated decomposition of a goal."""
    subtasks: tuple[SubtaskState, ...]
    reasoning: str
    estimated_duration_seconds: int = 120


@dataclass(frozen=True)
class AutonomousTask:
    """Top-level autonomous task envelope."""
    id: str
    goal: str
    status: str = "pending"  # pending | planning | executing | completed | failed | cancelled
    plan: Optional[TaskPlan] = None
    subtasks: tuple[SubtaskState, ...] = ()
    final_result: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Task Executor ────────────────────────────────────────────────


class TaskExecutor:
    """Autonomous goal decomposition and multi-step execution engine."""

    MAX_SUBTASKS = 10
    MAX_RETRIES = 2
    DEFAULT_TIMEOUT = 120
    MAX_ACTIVE = 5

    def __init__(
        self,
        llm=None,
        collab=None,
        plugins=None,
        approval=None,
        bus=None,
        memory=None,
        learning=None,
        registry=None,
    ) -> None:
        self._llm = llm
        self._collab = collab
        self._plugins = plugins
        self._approval = approval
        self._bus = bus
        self._memory = memory
        self._learning = learning
        self._registry = registry

        self._tasks: dict[str, AutonomousTask] = {}
        self._async_tasks: dict[str, asyncio.Task] = {}

    # ── Public API ───────────────────────────────────────────────

    async def submit(self, goal: str, metadata: Optional[dict[str, Any]] = None) -> AutonomousTask:
        """Submit a goal for autonomous execution. Returns immediately."""
        active = [t for t in self._tasks.values() if t.status in ("pending", "planning", "executing")]
        if len(active) >= self.MAX_ACTIVE:
            raise RuntimeError(f"Max {self.MAX_ACTIVE} concurrent tasks — cancel one first")

        task = AutonomousTask(
            id=f"atask_{uuid.uuid4().hex[:12]}",
            goal=goal,
            metadata=metadata or {},
        )
        self._tasks[task.id] = task
        self._async_tasks[task.id] = asyncio.create_task(self._run_task(task.id))
        logger.info("Task submitted: %s — '%s'", task.id, goal[:80])
        return task

    async def cancel(self, task_id: str) -> Optional[AutonomousTask]:
        """Cancel a running task."""
        task = self._tasks.get(task_id)
        if not task or task.status in ("completed", "failed", "cancelled"):
            return task

        # Cancel asyncio task
        atask = self._async_tasks.pop(task_id, None)
        if atask:
            atask.cancel()

        cancelled_subtasks = tuple(
            replace(s, status="cancelled") if s.status in ("pending", "running") else s
            for s in task.subtasks
        )
        updated = replace(task, status="cancelled", subtasks=cancelled_subtasks, completed_at=_now_iso())
        self._tasks[task_id] = updated
        logger.info("Task cancelled: %s", task_id)
        return updated

    def get_task(self, task_id: str) -> Optional[AutonomousTask]:
        return self._tasks.get(task_id)

    def get_active(self) -> list[AutonomousTask]:
        return [t for t in self._tasks.values() if t.status in ("pending", "planning", "executing")]

    def get_all(self, limit: int = 50) -> list[AutonomousTask]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for t in self._tasks.values():
            by_status[t.status] = by_status.get(t.status, 0) + 1
        return {
            "total_tasks": len(self._tasks),
            "active": len(self.get_active()),
            "by_status": by_status,
        }

    # ── Main Execution Pipeline ──────────────────────────────────

    async def _run_task(self, task_id: str) -> None:
        """Main loop: decompose → execute → finalize."""
        try:
            # Phase 1: Plan
            task = self._tasks[task_id]
            task = replace(task, status="planning", started_at=_now_iso())
            self._tasks[task_id] = task
            await self._publish(task, None, "task_started")

            plan = await self._decompose(task)
            task = replace(task, status="executing", plan=plan, subtasks=plan.subtasks)
            self._tasks[task_id] = task
            await self._publish(task, None, "plan_ready")

            # Phase 2: Execute subtasks in dependency order
            batches = self._resolve_order(task.subtasks)
            for batch in batches:
                results = await asyncio.gather(
                    *[self._execute_with_retry(task, s) for s in batch],
                    return_exceptions=True,
                )

                # Update subtask states (immutable rebuild — pre-filter avoids BaseException narrowing issue)
                new_subtasks = list(task.subtasks)
                succeeded = [r for r in results if not isinstance(r, BaseException)]
                for completed in succeeded:
                    new_subtasks = [completed if s.id == completed.id else s for s in new_subtasks]

                # Skip dependents of failed subtasks
                failed_ids = {s.id for s in new_subtasks if s.status == "failed"}
                new_subtasks = [
                    replace(s, status="skipped", error="Dependency failed")
                    if s.status == "pending" and set(s.depends_on) & failed_ids
                    else s
                    for s in new_subtasks
                ]

                task = replace(task, subtasks=tuple(new_subtasks))
                self._tasks[task_id] = task

            # Phase 3: Finalize
            task = await self._finalize(task)
            self._tasks[task_id] = task
            await self._publish(task, None, "task_complete")

        except asyncio.CancelledError:
            logger.info("Task %s was cancelled", task_id)
        except Exception as exc:
            logger.error("Task %s failed: %s", task_id, exc)
            task = self._tasks.get(task_id)
            if task:
                task = replace(task, status="failed", final_result=f"Error: {exc}", completed_at=_now_iso())
                self._tasks[task_id] = task
        finally:
            self._async_tasks.pop(task_id, None)
            self._prune_terminal_tasks()

    def _prune_terminal_tasks(self, keep: int = 200) -> None:
        """Remove oldest terminal tasks to prevent unbounded growth."""
        terminal = [t for t in self._tasks.values() if t.status in ("completed", "failed", "cancelled")]
        if len(terminal) > keep:
            terminal.sort(key=lambda t: t.created_at)
            count_to_remove = len(terminal) - keep
            for old in [terminal[i] for i in range(count_to_remove)]:
                self._tasks.pop(old.id, None)

    # ── Decomposition ────────────────────────────────────────────

    async def _decompose(self, task: AutonomousTask) -> TaskPlan:
        """Use LLM to break a goal into subtasks."""
        if not self._llm:
            # No LLM: single subtask fallback
            return TaskPlan(
                subtasks=(SubtaskState(
                    id=f"sub_{uuid.uuid4().hex[:8]}",
                    index=0,
                    description=task.goal,
                    agent_id="researcher",
                ),),
                reasoning="No LLM available — routing entire goal to researcher",
            )

        # Build context for LLM
        agents_info = ""
        if self._registry:
            agents = self._registry.list_agents()
            agents_info = "\n".join(
                f"- {a.id}: {a.name} — {a.description}" for a in agents
            )

        tools_info = ""
        if self._plugins:
            tool_names = [t["name"] for t in self._plugins.list_tools()]
            tools_info = ", ".join(tool_names[:30])

        prompt = (
            f"Decompose this goal into 1-{self.MAX_SUBTASKS} ordered subtasks.\n\n"
            f"GOAL: {task.goal}\n\n"
            f"AVAILABLE AGENTS:\n{agents_info}\n\n"
            f"AVAILABLE TOOLS: {tools_info}\n\n"
            "Return ONLY valid JSON (no markdown):\n"
            '{"subtasks": [{"description": "...", "agent_id": "...", '
            '"tools_hint": ["tool1"], "depends_on": [], '
            '"risk_level": "low|medium|high|critical"}], '
            '"reasoning": "...", "estimated_duration_seconds": 120}'
        )

        try:
            response = await self._llm.complete(
                system=(
                    "You are a task decomposition engine. Break goals into concrete, "
                    "actionable subtasks. Assign the best agent for each subtask. "
                    "Use depends_on with subtask indices (0-based) for ordering. "
                    "Keep subtasks specific and executable."
                ),
                messages=[{"role": "user", "content": prompt}],
                model_tier="default",
                max_tokens=1500,
            )

            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            data = json.loads(raw)
            # Handle Ollama returning a bare list instead of {"subtasks": [...]}
            if isinstance(data, list):
                data = {"subtasks": data}
            subtask_dicts = data.get("subtasks", [])[:self.MAX_SUBTASKS]

            subtasks: list[SubtaskState] = []
            for i, sd in enumerate(subtask_dicts):
                deps = sd.get("depends_on", [])
                dep_ids = tuple(
                    f"sub_{j}" for j in deps
                    if isinstance(j, int) and 0 <= j < len(subtask_dicts)
                )
                subtasks.append(SubtaskState(
                    id=f"sub_{i}",
                    index=i,
                    description=str(sd.get("description", "")),
                    agent_id=str(sd.get("agent_id", "researcher")),
                    tools_hint=tuple(sd.get("tools_hint", [])),
                    depends_on=dep_ids,
                    risk_level=str(sd.get("risk_level", "low")),
                ))

            return TaskPlan(
                subtasks=tuple(subtasks),
                reasoning=str(data.get("reasoning", "")),
                estimated_duration_seconds=int(data.get("estimated_duration_seconds", 120)),
            )

        except Exception as exc:
            logger.warning("Decomposition parse failed: %s — using single-task fallback", exc)
            return TaskPlan(
                subtasks=(SubtaskState(
                    id="sub_0",
                    index=0,
                    description=task.goal,
                    agent_id="researcher",
                ),),
                reasoning=f"Decomposition failed ({exc}), routing to researcher",
            )

    # ── Subtask Execution ────────────────────────────────────────

    async def _execute_with_retry(self, task: AutonomousTask, subtask: SubtaskState) -> SubtaskState:
        """Execute a subtask with retry on failure."""
        result = await self._execute_subtask(task, subtask)

        retries = 0
        while result.status == "failed" and retries < self.MAX_RETRIES:
            retries += 1
            logger.info("Retrying subtask %s (attempt %d): %s", result.id, retries, result.error)
            result = await self._retry_subtask(task, result)

        return result

    async def _execute_subtask(self, task: AutonomousTask, subtask: SubtaskState) -> SubtaskState:
        """Execute a single subtask through agent collaboration."""
        running = replace(subtask, status="running", started_at=_now_iso())
        await self._publish(task, running, "subtask_started")

        # Check approval for high-risk subtasks
        if self._approval and subtask.risk_level in ("high", "critical"):
            from backend.core.approval_chain import RiskLevel
            risk_map = {"high": RiskLevel.HIGH, "critical": RiskLevel.CRITICAL}
            approval_req = await self._approval.request_approval(
                agent_id="task_executor",
                action="execute_subtask",
                description=f"[{subtask.agent_id}] {subtask.description[:200]}",
                risk_override=risk_map.get(subtask.risk_level),
            )
            if approval_req.status.value == "rejected":
                return replace(running, status="failed", error="Approval rejected",
                               completed_at=_now_iso())

        # Build context from completed sibling subtasks
        context_parts = []
        for s in task.subtasks:
            if s.status == "completed" and s.result and s.id in subtask.depends_on:
                context_parts.append(f"[{s.agent_id}]: {s.result[:1500]}")
        context_str = "\n".join(context_parts)

        enriched_task = subtask.description
        if context_str:
            enriched_task = f"{subtask.description}\n\nContext from previous steps:\n{context_str}"

        try:
            if self._collab:
                wf = await asyncio.wait_for(
                    self._collab.delegate(
                        from_agent="task_executor",
                        to_agent=subtask.agent_id,
                        task=enriched_task,
                    ),
                    timeout=self.DEFAULT_TIMEOUT,
                )
                result_text = wf.final_result or ""
                success = wf.status.value == "completed" and len(result_text) > 5
            else:
                result_text = f"[No collaboration engine] Would delegate to {subtask.agent_id}: {subtask.description}"
                success = True

            if success:
                completed = replace(running, status="completed", result=result_text[:5000],
                                    attempt=subtask.attempt, completed_at=_now_iso())
                await self._publish(task, completed, "subtask_completed")

                # Record to learning engine
                if self._learning:
                    try:
                        self._learning.record_agent_outcome(
                            agent_id=subtask.agent_id,
                            task_description=subtask.description[:200],
                            task_category="autonomous_task",
                            status="completed",
                        )
                    except Exception as exc:
                        logger.warning("Failed to record learning for subtask %s: %s", subtask.id, exc)

                return completed
            else:
                failed = replace(running, status="failed", error=result_text[:500] or "Empty result",
                                 attempt=subtask.attempt, completed_at=_now_iso())
                await self._publish(task, failed, "subtask_failed")
                return failed

        except asyncio.TimeoutError:
            return replace(running, status="failed", error=f"Timeout after {self.DEFAULT_TIMEOUT}s",
                           attempt=subtask.attempt, completed_at=_now_iso())
        except Exception as exc:
            return replace(running, status="failed", error=str(exc)[:500],
                           attempt=subtask.attempt, completed_at=_now_iso())

    async def _retry_subtask(self, task: AutonomousTask, failed: SubtaskState) -> SubtaskState:
        """Use LLM to propose an alternative approach and retry."""
        new_description = failed.description
        new_agent = failed.agent_id

        if self._llm:
            try:
                response = await self._llm.complete(
                    system="You fix failed task steps. Suggest a revised approach.",
                    messages=[{"role": "user", "content": (
                        f"This subtask failed:\n"
                        f"Description: {failed.description}\n"
                        f"Agent: {failed.agent_id}\n"
                        f"Error: {failed.error}\n\n"
                        f"Suggest a revised description and optionally a different agent. "
                        f"Return JSON: {{\"description\": \"...\", \"agent_id\": \"...\"}}"
                    )}],
                    model_tier="fast",
                    max_tokens=300,
                )
                raw = response.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                fix = json.loads(raw)
                new_description = str(fix.get("description", failed.description))
                new_agent = str(fix.get("agent_id", failed.agent_id))
            except Exception as exc:
                logger.warning("Failed to parse LLM retry suggestion: %s", exc)

        retry = replace(
            failed,
            status="pending",
            description=new_description,
            agent_id=new_agent,
            result=None,
            error=None,
            attempt=failed.attempt + 1,
            started_at=None,
            completed_at=None,
        )
        return await self._execute_subtask(task, retry)

    # ── Dependency Resolution ────────────────────────────────────

    def _resolve_order(self, subtasks: tuple[SubtaskState, ...]) -> list[list[SubtaskState]]:
        """Topological sort into execution batches."""
        if not subtasks:
            return []

        remaining = {s.id: s for s in subtasks}
        completed: set[str] = set()
        batches: list[list[SubtaskState]] = []

        max_iterations = len(subtasks) + 1
        for _ in range(max_iterations):
            if not remaining:
                break
            batch = [
                s for s in remaining.values()
                if all(dep in completed for dep in s.depends_on)
            ]
            if not batch:
                # Circular dependency — force remaining into one batch
                batch = list(remaining.values())
            batches.append(batch)
            for s in batch:
                completed.add(s.id)
                remaining.pop(s.id, None)

        return batches

    # ── Finalization ─────────────────────────────────────────────

    async def _finalize(self, task: AutonomousTask) -> AutonomousTask:
        """Synthesize results and store learnings."""
        completed_subtasks = [s for s in task.subtasks if s.status == "completed"]
        failed_subtasks = [s for s in task.subtasks if s.status == "failed"]

        # Synthesize final result
        if completed_subtasks and self._llm:
            results_text = "\n\n".join(
                f"Step {s.index + 1} ({s.agent_id}): {s.result[:1500]}"
                for s in completed_subtasks
            )
            try:
                synthesis = await self._llm.complete(
                    system="Synthesize the results of multiple subtasks into a clear final answer.",
                    messages=[{"role": "user", "content": (
                        f"Goal: {task.goal}\n\n"
                        f"Completed steps:\n{results_text}\n\n"
                        f"Failed steps: {len(failed_subtasks)}\n\n"
                        f"Provide a concise synthesis of what was accomplished."
                    )}],
                    model_tier="fast",
                    max_tokens=1000,
                )
                final_result = synthesis.strip()
            except Exception as exc:
                logger.warning("LLM synthesis failed for task %s: %s", task.id, exc)
                final_result = results_text[:3000]
        elif completed_subtasks:
            final_result = "\n".join(f"[{s.agent_id}] {s.result[:500]}" for s in completed_subtasks)
        else:
            final_result = "No subtasks completed successfully."

        overall_status = "completed" if completed_subtasks else "failed"

        # Store in memory
        if self._memory and completed_subtasks:
            from backend.models.memory import MemoryEntry, MemoryType
            self._memory.store(MemoryEntry(
                content=f"Autonomous task: {task.goal[:200]} — {final_result[:300]}",
                memory_type=MemoryType.LEARNING,
                tags=["autonomous_task", "task_executor"],
                source="task_executor",
                confidence=0.8,
            ))

        return replace(
            task,
            status=overall_status,
            final_result=final_result[:5000],
            completed_at=_now_iso(),
        )

    # ── Bus Publishing ───────────────────────────────────────────

    async def _publish(self, task: AutonomousTask, subtask: Optional[SubtaskState], event: str) -> None:
        """Publish progress event to message bus."""
        if not self._bus:
            return
        try:
            payload: dict[str, Any] = {
                "event": event,
                "task_id": task.id,
                "goal": task.goal[:200],
                "status": task.status,
            }
            if subtask:
                payload["subtask_id"] = subtask.id
                payload["subtask_status"] = subtask.status
                payload["agent_id"] = subtask.agent_id

            msg = self._bus.create_message(
                topic=f"task.{task.id}.{event}",
                sender="task_executor",
                payload=payload,
            )
            await self._bus.publish(msg)
        except Exception as exc:
            logger.debug("Failed to publish bus event '%s' for task %s: %s", event, task.id, exc)
