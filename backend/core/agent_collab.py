"""
Agent Collaboration Protocol — structured agent-to-agent delegation.

From HERMES delegation + Agent Orchestrator patterns:
- Any agent can request help from another agent
- Workflows chain multiple agents in sequence or parallel
- Results flow back through the collaboration graph
- All communication goes through the message bus

Collaboration Patterns:
1. DELEGATE      — Agent A asks Agent B to do something, waits for result
2. PIPELINE      — Chain: A → B → C → result (each transforms output)
3. FANOUT        — A sends same task to B, C, D in parallel, merges results
4. COUNCIL       — Multiple agents discuss/vote on a decision
5. LOOP          — A ↔ B iterate until convergence
6. CONDITIONAL   — Evaluator classifies task, routes to branch agent
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("root.collab")


class CollabPattern(str, Enum):
    DELEGATE = "delegate"        # A → B (single handoff)
    PIPELINE = "pipeline"        # A → B → C (chain)
    FANOUT = "fanout"            # A → [B, C, D] (parallel)
    COUNCIL = "council"          # [A, B, C] → consensus
    LOOP = "loop"                # A ↔ B (iterative refinement)
    CONDITIONAL = "conditional"  # evaluator → branch agent


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class CollabStep:
    """One step in a collaboration workflow."""
    agent_id: str
    task: str
    result: Optional[str] = None
    status: str = "pending"
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class CollabWorkflow:
    """Immutable collaboration workflow."""
    id: str
    pattern: CollabPattern
    initiator: str
    goal: str
    steps: tuple[CollabStep, ...] = ()
    status: WorkflowStatus = WorkflowStatus.PENDING
    final_result: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None


@dataclass(frozen=True)
class LoopResult:
    """Result of an iterative loop collaboration between two agents."""
    task: str
    iterations: int
    final_result: str
    converged: bool
    history: tuple  # tuple of iteration results


@dataclass(frozen=True)
class ConditionalResult:
    """Result of a conditional routing collaboration."""
    task: str
    classification: str
    selected_agent: str
    result: str


# Circuit breaker constants
_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_OPEN_DURATION_SECONDS = 300  # 5 minutes


class AgentCollaboration:
    """Manages multi-agent collaboration workflows.

    Uses the orchestrator for actual task execution and the message bus
    for inter-agent communication. Integrates VerificationProtocol for
    redundancy detection and multi-agent consensus.
    """

    def __init__(self, orchestrator=None, bus=None, registry=None, network=None,
                 verification=None) -> None:
        self._orchestrator = orchestrator
        self._bus = bus
        self._registry = registry
        self._network = network  # AgentNetwork for inter-agent knowledge sharing
        self._verification = verification  # VerificationProtocol for consensus
        self._sandbox_gate = None  # Set via main.py
        self._workflows: dict[str, CollabWorkflow] = {}
        self._history: list[CollabWorkflow] = []
        # Circuit breaker: {agent_id: {"failures": int, "last_failure": float|None, "open_until": float|None}}
        self._circuit_state: dict[str, dict] = {}

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        context: Optional[dict] = None,
        timeout_seconds: float = 120,
    ) -> CollabWorkflow:
        """Simple delegation: one agent asks another to do something."""
        wf_id = f"collab_{uuid.uuid4().hex[:10]}"

        # Circuit breaker check
        if not self._check_circuit(to_agent):
            failed_step = CollabStep(
                agent_id=to_agent, task=task,
                result=f"Circuit open for {to_agent} — agent temporarily unavailable",
                status="failed",
            )
            failed_wf = CollabWorkflow(
                id=wf_id, pattern=CollabPattern.DELEGATE,
                initiator=from_agent, goal=task,
                steps=(failed_step,), status=WorkflowStatus.FAILED,
                final_result=failed_step.result,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            self._workflows[wf_id] = failed_wf
            self._history = [*self._history[-199:], failed_wf]
            return failed_wf

        workflow = CollabWorkflow(
            id=wf_id,
            pattern=CollabPattern.DELEGATE,
            initiator=from_agent,
            goal=task,
            steps=(CollabStep(agent_id=to_agent, task=task),),
            status=WorkflowStatus.RUNNING,
        )
        self._workflows[wf_id] = workflow

        # Notify via bus
        if self._bus:
            msg = self._bus.create_message(
                topic=f"agent.{to_agent}.task",
                sender=from_agent,
                payload={"workflow_id": wf_id, "task": task, "context": context or {}},
                correlation_id=wf_id,
            )
            await self._bus.publish(msg)

        # Execute via orchestrator with timeout
        try:
            result = await asyncio.wait_for(
                self._execute_single(to_agent, task),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            self._record_failure(to_agent)
            result = {"error": f"Timeout after {timeout_seconds}s for agent {to_agent}"}

        has_error = bool(result.get("error"))
        if has_error:
            self._record_failure(to_agent)
        else:
            self._record_success(to_agent)

        completed_step = CollabStep(
            agent_id=to_agent,
            task=task,
            result=result.get("result", str(result))[:5000],
            status="completed" if not has_error else "failed",
        )

        completed = CollabWorkflow(
            id=wf_id,
            pattern=CollabPattern.DELEGATE,
            initiator=from_agent,
            goal=task,
            steps=(completed_step,),
            status=WorkflowStatus.COMPLETED if not has_error else WorkflowStatus.FAILED,
            final_result=completed_step.result,
            created_at=workflow.created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._workflows[wf_id] = completed
        self._history = [*self._history[-199:], completed]

        # Notify completion
        if self._bus:
            msg = self._bus.create_message(
                topic=f"agent.{from_agent}.result",
                sender=to_agent,
                payload={
                    "workflow_id": wf_id,
                    "result": completed_step.result,
                    "status": completed_step.status,
                },
                correlation_id=wf_id,
            )
            await self._bus.publish(msg)

        return completed

    async def pipeline(
        self,
        initiator: str,
        goal: str,
        steps: list[dict[str, str]],
        timeout_seconds: float = 120,
    ) -> CollabWorkflow:
        """Chain: each agent's output becomes the next agent's input.

        steps: [{"agent_id": "researcher", "task": "find X"},
                {"agent_id": "analyst", "task": "analyze {prev_result}"},
                {"agent_id": "writer", "task": "summarize {prev_result}"}]
        """
        wf_id = f"pipe_{uuid.uuid4().hex[:10]}"

        step_objs = tuple(
            CollabStep(agent_id=s["agent_id"], task=s["task"]) for s in steps
        )

        workflow = CollabWorkflow(
            id=wf_id,
            pattern=CollabPattern.PIPELINE,
            initiator=initiator,
            goal=goal,
            steps=step_objs,
            status=WorkflowStatus.RUNNING,
        )
        self._workflows[wf_id] = workflow

        completed_steps: list[CollabStep] = []
        prev_result = ""
        final_status = WorkflowStatus.COMPLETED

        for step_def in steps:
            agent_id = step_def["agent_id"]
            task = step_def["task"]

            # Inject previous result
            if prev_result and "{prev_result}" in task:
                task = task.replace("{prev_result}", prev_result[:2000])
            elif prev_result:
                task = f"{task}\n\nContext from previous step:\n{prev_result[:2000]}"

            try:
                result = await asyncio.wait_for(
                    self._execute_single(agent_id, task),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                self._record_failure(agent_id)
                result = {"error": f"Timeout after {timeout_seconds}s for agent {agent_id}"}

            result_text = result.get("result", str(result))[:5000]
            failed = bool(result.get("error"))

            if failed:
                self._record_failure(agent_id)
            else:
                self._record_success(agent_id)

            completed_steps.append(CollabStep(
                agent_id=agent_id,
                task=task,
                result=result_text,
                status="failed" if failed else "completed",
            ))

            if failed:
                final_status = WorkflowStatus.FAILED
                break

            prev_result = result_text

        completed = CollabWorkflow(
            id=wf_id,
            pattern=CollabPattern.PIPELINE,
            initiator=initiator,
            goal=goal,
            steps=tuple(completed_steps),
            status=final_status,
            final_result=prev_result[:5000] if prev_result else None,
            created_at=workflow.created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._workflows[wf_id] = completed
        self._history = [*self._history[-199:], completed]
        return completed

    async def fanout(
        self,
        initiator: str,
        goal: str,
        agents: list[str],
        task: str,
        merge_prompt: Optional[str] = None,
        timeout_seconds: float = 120,
    ) -> CollabWorkflow:
        """Parallel: send same task to multiple agents, merge results.

        If merge_prompt is given, a final synthesis step combines all outputs.
        """
        wf_id = f"fan_{uuid.uuid4().hex[:10]}"

        step_objs = tuple(CollabStep(agent_id=a, task=task) for a in agents)

        workflow = CollabWorkflow(
            id=wf_id,
            pattern=CollabPattern.FANOUT,
            initiator=initiator,
            goal=goal,
            steps=step_objs,
            status=WorkflowStatus.RUNNING,
        )
        self._workflows[wf_id] = workflow

        # Run in parallel via orchestrator
        subtasks = [{"agent_id": a, "task": task, "priority": 5} for a in agents]
        orch_result = await self._orchestrator.execute_parallel(subtasks)

        completed_steps: list[CollabStep] = []
        results_for_merge: list[str] = []

        for orch_task in orch_result.tasks:
            result_text = orch_task.result or orch_task.error or "no output"
            completed_steps.append(CollabStep(
                agent_id=orch_task.agent_id,
                task=task,
                result=result_text[:3000],
                status=orch_task.status.value,
            ))
            if orch_task.result:
                results_for_merge.append(
                    f"**{orch_task.agent_id}**:\n{orch_task.result[:2000]}"
                )

        # Optional merge step
        final_result = "\n\n---\n\n".join(results_for_merge)
        if merge_prompt and results_for_merge:
            merge_task = (
                f"{merge_prompt}\n\n"
                f"Agent outputs to synthesize:\n\n{final_result[:4000]}"
            )
            merge_result = await self._execute_single("root", merge_task)
            final_result = merge_result.get("result", final_result)[:5000]

        completed = CollabWorkflow(
            id=wf_id,
            pattern=CollabPattern.FANOUT,
            initiator=initiator,
            goal=goal,
            steps=tuple(completed_steps),
            status=WorkflowStatus.COMPLETED if orch_result.success_count > 0 else WorkflowStatus.FAILED,
            final_result=final_result[:5000],
            created_at=workflow.created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._workflows[wf_id] = completed
        self._history = [*self._history[-199:], completed]
        return completed

    async def council(
        self,
        initiator: str,
        question: str,
        agents: list[str],
        synthesizer: str = "root",
    ) -> CollabWorkflow:
        """Council: multiple agents give opinions, synthesizer merges into decision."""
        return await self.fanout(
            initiator=initiator,
            goal=f"Council decision: {question}",
            agents=agents,
            task=(
                f"You are participating in a council discussion. "
                f"Give your expert opinion on this question:\n\n{question}\n\n"
                f"Provide your analysis, recommendation, and confidence level."
            ),
            merge_prompt=(
                f"You are the council synthesizer. Multiple agents have weighed in on: "
                f"{question}\n\n"
                f"Synthesize their perspectives into a clear recommendation. "
                f"Note areas of agreement and disagreement. "
                f"Provide a final decision with reasoning."
            ),
        )

    # ── Loop Pattern ──────────────────────────────────────────────

    async def loop(
        self,
        task: str,
        agent_a: str,
        agent_b: str,
        max_iterations: int = 3,
        convergence_threshold: float = 0.9,
    ) -> LoopResult:
        """Iterative refinement: agent_a produces, agent_b reviews, repeat.

        Stops when max_iterations reached or consecutive results are
        similar enough (SequenceMatcher ratio >= convergence_threshold).
        """
        iteration_history: list[str] = []
        converged = False

        # Initial production by agent_a
        result_a = await self._execute_single(agent_a, task)
        current_output = result_a.get("result", str(result_a))[:5000]
        iteration_history.append(current_output)

        for iteration in range(max_iterations):
            # agent_b reviews agent_a's output
            review_prompt = (
                f"Review and refine the following output for this task: {task}\n\n"
                f"Current output:\n{current_output[:3000]}\n\n"
                f"Provide an improved version with corrections and enhancements."
            )
            result_b = await self._execute_single(agent_b, review_prompt)
            review_output = result_b.get("result", str(result_b))[:5000]
            iteration_history.append(review_output)

            # Check convergence
            similarity = SequenceMatcher(
                None, current_output, review_output,
            ).ratio()
            if similarity >= convergence_threshold:
                converged = True
                current_output = review_output
                break

            # agent_a refines based on agent_b's feedback
            if iteration < max_iterations - 1:
                refine_prompt = (
                    f"Refine your output for this task: {task}\n\n"
                    f"Feedback from reviewer:\n{review_output[:3000]}\n\n"
                    f"Produce an improved version incorporating the feedback."
                )
                result_a = await self._execute_single(agent_a, refine_prompt)
                current_output = result_a.get("result", str(result_a))[:5000]
                iteration_history.append(current_output)

                # Check convergence between refined and review
                similarity = SequenceMatcher(
                    None, review_output, current_output,
                ).ratio()
                if similarity >= convergence_threshold:
                    converged = True
                    break
            else:
                current_output = review_output

        loop_result = LoopResult(
            task=task,
            iterations=len(iteration_history),
            final_result=current_output,
            converged=converged,
            history=tuple(iteration_history),
        )

        # Track in _history as a workflow
        wf_id = f"loop_{uuid.uuid4().hex[:10]}"
        wf = CollabWorkflow(
            id=wf_id,
            pattern=CollabPattern.LOOP,
            initiator=agent_a,
            goal=task,
            steps=(
                CollabStep(agent_id=agent_a, task=task, result="producer", status="completed"),
                CollabStep(agent_id=agent_b, task=task, result="reviewer", status="completed"),
            ),
            status=WorkflowStatus.COMPLETED,
            final_result=str(current_output)[:5000],
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        self._workflows[wf_id] = wf
        self._history = [*self._history[-199:], wf]

        return loop_result

    # ── Conditional Pattern ──────────────────────────────────────

    async def conditional(
        self,
        task: str,
        evaluator_agent: str,
        branches: dict[str, str],
    ) -> ConditionalResult:
        """Evaluator classifies task, routes to the matching branch agent.

        branches: {"category_name": "agent_id", ...}
        """
        branch_names = ", ".join(branches.keys())
        classify_prompt = (
            f"Classify this task into exactly one of the following categories: "
            f"{branch_names}\n\n"
            f"Task: {task}\n\n"
            f"Respond with ONLY the category name, nothing else."
        )
        eval_result = await self._execute_single(evaluator_agent, classify_prompt)
        classification_raw = eval_result.get("result", str(eval_result))[:200].strip()

        # Match classification to a branch (case-insensitive, partial match)
        selected_branch: str = next(iter(branches))  # default fallback
        selected_agent: str = branches[selected_branch]
        classification_lower = classification_raw.lower()
        for branch_name, branch_agent_id in branches.items():
            if branch_name.lower() in classification_lower or classification_lower in branch_name.lower():
                selected_branch = branch_name
                selected_agent = branch_agent_id
                break
        else:
            logger.warning(
                "Classification '%s' did not match any branch, defaulting to '%s'",
                classification_raw, selected_branch,
            )

        # Execute via selected branch agent
        branch_result = await self._execute_single(selected_agent, task)
        result_text: str = branch_result.get("result", str(branch_result))[:5000]

        cond_result = ConditionalResult(
            task=task,
            classification=selected_branch,
            selected_agent=selected_agent,
            result=result_text,
        )

        # Track in _history
        wf_id = f"cond_{uuid.uuid4().hex[:10]}"
        result_preview: str = result_text[:3000]
        final_preview: str = result_text[:5000]
        wf = CollabWorkflow(
            id=wf_id,
            pattern=CollabPattern.CONDITIONAL,
            initiator=evaluator_agent,
            goal=task,
            steps=(
                CollabStep(
                    agent_id=evaluator_agent, task=classify_prompt,
                    result=selected_branch, status="completed",
                ),
                CollabStep(
                    agent_id=selected_agent, task=task,
                    result=result_preview, status="completed",
                ),
            ),
            status=WorkflowStatus.COMPLETED,
            final_result=final_preview,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        self._workflows[wf_id] = wf
        self._history = [*self._history[-199:], wf]

        return cond_result

    # ── Circuit Breaker ──────────────────────────────────────────

    def _check_circuit(self, agent_id: str) -> bool:
        """Return True if agent is available (circuit closed or timeout elapsed)."""
        state = self._circuit_state.get(agent_id)
        if state is None:
            return True

        open_until = state.get("open_until")
        if open_until is None:
            return True

        if time.monotonic() >= open_until:
            # Timeout elapsed — half-open, allow one attempt
            updated = {**state, "open_until": None, "failures": 0}
            self._circuit_state = {**self._circuit_state, agent_id: updated}
            logger.info("Circuit half-open for %s — allowing retry", agent_id)
            return True

        logger.warning("Circuit OPEN for %s — rejecting until %.0fs", agent_id, open_until - time.monotonic())
        return False

    def _record_failure(self, agent_id: str) -> None:
        """Record a failure; open circuit after threshold consecutive failures."""
        current = self._circuit_state.get(agent_id, {
            "failures": 0, "last_failure": None, "open_until": None,
        })
        new_failures = current["failures"] + 1
        now = time.monotonic()

        if new_failures >= _CIRCUIT_FAILURE_THRESHOLD:
            open_until = now + _CIRCUIT_OPEN_DURATION_SECONDS
            logger.warning(
                "Circuit OPENED for %s after %d failures — blocked for %ds",
                agent_id, new_failures, _CIRCUIT_OPEN_DURATION_SECONDS,
            )
        else:
            open_until = current.get("open_until")

        updated = {
            "failures": new_failures,
            "last_failure": now,
            "open_until": open_until,
        }
        self._circuit_state = {**self._circuit_state, agent_id: updated}

    def _record_success(self, agent_id: str) -> None:
        """Reset failure count and close circuit on success."""
        if agent_id in self._circuit_state:
            updated = {"failures": 0, "last_failure": None, "open_until": None}
            self._circuit_state = {**self._circuit_state, agent_id: updated}

    # ── Status & History ──────────────────────────────────────────

    def get_workflow(self, workflow_id: str) -> Optional[CollabWorkflow]:
        return self._workflows.get(workflow_id)

    def get_active(self) -> list[CollabWorkflow]:
        return [w for w in self._workflows.values() if w.status == WorkflowStatus.RUNNING]

    def get_history(self, limit: int = 20) -> list[CollabWorkflow]:
        return list(reversed(self._history[-limit:]))

    def stats(self) -> dict[str, Any]:
        return {
            "total_workflows": len(self._history),
            "active": len(self.get_active()),
            "by_pattern": {
                p.value: sum(1 for w in self._history if w.pattern == p)
                for p in CollabPattern
            },
            "success_rate": (
                sum(1 for w in self._history if w.status == WorkflowStatus.COMPLETED)
                / max(len(self._history), 1)
            ),
        }

    # ── Internal ─────────────────────────────────────────────────

    async def _execute_single(self, agent_id: str, task: str) -> dict[str, Any]:
        """Execute a task on a single agent via its connector.

        Checks for redundancy (same task already dispatched to another agent),
        injects relevant network insights into the task context so agents
        benefit from knowledge shared by other agents.
        """
        if not self._registry:
            return {"error": "No registry available"}

        # Redundancy check — skip if another agent is already doing this
        if self._verification:
            dup = self._verification.check_redundancy(agent_id, task)
            if dup:
                logger.info(
                    "Redundancy detected: %s duplicates %s — reusing",
                    agent_id, dup["original_agent"],
                )
                return {"result": f"[Deferred to {dup['original_agent']} — same task already in progress]"}
            self._verification.register_task(agent_id, task)

        connector = self._registry.get_connector(agent_id)
        if not connector:
            return {"error": f"No connector for {agent_id}"}

        try:
            # Sandbox gate check for external-domain agents
            _EXTERNAL_DOMAINS = frozenset({"trading", "market"})
            if self._sandbox_gate is not None:
                domain = self._agent_to_domain(agent_id)
                if domain in _EXTERNAL_DOMAINS:
                    decision = self._sandbox_gate.check(
                        system_id="agents_external",
                        action=f"agent_execute:{agent_id}",
                        description=f"Agent {agent_id} executing: {task[:100]}",
                        agent_id=agent_id,
                        risk_level="medium",
                    )
                    if not decision.was_executed:
                        return {"result": f"[SANDBOX] Agent {agent_id} action simulated: {task[:200]}"}

            # Enrich task with network intelligence
            enriched_task = task
            if self._network:
                try:
                    network_ctx = self._network.get_network_context(agent_id, max_chars=1500)
                    if network_ctx:
                        enriched_task = f"{task}\n\n{network_ctx}"
                except Exception as exc:
                    logger.debug("Network context injection failed for %s: %s", agent_id, exc)

            if hasattr(connector, "send_task"):
                result = await connector.send_task(enriched_task)
            else:
                return {"error": f"Connector {agent_id} has no send_task method"}

            # Auto-share noteworthy results back to network
            if self._network and result.get("result") and len(str(result["result"])) > 50:
                try:
                    result_text = str(result["result"])[:500]
                    # Determine domain from agent
                    domain = self._agent_to_domain(agent_id)
                    self._network.share_insight(
                        source_agent=agent_id,
                        insight_type="discovery",
                        domain=domain,
                        content=f"Task result: {result_text}",
                        confidence=0.6,
                        ttl_hours=24,
                    )
                except Exception as exc:
                    logger.warning("Failed to share insight for agent %s: %s", agent_id, exc)

            return result
        except Exception as exc:
            logger.error("Collab execution failed for %s: %s", agent_id, exc)
            return {"error": str(exc)}

    @staticmethod
    def _agent_to_domain(agent_id: str) -> str:
        """Map agent to its primary domain."""
        mapping = {
            "swarm": "trading", "miro": "market", "analyst": "market",
            "researcher": "research", "coder": "code", "builder": "code",
            "hermes": "system", "writer": "writing", "guardian": "security",
            "openclaw": "data", "astra": "system", "root": "system",
        }
        return mapping.get(agent_id, "research")
