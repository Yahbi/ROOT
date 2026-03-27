"""
ROOT Brain — the central reasoning engine.

Handles conversations with Yohan, enriches them with memory context,
injects relevant skills, uses plugin tools, triggers reflections,
coordinates agent delegation via ASTRA, and persists conversations.

Flow: User -> ASTRA routes -> Agents dispatched in parallel -> ASTRA synthesizes -> Response
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from backend.core.brain_context import (
    SYSTEM_PROMPT,
    build_ecosystem_context,
    build_experience_context,
    build_prediction_context,
)
from backend.core.brain_routing import BrainRoutingMixin
from backend.core.memory_engine import MemoryEngine
from backend.core.reflection import ReflectionEngine
from backend.models.agent import AgentFinding, ChatMessage
from backend.models.memory import MemoryEntry, MemoryQuery, MemoryType
from backend.agents.registry import AgentRegistry

logger = logging.getLogger("root.brain")


class Brain(BrainRoutingMixin):
    """ROOT's central reasoning engine with ASTRA-supervised agent dispatch."""

    def __init__(
        self,
        llm,
        memory: MemoryEngine,
        reflection: ReflectionEngine,
        router,
        registry: AgentRegistry,
        skills=None,
        plugins=None,
        conversations=None,
        money_engine=None,
        interest_engine=None,
        orchestrator=None,
        learning_engine=None,
        goal_engine=None,
        escalation=None,
        user_patterns=None,
        ecosystem=None,
        prediction_ledger=None,
        experience_memory=None,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._reflection = reflection
        self._router = router
        self._registry = registry
        self._skills = skills
        self._plugins = plugins
        self._conversations = conversations
        self._money = money_engine
        self._interest = interest_engine
        self._orchestrator = orchestrator
        self._learning = learning_engine
        self._goal_engine = goal_engine
        self._escalation = escalation
        self._user_patterns = user_patterns
        self._ecosystem = ecosystem
        self._prediction_ledger = prediction_ledger
        self._experience_memory = experience_memory
        self._directive = None  # DirectiveEngine — set via late-binding
        self._agent_network = None  # AgentNetwork — set via late-binding
        self._offline_brain = None  # OfflineBrain — fallback when LLM is down
        self._proactive = None  # ProactiveEngine — for chat priority signaling
        self._degraded = False  # True when operating in fallback mode
        self._bus = None  # MessageBus — set via set_bus()
        self._conversation: list[dict[str, str]] = []
        self._interaction_count = 0

    def set_bus(self, bus) -> None:
        """Late-bind message bus for publishing agent findings."""
        self._bus = bus

    def _build_routing_agents_desc(self) -> str:
        """Build agent descriptions for ASTRA routing, including top civilization agents per division."""
        core_ids = {"astra", "hermes", "miro", "swarm", "openclaw", "builder",
                    "researcher", "coder", "writer", "analyst", "guardian"}
        agents = self._registry.list_agents()
        lines = [
            f"- {a.id}: {a.name} — {a.role}"
            for a in agents if a.id in core_ids
        ]
        # Include top 2 civilization agents per division (by description relevance)
        divisions = self._registry.list_divisions()
        for div_name in divisions:
            div_agents = self._registry.list_division(div_name)
            for agent in div_agents[:2]:
                lines.append(f"- {agent.id}: {agent.name} — {agent.role} (civilization/{div_name})")
        return "\n".join(lines)

    async def chat(self, user_message: str) -> ChatMessage:
        """Process a message from Yohan via ASTRA-supervised agent dispatch.

        Flow: User -> ASTRA routes -> Agents dispatched -> ASTRA synthesizes -> Response
        """
        self._interaction_count += 1
        start_time = time.monotonic()

        # Signal LLM router + proactive engine to pause background calls
        # User chat gets priority over all background LLM usage (Ollama is single-threaded)
        if hasattr(self._llm, 'chat_started'):
            self._llm.chat_started()
        if self._proactive:
            self._proactive.chat_started()

        try:
            return await self._chat_inner(user_message, start_time)
        finally:
            if hasattr(self._llm, 'chat_finished'):
                self._llm.chat_finished()
            if self._proactive:
                self._proactive.chat_finished()

    async def _chat_inner(self, user_message: str, start_time: float) -> ChatMessage:
        """Inner chat logic, wrapped by chat() for proactive engine priority."""
        # Check for money/strategy triggers
        money_triggers = (
            "make money", "money", "council", "strategy council",
            "opportunities", "how to make money", "revenue",
            "make yohan money", "wealth",
        )
        query_lower = user_message.lower().strip()
        if self._money and (query_lower in money_triggers or "make money" in query_lower):
            session = await self._money.convene_council(focus=user_message)
            response_text = self._format_council_session(session)
            self._conversation.append({"role": "user", "content": user_message})
            self._conversation.append({"role": "assistant", "content": response_text})
            self._persist_messages(user_message, response_text, [])
            return ChatMessage(
                role="assistant", content=response_text, agent_id="root",
                memories_used=[], timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # 0a. Fast path: financial status questions — query internal databases directly
        _financial_status_keywords = (
            "how much money", "how much did we make", "how much have we made",
            "trading results", "trading stats", "portfolio", "p&l", "pnl",
            "profit and loss", "our trades", "our positions", "open positions",
            "trading performance", "hedge fund", "revenue stats", "financial status",
            "how are our trades", "how are the trades", "progress of our trades",
            "did we make money", "are we making money", "show me the money",
            "earnings", "how much profit",
        )
        if any(kw in query_lower for kw in _financial_status_keywords):
            response_text = await self._build_financial_status()
            self._conversation.append({"role": "user", "content": user_message})
            self._conversation.append({"role": "assistant", "content": response_text})
            self._persist_messages(user_message, response_text, [])
            elapsed = round(time.monotonic() - start_time, 2)
            logger.info("Financial status fast path in %.1fs: '%s'", elapsed, user_message[:40])
            return ChatMessage(
                role="assistant", content=response_text, agent_id="root",
                memories_used=[], timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # 0b. Fast path: simple greetings/meta questions bypass ASTRA routing entirely
        _greeting_words = {"hi", "hello", "hey", "howdy", "sup", "yo", "hola",
                           "good morning", "good evening", "good afternoon",
                           "what can you do", "who are you", "what are you",
                           "what is root", "help", "status"}
        _greeting_patterns = ("what can you do", "who are you", "what are you",
                              "how are you", "tell me about yourself",
                              "what is root", "what do you do")
        is_greeting = (query_lower in _greeting_words
                       or len(user_message.split()) <= 3
                       or any(query_lower.startswith(p) for p in _greeting_patterns))
        if is_greeting:
            response_text = await self._llm.complete(
                system="You are ROOT, an AI civilization with 172+ agents. "
                       "Answer briefly and helpfully. Mention your key capabilities: "
                       "research, trading, coding, content, strategy analysis.",
                messages=[{"role": "user", "content": user_message}],
                model_tier="fast", temperature=0.7, max_tokens=300,
            )
            self._conversation.append({"role": "user", "content": user_message})
            self._conversation.append({"role": "assistant", "content": response_text})
            self._persist_messages(user_message, response_text, [])
            elapsed = round(time.monotonic() - start_time, 2)
            logger.info("Fast path greeting in %.1fs: '%s'", elapsed, user_message[:40])
            return ChatMessage(
                role="assistant", content=response_text, agent_id="root",
                memories_used=[], timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # 1. Fast keyword routing — skip ASTRA LLM call for ~70% of requests
        fast_route, fast_subtasks = self._force_delegation_if_needed(user_message)

        if fast_subtasks:
            # Keywords matched — run memory search in parallel (don't wait for ASTRA)
            logger.info("Fast-routed '%s' -> %s (%d subtasks) — skipping ASTRA LLM",
                        user_message[:60], fast_route, len(fast_subtasks))
            memories = await asyncio.to_thread(
                self._memory.search, MemoryQuery(query=user_message, limit=10)
            )
            memory_context = self._format_memories(memories)
            route = fast_route
            subtasks = fast_subtasks
            agent_ids = [st.get("agent_id", "") for st in subtasks]
            route_decision = {"route": route, "agent_ids": agent_ids,
                              "subtasks": subtasks, "reasoning": "fast-routed by keywords"}
        else:
            # No keyword match — run memory search + ASTRA routing in parallel
            astra_conn = self._registry.get_connector("astra")
            route_decision = {"route": "direct", "agent_ids": [], "subtasks": []}

            async def _astra_route():
                if not (astra_conn and hasattr(astra_conn, "route_request")):
                    return {"route": "direct", "agent_ids": [], "subtasks": []}
                agents_desc = self._build_routing_agents_desc()
                return await astra_conn.route_request(user_message, agents_desc)

            try:
                mem_future = asyncio.to_thread(
                    self._memory.search, MemoryQuery(query=user_message, limit=10)
                )
                route_future = _astra_route()
                memories, route_decision = await asyncio.gather(mem_future, route_future)
                self._degraded = False
                logger.info("ASTRA routed '%s' -> %s (agents: %s)",
                            user_message[:80], route_decision.get("route"),
                            route_decision.get("agent_ids", []))
            except Exception as e:
                from backend.services.llm import LLMUnavailableError
                if isinstance(e, LLMUnavailableError) and self._offline_brain:
                    logger.warning("LLM unavailable — falling back to offline brain")
                    self._degraded = True
                    result = self._offline_brain.chat(user_message)
                    self._persist_messages(user_message, result.content, [])
                    return result
                logger.error("ASTRA routing failed: %s — falling back to direct", e)
                memories = self._memory.search(MemoryQuery(query=user_message, limit=10))

            memory_context = self._format_memories(memories)
            route = route_decision.get("route", "direct")
            agent_ids = route_decision.get("agent_ids", [])
            subtasks = route_decision.get("subtasks", [])

        # 3. Dispatch agents if routed to delegate/multi/pipeline
        agent_findings: list[AgentFinding] = []

        if route == "pipeline" and subtasks:
            # Sequential pipeline — each step can depend on previous results
            agent_findings = await self._dispatch_pipeline(subtasks)
        elif route in ("delegate", "multi") and subtasks:
            agent_findings = await self._dispatch_agents(subtasks)
        elif route in ("delegate", "multi") and agent_ids and not subtasks:
            # Agent IDs but no subtasks — create subtasks from the user message
            subtasks = [{"agent_id": aid, "task": user_message} for aid in agent_ids]
            agent_findings = await self._dispatch_agents(subtasks)

        # 4. Auto-spawn exploration agents for new avenues discovered
        if agent_findings and route in ("multi", "pipeline"):
            spawn_findings = await self._spawn_exploration_agents(
                user_message, agent_findings, astra_conn
            )
            if spawn_findings:
                agent_findings.extend(spawn_findings)
                logger.info("Spawned %d exploration agents for new avenues", len(spawn_findings))

        # 5. Build final response
        if agent_findings:
            # Filter to findings with real content (not timeouts/errors)
            _failure_signals = ("LLM request timed out", "No response", "LLM error:",
                                "No connector for", "No output", "No LLM configured")
            completed = [
                f for f in agent_findings
                if f.status == "completed" and f.result
                and not any(f.result.startswith(sig) for sig in _failure_signals)
            ]

            if not completed:
                # ALL agents failed — fall back to direct LLM response
                logger.warning("All %d agents failed — falling back to direct response", len(agent_findings))
                response_text = await self._direct_handle(user_message, memory_context)
            elif len(completed) == 1 and len(agent_findings) <= 2:
                # Single agent — enrich only thin/raw results, pass through substantive ones
                raw = completed[0].result
                if len(raw) < 300 or raw.strip().startswith('{'):
                    response_text = await self._enrich_thin_result(
                        user_message, completed[0], memory_context
                    )
                    logger.info("Single-agent result enriched (%d chars raw)", len(raw))
                else:
                    response_text = raw
                    logger.info("Single-agent result used directly (%d chars)", len(raw))
            else:
                # Multi-agent: ASTRA synthesizes findings (only pass real results)
                findings_dicts = [
                    {
                        "agent_id": f.agent_id,
                        "agent_name": f.agent_name,
                        "task": f.task,
                        "result": f.result,
                        "status": f.status,
                    }
                    for f in completed
                ]
                if astra_conn and hasattr(astra_conn, "synthesize_findings"):
                    try:
                        response_text = await astra_conn.synthesize_findings(
                            user_message, findings_dicts, memory_context
                        )
                        # If synthesis returned empty (all findings filtered or JSON detected), fall back
                        if not response_text or not response_text.strip():
                            logger.warning("ASTRA synthesis returned empty — falling back to direct")
                            response_text = await self._direct_handle(user_message, memory_context)
                    except Exception as e:
                        logger.error("ASTRA synthesis failed: %s", e)
                        response_text = self._fallback_synthesis(user_message, completed)
                else:
                    response_text = self._fallback_synthesis(user_message, completed)
        else:
            # Direct handling — ROOT handles it with tools
            response_text = await self._direct_handle(user_message, memory_context)

        # 5. Add to conversation history
        self._conversation.append({"role": "user", "content": user_message})
        self._conversation.append({"role": "assistant", "content": response_text})

        # 6. Persist
        self._persist_messages(user_message, response_text, memories)

        # 7. Learn from interaction (background — don't block response)
        asyncio.create_task(self._extract_learnings(user_message, response_text))

        # 7b. Track interaction outcome for adaptive learning
        elapsed = round(time.monotonic() - start_time, 2)
        agents_used = [f.agent_id for f in agent_findings]
        total_tools = sum(f.tools_executed for f in agent_findings)
        if self._learning:
            try:
                self._learning.record_interaction(
                    user_message=user_message,
                    route=route,
                    agents_used=agents_used,
                    response_length=len(response_text),
                    agent_findings_count=len(agent_findings),
                    tools_used_count=total_tools,
                    duration_seconds=elapsed,
                )
                # Record individual agent outcomes
                for f in agent_findings:
                    quality = 0.7 if f.status == "success" else 0.3
                    if f.tools_executed > 0:
                        quality += 0.1  # Agents that use tools are doing real work
                    self._learning.record_agent_outcome(
                        agent_id=f.agent_id,
                        task_description=f.task,
                        status=f.status,
                        result_quality=min(1.0, quality),
                        duration_seconds=f.duration_seconds,
                        tools_used=f.tools_executed,
                    )
            except Exception as e:
                logger.error("Learning engine tracking failed: %s", e)

        # 7c. Publish agent findings to message bus
        if self._bus and agent_findings:
            try:
                msg = self._bus.create_message(
                    topic="agent.findings",
                    sender="brain",
                    payload={
                        "query": user_message[:200],
                        "agent_ids": agents_used,
                        "route": route,
                    },
                )
                await self._bus.publish(msg)
            except Exception as e:
                logger.warning("Bus publish agent findings failed: %s", e)

        # 7d. Feed failures into curiosity engine (learn from mistakes)
        curiosity = getattr(self, '_curiosity', None)
        if curiosity:
            failed_agents = [f for f in agent_findings if f.status != "success"]
            if failed_agents:
                for f in failed_agents[:2]:  # Max 2 curiosity items per chat
                    curiosity.add_curiosity(
                        question=f"Agent {f.agent_id} failed task: {f.task[:100]}. How to handle this better?",
                        domain="self_improvement",
                        priority=0.8,
                    )
            elif not response_text or len(response_text) < 50:
                curiosity.add_curiosity(
                    question=f"ROOT couldn't adequately answer: {user_message[:150]}. What knowledge is needed?",
                    domain="general",
                    priority=0.85,
                )

        # 7e. Auto-create goals from substantive intent
        if self._goal_engine and len(user_message) > 30 and route != "direct":
            try:
                await self._maybe_create_goal(user_message, route, agents_used)
            except Exception as e:
                logger.error("Goal auto-creation failed: %s", e)

        # 8. Periodic reflection
        if self._interaction_count % 10 == 0:
            try:
                await self._reflection.reflect(
                    trigger=f"periodic (interaction #{self._interaction_count})"
                )
            except Exception as e:
                logger.error("Reflection failed: %s", e)

        total_msgs = sum(f.messages_exchanged for f in agent_findings)
        reasoning = route_decision.get("reasoning", "")
        logger.info("Chat complete in %.1fs — route=%s, agents=%s, msgs=%d, tools=%d",
                     elapsed, route, agents_used, total_msgs, total_tools)

        return ChatMessage(
            role="assistant",
            content=response_text,
            agent_id="astra" if agent_findings else "root",
            memories_used=[m.id for m in memories if m.id],
            agents_used=agents_used,
            agent_findings=agent_findings,
            route=route,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_messages_exchanged=total_msgs,
            total_tools_executed=total_tools,
            routing_reasoning=reasoning,
        )

    async def chat_stream(self, user_message: str):
        """Stream chat response as SSE events.

        Yields dicts with event type and data as each step completes:
        - {"event": "routing", "data": {...}} — ASTRA routing decision
        - {"event": "agent_start", "data": {"agent_id": ..., "task": ...}}
        - {"event": "agent_result", "data": {"agent_id": ..., "result": ...}}
        - {"event": "token", "data": {"text": ...}} — streaming synthesis tokens
        - {"event": "done", "data": {...}} — final ChatMessage
        """
        self._interaction_count += 1
        start_time = time.monotonic()

        # Signal LLM router + proactive engine to pause background calls
        if hasattr(self._llm, 'chat_started'):
            self._llm.chat_started()
        if self._proactive:
            self._proactive.chat_started()

        try:
            async for event in self._chat_stream_inner(user_message, start_time):
                yield event
        finally:
            if hasattr(self._llm, 'chat_finished'):
                self._llm.chat_finished()
            if self._proactive:
                self._proactive.chat_finished()

    async def _chat_stream_inner(self, user_message: str, start_time: float):
        """Inner stream logic, wrapped by chat_stream() for deadlock prevention."""
        # 1. Fast keyword routing — skip ASTRA LLM call when possible
        fast_route, fast_subtasks = self._force_delegation_if_needed(user_message)

        if fast_subtasks:
            yield {"event": "thinking", "data": {"stage": "fast_routing"}}
            memories = await asyncio.to_thread(
                self._memory.search, MemoryQuery(query=user_message, limit=10)
            )
            memory_context = self._format_memories(memories)
            route = fast_route
            subtasks = fast_subtasks
            agent_ids = [st.get("agent_id", "") for st in subtasks]
            route_decision = {"route": route, "agent_ids": agent_ids,
                              "subtasks": subtasks, "reasoning": "fast-routed by keywords"}
            logger.info("Stream fast-routed '%s' -> %s (%d subtasks)",
                        user_message[:60], route, len(subtasks))
        else:
            yield {"event": "thinking", "data": {"stage": "routing"}}

            astra_conn = self._registry.get_connector("astra")
            route_decision = {"route": "direct", "agent_ids": [], "subtasks": []}

            async def _astra_route_stream():
                if not (astra_conn and hasattr(astra_conn, "route_request")):
                    return {"route": "direct", "agent_ids": [], "subtasks": []}
                agents_desc = self._build_routing_agents_desc()
                return await astra_conn.route_request(user_message, agents_desc)

            try:
                mem_future = asyncio.to_thread(
                    self._memory.search, MemoryQuery(query=user_message, limit=10)
                )
                memories, route_decision = await asyncio.gather(mem_future, _astra_route_stream())
                self._degraded = False
            except Exception as e:
                from backend.services.llm import LLMUnavailableError
                if isinstance(e, LLMUnavailableError) and self._offline_brain:
                    self._degraded = True
                    result = self._offline_brain.chat(user_message)
                    yield {"event": "done", "data": result.model_dump()}
                    return
                logger.error("ASTRA routing failed: %s — falling back to direct", e)
                memories = self._memory.search(MemoryQuery(query=user_message, limit=10))

            memory_context = self._format_memories(memories)
            route = route_decision.get("route", "direct")
            subtasks = route_decision.get("subtasks", [])
            agent_ids = route_decision.get("agent_ids", [])

        yield {"event": "routing", "data": {
            "route": route,
            "agents": agent_ids,
            "subtask_count": len(subtasks),
            "reasoning": route_decision.get("reasoning", ""),
        }}

        # 3. Dispatch agents with per-agent streaming
        agent_findings: list[AgentFinding] = []

        if route in ("delegate", "multi", "pipeline") and subtasks:
            for st in subtasks:
                agent_id = st.get("agent_id", "")
                task_desc = st.get("task", user_message)
                yield {"event": "agent_start", "data": {
                    "agent_id": agent_id, "task": task_desc[:200],
                }}

            # Dispatch all at once (parallel or pipeline)
            if route == "pipeline":
                agent_findings = await self._dispatch_pipeline(subtasks)
            else:
                agent_findings = await self._dispatch_agents(subtasks)

            # Yield each result
            for f in agent_findings:
                yield {"event": "agent_result", "data": {
                    "agent_id": f.agent_id,
                    "agent_name": f.agent_name,
                    "status": f.status,
                    "result": f.result[:2000],
                    "duration_seconds": f.duration_seconds,
                    "tools_executed": f.tools_executed,
                    "tools_used": f.tools_used,
                }}

        # 4. Synthesize response (stream if possible)
        yield {"event": "thinking", "data": {"stage": "synthesizing"}}

        if agent_findings:
            _failure_signals = ("LLM request timed out", "No response", "LLM error:",
                                "No connector for", "No output", "No LLM configured")
            completed = [
                f for f in agent_findings
                if f.status == "completed" and f.result
                and not any(f.result.startswith(sig) for sig in _failure_signals)
            ]

            if not completed:
                logger.warning("All %d agents failed (stream) — falling back to direct", len(agent_findings))
                response_text = await self._direct_handle(user_message, memory_context)
            elif len(completed) == 1 and len(agent_findings) <= 2:
                raw = completed[0].result
                if len(raw) < 300 or raw.strip().startswith('{'):
                    response_text = await self._enrich_thin_result(
                        user_message, completed[0], memory_context
                    )
                else:
                    response_text = raw
            else:
                findings_dicts = [
                    {"agent_id": f.agent_id, "agent_name": f.agent_name,
                     "task": f.task, "result": f.result, "status": f.status}
                    for f in completed
                ]
                if astra_conn and hasattr(astra_conn, "synthesize_findings"):
                    try:
                        response_text = await astra_conn.synthesize_findings(
                            user_message, findings_dicts, memory_context
                        )
                        if not response_text or not response_text.strip():
                            logger.warning("ASTRA synthesis returned empty (stream) — falling back to direct")
                            response_text = await self._direct_handle(user_message, memory_context)
                    except Exception:
                        response_text = self._fallback_synthesis(user_message, completed)
                else:
                    response_text = self._fallback_synthesis(user_message, completed)
        else:
            # Direct handling — stream tokens from LLM
            if hasattr(self._llm, "stream"):
                system = self._build_system_prompt(user_message, memory_context)
                window = self._conversation[-50:] + [{"role": "user", "content": user_message}]
                response_text = ""
                async for chunk in self._llm.stream(
                    messages=window,
                    system=system,
                    model_tier="default",
                ):
                    response_text += chunk
                    yield {"event": "token", "data": {"text": chunk}}
            else:
                response_text = await self._direct_handle(user_message, memory_context)

        # 5. Persist and learn (same as chat())
        self._conversation.append({"role": "user", "content": user_message})
        self._conversation.append({"role": "assistant", "content": response_text})
        self._persist_messages(user_message, response_text, memories)
        await self._extract_learnings(user_message, response_text)

        elapsed = round(time.monotonic() - start_time, 2)
        agents_used = [f.agent_id for f in agent_findings]
        total_tools = sum(f.tools_executed for f in agent_findings)
        total_msgs = sum(f.messages_exchanged for f in agent_findings)

        if self._learning:
            try:
                self._learning.record_interaction(
                    user_message=user_message, route=route,
                    agents_used=agents_used, response_length=len(response_text),
                    agent_findings_count=len(agent_findings),
                    tools_used_count=total_tools, duration_seconds=elapsed,
                )
                # Record individual agent outcomes (closes learning feedback loop for streaming)
                for f in agent_findings:
                    quality = 0.7 if f.status == "success" else 0.3
                    if f.tools_executed > 0:
                        quality += 0.1
                    self._learning.record_agent_outcome(
                        agent_id=f.agent_id,
                        task_description=f.task,
                        status=f.status,
                        result_quality=min(1.0, quality),
                        duration_seconds=f.duration_seconds,
                        tools_used=f.tools_executed,
                    )
            except Exception as e:
                logger.error("Learning engine tracking failed: %s", e)

        # Publish agent findings to message bus
        if self._bus and agent_findings:
            try:
                msg = self._bus.create_message(
                    topic="agent.findings",
                    sender="brain",
                    payload={
                        "query": user_message[:200],
                        "agent_ids": agents_used,
                        "route": route,
                    },
                )
                await self._bus.publish(msg)
            except Exception as e:
                logger.warning("Bus publish agent findings failed: %s", e)

        # Yield final complete response
        reasoning = route_decision.get("reasoning", "")
        final = ChatMessage(
            role="assistant",
            content=response_text,
            agent_id="astra" if agent_findings else "root",
            memories_used=[m.id for m in memories if m.id],
            agents_used=agents_used,
            agent_findings=agent_findings,
            route=route,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_messages_exchanged=total_msgs,
            total_tools_executed=total_tools,
            routing_reasoning=reasoning,
        )
        yield {"event": "done", "data": final.model_dump()}

    async def _dispatch_agents(self, subtasks: list[dict]) -> list[AgentFinding]:
        """Dispatch subtasks to agents via the Orchestrator (parallel execution)."""
        findings: list[AgentFinding] = []

        if self._orchestrator:
            try:
                orch_result = await self._orchestrator.execute_parallel(subtasks)
                for task in orch_result.tasks:
                    agent = self._registry.get(task.agent_id)
                    agent_name = agent.name if agent else task.agent_id
                    duration = 0.0
                    if task.started_at and task.completed_at:
                        try:
                            t0 = datetime.fromisoformat(task.started_at)
                            t1 = datetime.fromisoformat(task.completed_at)
                            duration = round((t1 - t0).total_seconds(), 2)
                        except Exception as exc:
                            logger.debug("Failed to parse task duration: %s", exc)
                    findings.append(AgentFinding(
                        agent_id=task.agent_id,
                        agent_name=agent_name,
                        task=task.description,
                        result=task.result or task.error or "No output",
                        status="completed" if task.result else "failed",
                        duration_seconds=duration,
                    ))
                return findings
            except Exception as e:
                logger.error("Orchestrator dispatch failed: %s", e)

        # Fallback: sequential dispatch if no orchestrator
        for st in subtasks:
            agent_id = st["agent_id"]
            task_desc = st["task"]
            agent = self._registry.get(agent_id)
            agent_name = agent.name if agent else agent_id
            connector = self._registry.get_connector(agent_id)

            if not connector:
                # Reroute to researcher as fallback for hallucinated agent names
                fallback_id = "researcher"
                connector = self._registry.get_connector(fallback_id)
                if connector:
                    logger.warning("No connector for '%s', rerouting to '%s'", agent_id, fallback_id)
                    agent_id = fallback_id
                    agent = self._registry.get(fallback_id)
                    agent_name = agent.name if agent else fallback_id
                else:
                    findings.append(AgentFinding(
                        agent_id=agent_id, agent_name=agent_name,
                        task=task_desc, result=f"No connector for {agent_id}",
                        status="failed",
                    ))
                    continue

            t0 = time.monotonic()
            try:
                if hasattr(connector, "send_task"):
                    result = await connector.send_task(task_desc)
                else:
                    result = {"error": "No send_task method"}

                result_text = result.get("result", result.get("error", str(result)))
                findings.append(AgentFinding(
                    agent_id=agent_id, agent_name=agent_name,
                    task=task_desc, result=str(result_text)[:5000],
                    status="completed" if not result.get("error") else "failed",
                    duration_seconds=round(time.monotonic() - t0, 2),
                    messages_exchanged=result.get("messages_exchanged", 0),
                    tools_executed=result.get("tools_executed", 0),
                    tools_used=result.get("tools_used", []),
                ))
            except Exception as e:
                findings.append(AgentFinding(
                    agent_id=agent_id, agent_name=agent_name,
                    task=task_desc, result=str(e), status="failed",
                    duration_seconds=round(time.monotonic() - t0, 2),
                ))

        return findings

    async def _dispatch_pipeline(self, subtasks: list[dict]) -> list[AgentFinding]:
        """Execute subtasks as a sequential pipeline — each step feeds into the next.

        Subtasks with "depends_on" (0-based index) wait for that step to complete,
        and receive the previous step's results as context in their task description.
        Steps without dependencies run immediately.
        """
        findings: list[AgentFinding] = []
        results_by_index: dict[int, str] = {}

        # Group by dependency order
        for i, st in enumerate(subtasks):
            dep = st.get("depends_on")

            # If this step depends on a previous one, inject its results
            task_desc = st["task"]
            if dep is not None and dep in results_by_index:
                prev_result = results_by_index[dep][:3000]
                task_desc = (
                    f"{task_desc}\n\n"
                    f"## Context from previous step (step {dep + 1}):\n"
                    f"{prev_result}"
                )

            # Dispatch this single step
            step_findings = await self._dispatch_agents([
                {"agent_id": st["agent_id"], "task": task_desc}
            ])
            findings.extend(step_findings)

            # Store result for dependent steps
            if step_findings:
                results_by_index[i] = step_findings[-1].result

            logger.info("Pipeline step %d/%d complete: %s → %s",
                        i + 1, len(subtasks), st["agent_id"],
                        "success" if step_findings and step_findings[-1].status == "completed" else "failed")

        return findings

    async def _spawn_exploration_agents(
        self,
        user_message: str,
        initial_findings: list[AgentFinding],
        astra_conn,
    ) -> list[AgentFinding]:
        """Auto-dispatch additional agents when initial findings reveal new avenues.

        After agents complete their work, ASTRA reviews findings and decides
        if more specialized agents should be dispatched to explore discoveries.
        This is how ROOT proactively explores — MiRo, specialists, and analysts
        get auto-dispatched when new opportunities or knowledge gaps emerge.
        """
        if not astra_conn or not self._llm:
            return []

        # Only spawn if we got meaningful results
        successful = [f for f in initial_findings if f.status == "completed" and len(f.result) > 100]
        if not successful:
            return []

        # Ask ASTRA to identify new avenues worth exploring
        findings_summary = "\n".join(
            f"- {f.agent_name}: {f.result[:500]}" for f in successful[:5]
        )

        spawn_prompt = (
            "Review these agent findings and identify NEW AVENUES worth exploring.\n"
            "If the findings reveal opportunities, strategies, risks, or knowledge gaps\n"
            "that specialist agents should investigate further, return dispatch instructions.\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"spawn": [{"agent_id": "...", "task": "specific exploration task"}], "reasoning": "..."}\n'
            'Return {"spawn": [], "reasoning": "no new avenues"} if nothing needs further exploration.\n\n'
            "IMPORTANT: Only spawn if there are genuinely new avenues. Max 3 spawned agents.\n"
            "Use specialist agents: miro (predictions), algorithm_researcher, backtester,\n"
            "opportunity_scanner, market_researcher, startup_builder, etc.\n"
        )

        prompt = (
            f"Original request: {user_message}\n\n"
            f"## Agent Findings:\n{findings_summary}"
        )

        try:
            response = await self._llm.complete(
                system=spawn_prompt,
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                temperature=0.3,
            )

            text = response.strip()
            if "```" in text:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                text = text[start:end].strip()

            data = json.loads(text)
            spawn_tasks = data.get("spawn", [])

            if not spawn_tasks:
                return []

            # Limit to 3 spawned agents
            spawn_tasks = spawn_tasks[:3]

            # Inject context from initial findings into spawned tasks
            context_snippet = findings_summary[:2000]
            enriched_tasks = []
            for st in spawn_tasks:
                enriched_tasks.append({
                    "agent_id": st["agent_id"],
                    "task": (
                        f"{st['task']}\n\n"
                        f"## Context from initial investigation:\n{context_snippet}"
                    ),
                })

            logger.info("ASTRA spawning %d exploration agents: %s (reason: %s)",
                        len(enriched_tasks),
                        [t["agent_id"] for t in enriched_tasks],
                        data.get("reasoning", "")[:100])

            return await self._dispatch_agents(enriched_tasks)

        except Exception as e:
            logger.debug("Spawn exploration failed (non-critical): %s", e)
            return []

    def _build_system_prompt(self, user_message: str, memory_context: str) -> str:
        """Build the full system prompt with memories, skills, tools, and directives."""
        skill_context = ""
        if self._skills:
            relevant_skills = self._skills.search(user_message, limit=3)
            if relevant_skills:
                skill_context = self._skills.build_context(relevant_skills)

        tool_defs = self._plugins.list_tools() if self._plugins else []

        now = datetime.now(timezone.utc)
        system = SYSTEM_PROMPT + f"\n\n## Current Date & Time\nToday is {now.strftime('%A, %B %d, %Y')} (UTC: {now.strftime('%H:%M')}). Use this for all date-aware responses."
        if memory_context:
            system += f"\n\n## Relevant Memories\n{memory_context}"
        if skill_context:
            system += f"\n\n{skill_context}"
        if tool_defs:
            system += (
                "\n\n## Tools — USE THEM\n"
                "You have real, executable tools. When a task needs live data, "
                "searching the web, fetching URLs, running shell commands, "
                "calculations, or file access — CALL THE TOOL. "
                "Don't describe what you would do. Actually do it."
            )

        # Inject active directives so ROOT is aware of autonomous work
        directive_ctx = self._build_directive_context()
        if directive_ctx:
            system += f"\n\n{directive_ctx}"

        # Inject ecosystem awareness — cross-project intelligence
        eco_ctx = build_ecosystem_context(self._ecosystem)
        if eco_ctx:
            system += f"\n\n{eco_ctx}"

        # Inject prediction intelligence — active forecasts and calibration
        pred_ctx = build_prediction_context(self._prediction_ledger)
        if pred_ctx:
            system += f"\n\n{pred_ctx}"

        # Inject experience wisdom — lessons from past successes/failures
        exp_ctx = build_experience_context(self._experience_memory, user_message)
        if exp_ctx:
            system += f"\n\n{exp_ctx}"

        return system

    async def _enrich_thin_result(
        self, user_message: str, finding: AgentFinding, memory_context: str,
    ) -> str:
        """Process an agent result into a clear, structured response for Yohan.

        Never returns raw agent output — always formats for human consumption
        with context, structure, and actionable insights.
        """
        try:
            now = datetime.now(timezone.utc)
            raw_len = len(finding.result)
            system = (
                "You are ROOT — the execution governor of an AI civilization. "
                "An agent has completed work. Your job: present the findings to Yohan "
                "in a clear, well-structured, and actionable format.\n\n"
                "## Response Rules\n"
                "- NEVER dump raw data — always interpret and contextualize\n"
                "- Use clear markdown: headers, bullet points, bold for key facts\n"
                "- Lead with the answer/conclusion, then supporting details\n"
                "- Include implications and suggested next steps when relevant\n"
                "- If the agent found numbers/data, present them in context\n"
                "- Match response depth to question complexity: simple question = efficient answer, "
                "complex topic = thorough deep-dive with full explanation. Never artificially shorten.\n\n"
                f"Current date: {now.strftime('%A, %B %d, %Y')} UTC."
            )
            # Truncate very long results to avoid context overflow
            result_text = finding.result[:8000] if raw_len > 8000 else finding.result
            content = (
                f"Yohan asked: {user_message}\n\n"
                f"Agent **{finding.agent_name}** ({finding.agent_id}) returned:\n"
                f"---\n{result_text}\n---\n\n"
            )
            if memory_context:
                content += f"Relevant context from memory:\n{memory_context}\n\n"
            content += "Present this clearly and comprehensively for Yohan."

            # Use fast model — enrichment is formatting, not reasoning
            return await self._llm.complete(
                system=system,
                messages=[{"role": "user", "content": content}],
                model_tier="fast", temperature=0.4,
            )
        except Exception as e:
            logger.warning("Result processing failed: %s — using raw result", e)
            return finding.result

    async def _direct_handle(self, user_message: str, memory_context: str) -> str:
        """ROOT handles the request directly when no agent delegation needed."""
        system = self._build_system_prompt(user_message, memory_context)
        window = self._conversation[-10:] + [{"role": "user", "content": user_message}]
        # Use default model for substantive queries, fast only for short/simple ones
        is_simple = len(user_message.split()) <= 8
        tier = "fast" if is_simple else "default"
        return await self._llm.complete(
            system=system, messages=window,
            model_tier=tier, temperature=0.5,
        )

    async def remember(self, content: str, memory_type: str = "fact", tags: Optional[list[str]] = None) -> MemoryEntry:
        """Explicitly store something in memory."""
        try:
            mt = MemoryType(memory_type)
        except ValueError:
            mt = MemoryType.FACT
        entry = MemoryEntry(
            content=content,
            memory_type=mt,
            tags=tags or [],
            source="yohan_direct",
            confidence=1.0,
        )
        return self._memory.store(entry)

    async def delegate(self, agent_id: str, task: str) -> dict[str, Any]:
        """Delegate a task to a specific agent."""
        agent = self._registry.get(agent_id)
        if not agent:
            return {"error": f"Agent '{agent_id}' not found"}

        connector = self._registry.get_connector(agent_id)
        if not connector:
            return {"error": f"No connector for agent '{agent_id}'"}

        self._registry.update_status(agent_id, "working")
        try:
            if hasattr(connector, "send_task"):
                result = await connector.send_task(task)
            elif hasattr(connector, "delegate_task"):
                result = await connector.delegate_task(agent_id, task)
            else:
                result = {"error": "Agent connector has no task method"}

            self._registry.increment_tasks(agent_id)
            self._registry.update_status(agent_id, "idle")

            self._memory.store(MemoryEntry(
                content=f"Delegated to {agent.name}: {task[:200]}",
                memory_type=MemoryType.OBSERVATION,
                tags=["delegation", agent_id],
                source="brain",
            ))

            return result
        except Exception as e:
            self._registry.update_status(agent_id, "error")
            return {"error": str(e)}

    def get_conversation(self) -> list[dict[str, str]]:
        return list(self._conversation)

    def clear_conversation(self) -> None:
        self._conversation.clear()
        # Start a new session in conversation store
        if self._conversations:
            self._conversations.new_session()

    # ── internals ──────────────────────────────────────────────

    def _persist_messages(self, user_msg: str, assistant_msg: str, memories: list) -> None:
        """Persist messages to conversation store."""
        if not self._conversations:
            return
        try:
            self._conversations.add_message("user", user_msg)
            self._conversations.add_message(
                "assistant", assistant_msg, agent_id="root",
                memories_used=[m.id for m in memories if m.id],
            )
        except Exception as e:
            logger.error("Failed to persist conversation: %s", e)

    async def _build_financial_status(self) -> str:
        """Build a financial status report from ROOT's internal databases."""
        sections: list[str] = []
        sections.append("# Financial Status Report\n")

        # 1. Hedge Fund (Alpaca paper trading)
        hedge_fund = getattr(self, '_hedge_fund', None)
        if not hedge_fund:
            # Try to find it via the app state or other references
            hedge_fund = getattr(self, '_money', None)
            if hedge_fund and hasattr(hedge_fund, '_hedge_fund'):
                hedge_fund = hedge_fund._hedge_fund
            elif not hasattr(hedge_fund, 'get_performance'):
                hedge_fund = None

        if hedge_fund and hasattr(hedge_fund, 'get_performance'):
            try:
                perf = hedge_fund.get_performance()
                portfolio = (await hedge_fund.get_portfolio()) if hasattr(hedge_fund, 'get_portfolio') else {}
                sections.append("## Hedge Fund (Alpaca Paper Trading)")
                sections.append(f"- **Total P&L**: ${perf.get('total_pnl', 0):,.2f}")
                sections.append(f"- **Daily P&L**: ${perf.get('daily_pnl', 0):,.2f}")
                sections.append(f"- **Total Trades**: {perf.get('total_trades', 0)}")
                sections.append(f"- **Win Rate**: {perf.get('win_rate', 0):.1f}%")
                sections.append(f"- **Open Trades**: {perf.get('open_trades', 0)}")
                if portfolio:
                    sections.append(f"- **Portfolio Value**: ${portfolio.get('total_value', 0):,.2f}")
                    sections.append(f"- **Cash**: ${portfolio.get('cash', 0):,.2f}")
                    positions = portfolio.get('positions', [])
                    if positions:
                        sections.append(f"- **Positions**: {len(positions)} open")
                        for p in positions[:5]:
                            sym = p.get('symbol', '?')
                            qty = p.get('qty', p.get('quantity', 0))
                            pnl = p.get('unrealized_pl', p.get('pnl', 0))
                            sections.append(f"  - {sym}: {qty} shares, P&L ${float(pnl):,.2f}")
                sections.append("")
            except Exception as e:
                sections.append(f"## Hedge Fund\n- Error fetching data: {str(e)[:100]}\n")

        # 2. Revenue Engine
        revenue = getattr(self, '_revenue', None)
        if revenue and hasattr(revenue, 'stats'):
            try:
                rev_stats = revenue.stats()
                sections.append("## Revenue Engine")
                sections.append(f"- **Total Revenue**: ${rev_stats.get('total_revenue', 0):,.2f}")
                sections.append(f"- **Total Cost**: ${rev_stats.get('total_cost', 0):,.2f}")
                sections.append(f"- **Profit**: ${rev_stats.get('profit', 0):,.2f}")
                sections.append(f"- **Products**: {rev_stats.get('total_products', 0)}")
                sections.append(f"- **Emergency Mode**: {'YES' if rev_stats.get('emergency_mode') else 'No'}")
                streams = rev_stats.get('streams', {})
                if streams:
                    sections.append("- **Revenue Streams**:")
                    for name, data in streams.items():
                        count = data.get('count', 0)
                        rev = data.get('revenue', 0)
                        sections.append(f"  - {name}: {count} products, ${rev:,.2f}")
                sections.append("")
            except Exception as e:
                sections.append(f"## Revenue Engine\n- Error: {str(e)[:100]}\n")

        # 3. Polymarket Bot
        polymarket = getattr(self, '_polymarket_bot', None)
        if not polymarket:
            # Check via proactive engine
            proactive = getattr(self, '_proactive', None)
            if proactive and hasattr(proactive, '_polymarket_bot'):
                polymarket = proactive._polymarket_bot
        if polymarket and hasattr(polymarket, 'stats'):
            try:
                pm_stats = polymarket.stats()
                sections.append("## Polymarket Bot")
                sections.append(f"- **Open Positions**: {pm_stats.get('open_positions', 0)}")
                sections.append(f"- **Closed Positions**: {pm_stats.get('closed_positions', 0)}")
                sections.append(f"- **Total P&L**: ${pm_stats.get('total_pnl', 0):,.2f}")
                sections.append(f"- **Win Rate**: {pm_stats.get('win_rate', 0):.1f}%")
                sections.append(f"- **Signals Generated**: {pm_stats.get('total_signals', 0)}")
                sections.append(f"- **Markets Tracked**: {pm_stats.get('market_snapshots', 0)}")
                trades = pm_stats.get('recent_trades', [])
                if trades:
                    sections.append("- **Recent Trades**:")
                    for t in trades[:5]:
                        sections.append(f"  - {t.get('question', '?')[:50]} | "
                                      f"{t.get('strategy', '?')} | P&L: ${t.get('pnl', 0):,.2f}")
                sections.append("")
            except Exception as e:
                sections.append(f"## Polymarket Bot\n- Error: {str(e)[:100]}\n")
        elif not polymarket:
            sections.append("## Polymarket Bot\n- Not configured (no POLYMARKET_PRIVATE_KEY)\n")

        # 4. Summary
        if len(sections) <= 2:
            sections.append("No active trading or revenue systems found with data.\n"
                          "Set up ALPACA_API_KEY for stock trading or "
                          "POLYMARKET_PRIVATE_KEY for prediction markets.")

        return "\n".join(sections)

    def _format_memories(self, memories: list[MemoryEntry]) -> str:
        if not memories:
            return ""
        lines = []
        for m in memories:
            tags = f" [{', '.join(m.tags)}]" if m.tags else ""
            lines.append(f"- ({m.memory_type.value}{tags}) {m.content}")
        return "\n".join(lines)
