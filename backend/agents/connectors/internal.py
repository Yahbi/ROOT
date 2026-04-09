"""
Internal Agent Connector — LLM-powered specialist agents.

Uses dynamic prompt generation from agent profiles so ALL agents
(core + civilization) get proper, actionable system prompts with
tool-aware capabilities. No more generic fallback prompts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from datetime import datetime, timezone
from typing import Any, Optional

from backend.agents.connectors import sanitize_tool_output
from backend.agents.prompt_builder import build_system_message, get_tools_for_agent

logger = logging.getLogger("root.connectors.internal")


class InternalAgentConnector:
    """Executes tasks using the LLM with agent-specific prompts and plugin tools.

    Prompts are generated dynamically from the agent's AgentProfile — no more
    hardcoded prompt dict. Every agent (core or civilization) gets a proper prompt.
    """

    def __init__(
        self,
        agent_id: str,
        llm: Any,
        plugins: Any = None,
        registry: Any = None,
        collab: Any = None,
    ) -> None:
        self._agent_id = agent_id
        self._llm = llm
        self._plugins = plugins
        self._registry = registry
        self._collab = collab
        self._skill_executor = None

    def set_collab(self, collab: Any) -> None:
        """Wire in the AgentCollaboration instance after construction."""
        self._collab = collab

    async def health_check(self) -> dict[str, Any]:
        return {"status": "online", "type": "internal", "agent": self._agent_id}

    def _build_system(self) -> str:
        """Build system prompt dynamically from agent profile."""
        agent = self._registry.get(self._agent_id) if self._registry else None
        if agent:
            return build_system_message(agent)

        # Fallback for agents without registry access
        now = datetime.now(timezone.utc)
        return (
            f"You are a specialist agent ({self._agent_id}) in ROOT's AI civilization.\n"
            f"Complete tasks thoroughly using your tools.\n\n"
            f"## Current Date\nToday is {now.strftime('%A, %B %d, %Y')} (UTC)."
        )

    def _get_filtered_tools(self) -> list[dict]:
        """Get tool definitions filtered to this agent's capabilities."""
        if not self._plugins:
            return []

        all_tools = self._plugins.list_tools()
        agent = self._registry.get(self._agent_id) if self._registry else None
        if not agent:
            return all_tools  # Give all tools if no profile

        # Get tools mapped to this agent's capabilities
        allowed = get_tools_for_agent(agent)
        if not allowed:
            return all_tools  # Give all tools if no mapping

        # Filter to only tools this agent should use, but always include basics
        always_allowed = {
            "web_web_search", "web_fetch_url", "calculator_calculate",
            "proposals_propose_direction", "agent_comms_request_agent_help",
            "agent_comms_broadcast_finding", "agent_comms_invoke_agent",
            "file_writer_write_file", "reports_write_report", "charts_generate_chart",
        }
        allowed = allowed | always_allowed

        filtered = [t for t in all_tools if t.get("name") in allowed]
        return filtered if filtered else all_tools  # Fallback to all if filter empty

    def _extract_tool_calls_from_text(self, text: str) -> list[dict[str, Any]]:
        """Try to extract tool calls from plain text (Ollama sometimes outputs them as text)."""
        try:
            # Look for JSON with "name" and "parameters" keys
            cleaned = text.strip()
            # Strip markdown code blocks
            if "```" in cleaned:
                start = cleaned.index("```") + 3
                if cleaned[start:start + 4] == "json":
                    start += 4
                end = cleaned.index("```", start)
                cleaned = cleaned[start:end].strip()

            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "name" in parsed:
                name = parsed["name"]
                args = parsed.get("parameters", parsed.get("input", {}))
                return [{"name": name, "input": args}]
        except (json.JSONDecodeError, ValueError):
            logger.debug("Failed to extract tool calls from text", exc_info=True)
        return []

    async def send_task(self, task: str) -> dict[str, Any]:
        """Execute a task using the LLM with specialized prompt and tools."""
        # Try skill executor for structured execution
        if hasattr(self, '_skill_executor') and self._skill_executor:
            try:
                task_lower = task.lower()
                matching = [s for s in self._skill_executor.list_executable()
                           if any(kw in task_lower for kw in s.split('-'))]
                if matching:
                    result = await self._skill_executor.execute(matching[0], task)
                    if result and result.success and result.output:
                        logger.info("Skill executor handled task via '%s'", matching[0])
                        return {
                            "agent": self._agent_id, "result": result.output,
                            "messages_exchanged": 0, "tools_executed": 0,
                            "tools_used": [f"skill:{matching[0]}"],
                        }
            except Exception as e:
                logger.debug("Skill executor unavailable: %s", e)

        system = self._build_system()
        messages = [{"role": "user", "content": task}]
        tool_defs = self._get_filtered_tools()

        msg_count = 1
        tool_count = 0
        tools_used: list[str] = []

        if not tool_defs:
            result = await self._llm.complete(
                system=system, messages=messages,
                model_tier="default", temperature=0.5,
            )
            return {
                "agent": self._agent_id, "result": result,
                "messages_exchanged": 2, "tools_executed": 0, "tools_used": [],
            }

        # Tool-use loop (up to 3 rounds)
        is_openai = getattr(self._llm, "provider", "") == "openai"
        working = list(messages)
        _loop_start = _time.monotonic()
        MAX_TOTAL_SECONDS = 300.0  # 5 minutes max total
        for _round in range(3):
            if _time.monotonic() - _loop_start > MAX_TOTAL_SECONDS:
                logger.warning("[%s] Total time exceeded %.0fs — stopping tool loop", self._agent_id, MAX_TOTAL_SECONDS)
                break
            try:
                text, tool_calls = await asyncio.wait_for(
                    self._llm.complete_with_tools(
                        system=system, messages=working,
                        tools=tool_defs, model_tier="default",
                    ),
                    timeout=280.0,  # Just under httpx read timeout (300s)
                )
            except asyncio.TimeoutError:
                # If we already got tool results, try a final fast completion
                if tool_count > 0:
                    logger.warning("[%s] Round %d timed out after %d tools — attempting final completion", self._agent_id, _round, tool_count)
                    try:
                        final = await asyncio.wait_for(
                            self._llm.complete(system=system, messages=working, model_tier="fast", temperature=0.5),
                            timeout=60.0,
                        )
                        return {"agent": self._agent_id, "result": final, "messages_exchanged": msg_count + 1,
                                "tools_executed": tool_count, "tools_used": tools_used}
                    except Exception:
                        logger.debug("[%s] Final fast completion after timeout also failed", self._agent_id, exc_info=True)
                agent = self._registry.get(self._agent_id) if self._registry else None
                agent_name = agent.name if agent else self._agent_id
                return {
                    "agent": self._agent_id,
                    "result": f"{agent_name} analysis timed out — LLM provider may be slow. Try again shortly.",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            except Exception as llm_err:
                logger.error("[%s] LLM error: %s", self._agent_id, llm_err)
                agent = self._registry.get(self._agent_id) if self._registry else None
                agent_name = agent.name if agent else self._agent_id
                return {
                    "agent": self._agent_id,
                    "result": f"{agent_name} encountered an error: {str(llm_err)[:200]}. Try again or check provider status.",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            msg_count += 1

            # Ollama sometimes returns tool calls as plain text JSON
            if not tool_calls and text:
                tool_calls = self._extract_tool_calls_from_text(text)
                if tool_calls:
                    logger.info("[%s] Extracted tool call from text: %s", self._agent_id, tool_calls[0].get("name"))

            if not tool_calls:
                return {
                    "agent": self._agent_id, "result": text or "No response",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }

            # Execute each tool call
            tool_results: list[tuple[dict, str]] = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("input", {})
                logger.info("[%s] Tool call: %s(%s)", self._agent_id, name, json.dumps(args)[:200])

                # Special case: synchronous agent invocation — handled directly, not via plugin
                if name == "agent_comms_invoke_agent" and self._collab:
                    target_id = args.get("agent_id", "researcher")
                    agent_task = args.get("task", "")
                    ctx = args.get("context", "")
                    if not agent_task:
                        output_str = json.dumps({"error": "task is required"})
                    else:
                        full_task = f"{agent_task}\n\nContext from {self._agent_id}: {ctx}" if ctx else agent_task
                        try:
                            wf = await asyncio.wait_for(
                                self._collab.delegate(
                                    from_agent=self._agent_id,
                                    to_agent=target_id,
                                    task=full_task,
                                ),
                                timeout=240.0,
                            )
                            output_str = json.dumps({
                                "agent": target_id,
                                "result": wf.final_result or "Agent returned no result",
                                "status": wf.status.value if hasattr(wf.status, "value") else str(wf.status),
                            }, default=str)[:4000]
                        except asyncio.TimeoutError:
                            output_str = json.dumps({"agent": target_id, "error": "Agent invocation timed out after 240s"})
                        except Exception as inv_err:
                            output_str = json.dumps({"agent": target_id, "error": str(inv_err)[:300]})
                    tool_results.append((tc, output_str))
                    tool_count = tool_count + 1
                    if name not in tools_used:
                        tools_used.append(name)
                    continue

                try:
                    result = await asyncio.wait_for(self._plugins.invoke(name, args), timeout=30.0)
                except asyncio.TimeoutError:
                    result = type('R', (), {'success': False, 'output': None, 'error': f"Tool '{name}' timed out"})()
                except Exception as tool_err:
                    result = type('R', (), {'success': False, 'output': None, 'error': str(tool_err)})()
                output = result.output if result.success else {"error": result.error}
                output = sanitize_tool_output(output)
                output_str = json.dumps(output, default=str)[:4000]
                tool_results.append((tc, output_str))
                tool_count = tool_count + 1
                if name not in tools_used:
                    tools_used.append(name)

            # Feed results back in the format the LLM provider expects
            if is_openai:
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": text or None,
                    "tool_calls": [
                        {
                            "id": tc.get("id", f"call_{_round}_{i}"),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("input", {})),
                            },
                        }
                        for i, (tc, _) in enumerate(tool_results)
                    ],
                }
                working.append(assistant_msg)
                for (tc, output_str) in tool_results:
                    working.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{_round}"),
                        "content": output_str,
                    })
            else:
                # Anthropic requires tool_use blocks in assistant content
                # and tool_result blocks in user content
                asst_content: list[dict[str, Any]] = []
                if text:
                    asst_content.append({"type": "text", "text": text})
                for tc, _ in tool_results:
                    asst_content.append({
                        "type": "tool_use",
                        "id": tc.get("id", f"call_{_round}"),
                        "name": tc["name"],
                        "input": tc.get("input", {}),
                    })
                working.append({"role": "assistant", "content": asst_content})
                working.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tc.get("id", f"call_{_round}"),
                            "content": output_str,
                        }
                        for tc, output_str in tool_results
                    ],
                })
            msg_count += 1

        final = await self._llm.complete(
            system=system, messages=working,
            model_tier="default", temperature=0.5,
        )
        msg_count += 1
        return {
            "agent": self._agent_id, "result": final,
            "messages_exchanged": msg_count, "tools_executed": tool_count,
            "tools_used": tools_used,
        }
