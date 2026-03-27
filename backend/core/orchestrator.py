"""
Orchestrator — parallel agent task coordination.

From Agent Orchestrator patterns: session management, parallel execution,
reaction handling, state machine lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("root.orchestrator")


class TaskStatus(str, Enum):
    PENDING = "pending"
    SPAWNING = "spawning"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    CRITICAL = 1
    HIGH = 3
    NORMAL = 5
    LOW = 7
    BACKGROUND = 9


@dataclass(frozen=True)
class OrchestratedTask:
    """Immutable task in the orchestration pipeline."""
    id: str
    description: str
    agent_id: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    parent_id: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrchestrationResult:
    """Immutable result of an orchestrated workflow."""
    workflow_id: str
    tasks: list[OrchestratedTask]
    total_duration_seconds: float
    success_count: int
    failure_count: int


class Orchestrator:
    """Manages parallel agent task execution with lifecycle tracking."""

    MAX_CONCURRENT = 3  # From HERMES pattern
    DEFAULT_TIMEOUT = 300  # 5 minutes per task — matches httpx read timeout

    def __init__(self, registry=None) -> None:
        self._registry = registry
        self._tasks: dict[str, OrchestratedTask] = {}
        self._history: list[OrchestrationResult] = []

    async def execute_parallel(
        self,
        subtasks: list[dict[str, Any]],
        parent_id: Optional[str] = None,
    ) -> OrchestrationResult:
        """Execute multiple agent tasks in parallel (max MAX_CONCURRENT).

        Each subtask dict: {"agent_id": "...", "task": "...", "priority": 5}
        """
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now(timezone.utc)

        # Create task objects
        tasks = []
        for st in subtasks:
            metadata = dict(st.get("metadata", {}))
            if "timeout" in st:
                metadata["timeout"] = st["timeout"]
            task = OrchestratedTask(
                id=f"task_{uuid.uuid4().hex[:12]}",
                description=st.get("task", ""),
                agent_id=st.get("agent_id", "unknown"),
                priority=TaskPriority(st.get("priority", 5)),
                parent_id=parent_id,
                metadata=metadata,
            )
            tasks.append(task)
            self._tasks[task.id] = task

        # Execute with semaphore
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        results = await asyncio.gather(
            *[self._execute_task(task, semaphore) for task in tasks],
            return_exceptions=True,
        )

        # Collect results
        completed_tasks = []
        for i, result in enumerate(results):
            task = tasks[i]
            if isinstance(result, Exception):
                updated = OrchestratedTask(
                    id=task.id,
                    description=task.description,
                    agent_id=task.agent_id,
                    priority=task.priority,
                    status=TaskStatus.FAILED,
                    parent_id=task.parent_id,
                    error=str(result),
                    created_at=task.created_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    metadata=task.metadata,
                )
            else:
                updated = result
            completed_tasks.append(updated)
            self._tasks[task.id] = updated

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        orch_result = OrchestrationResult(
            workflow_id=workflow_id,
            tasks=completed_tasks,
            total_duration_seconds=round(duration, 2),
            success_count=sum(1 for t in completed_tasks if t.status == TaskStatus.COMPLETED),
            failure_count=sum(1 for t in completed_tasks if t.status == TaskStatus.FAILED),
        )
        self._history.append(orch_result)
        # Bound history to last 100 results
        if len(self._history) > 100:
            self._history = self._history[-100:]
        return orch_result

    async def _execute_task(
        self, task: OrchestratedTask, semaphore: asyncio.Semaphore
    ) -> OrchestratedTask:
        """Execute a single task within the semaphore, with timeout."""
        async with semaphore:
            started = datetime.now(timezone.utc).isoformat()
            working_task = OrchestratedTask(
                id=task.id,
                description=task.description,
                agent_id=task.agent_id,
                priority=task.priority,
                status=TaskStatus.WORKING,
                parent_id=task.parent_id,
                created_at=task.created_at,
                started_at=started,
                metadata=task.metadata,
            )
            self._tasks[task.id] = working_task

            result_text = ""
            error_text = None
            status = TaskStatus.COMPLETED
            timeout = task.metadata.get("timeout", self.DEFAULT_TIMEOUT)

            if self._registry:
                connector = self._registry.get_connector(task.agent_id)
                if connector:
                    try:
                        coro = self._call_connector(connector, task.description)
                        result = await asyncio.wait_for(coro, timeout=timeout)

                        if isinstance(result, dict):
                            if result.get("error"):
                                status = TaskStatus.FAILED
                                error_text = result["error"]
                            else:
                                raw = result.get("result") or result.get("output") or str(result)
                                result_text = str(raw)[:5000]
                        else:
                            result_text = str(result)[:5000]
                    except asyncio.TimeoutError:
                        status = TaskStatus.FAILED
                        error_text = f"Task timed out after {timeout}s"
                        logger.warning("Task %s timed out for agent %s", task.id, task.agent_id)
                    except Exception as e:
                        status = TaskStatus.FAILED
                        error_text = str(e)
                else:
                    status = TaskStatus.FAILED
                    error_text = f"No connector for agent {task.agent_id}"
            else:
                result_text = f"[Simulated] Task '{task.description}' for agent {task.agent_id}"

            return OrchestratedTask(
                id=task.id,
                description=task.description,
                agent_id=task.agent_id,
                priority=task.priority,
                status=status,
                parent_id=task.parent_id,
                result=result_text,
                error=error_text,
                created_at=task.created_at,
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
                metadata=task.metadata,
            )

    async def _call_connector(self, connector: Any, description: str) -> Any:
        """Call the appropriate method on an agent connector."""
        if hasattr(connector, "send_task"):
            return await connector.send_task(description)
        if hasattr(connector, "delegate_task"):
            return await connector.delegate_task(description)
        return {"error": f"Connector {type(connector).__name__} has no send_task or delegate_task method"}

    def get_task(self, task_id: str) -> Optional[OrchestratedTask]:
        return self._tasks.get(task_id)

    def get_active_tasks(self) -> list[OrchestratedTask]:
        return [t for t in self._tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.WORKING, TaskStatus.SPAWNING)]

    def get_history(self, limit: int = 20) -> list[OrchestrationResult]:
        return list(reversed(self._history[-limit:]))

    def stats(self) -> dict:
        return {
            "total_tasks": len(self._tasks),
            "active": len(self.get_active_tasks()),
            "workflows_completed": len(self._history),
            "total_success": sum(r.success_count for r in self._history),
            "total_failures": sum(r.failure_count for r in self._history),
        }
