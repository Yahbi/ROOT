"""
HERMES Connector — Autonomous agent with terminal, browser, file ops, and messaging.

Powered by the LLM with aggressive tool use. HERMES is the "hands" of ROOT —
it actually executes things in the real world: runs commands, fetches web pages,
reads/writes files, and can send messages via available channels.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from datetime import datetime, timezone
from typing import Any, Optional

from backend.agents.connectors import sanitize_tool_output

logger = logging.getLogger("root.connectors.hermes")

_HERMES_PROMPT = (
    "You are HERMES — ROOT's autonomous execution agent. You are Yohan's hands.\n"
    "Your job is to EXECUTE tasks, not just describe them.\n\n"
    "## Core Principles\n"
    "1. USE TOOLS AGGRESSIVELY — run_command, fetch_url, web_search, read_file, list_files\n"
    "2. Chain multiple tool calls to complete multi-step tasks\n"
    "3. If a command fails, debug it and try again with a different approach\n"
    "4. Always verify your work — check outputs, confirm files exist, validate results\n\n"
    "## Capabilities\n"
    "- **Terminal**: Run any shell command via run_command (git, curl, python, npm, etc.)\n"
    "- **Browser**: Fetch any URL via fetch_url, search the web via web_search\n"
    "- **Files**: Read files with read_file, list directories with list_files\n"
    "- **Code**: Analyze Python with analyze_python, compute with calculate\n\n"
    "## Execution Style\n"
    "- Be thorough: if asked to research, search multiple sources\n"
    "- Be precise: give exact numbers, file paths, command outputs\n"
    "- Be autonomous: don't ask for clarification — make reasonable decisions and execute\n"
    "- Report results concisely with the actual data, not descriptions of what you did"
)


class HermesConnector:
    """LLM-powered autonomous execution agent with full tool access."""

    def __init__(self, llm: Any = None, plugins: Any = None) -> None:
        self._llm = llm
        self._plugins = plugins

    def set_llm(self, llm: Any, plugins: Any) -> None:
        """Late-bind LLM and plugins (set after startup)."""
        self._llm = llm
        self._plugins = plugins

    async def health_check(self) -> dict[str, Any]:
        if not self._llm:
            return {"status": "offline", "reason": "No LLM configured"}
        return {"status": "online", "type": "hermes", "agent": "hermes"}

    async def send_task(self, task: str) -> dict[str, Any]:
        """Execute a task autonomously using LLM + tools."""
        if not self._llm:
            return {"error": "HERMES not initialized — no LLM"}

        now = datetime.now(timezone.utc)
        date_line = f"\n\n## Current Date\nToday is {now.strftime('%A, %B %d, %Y')} (UTC). Use this date for all responses — never guess or use training data dates."
        system = (
            f"{_HERMES_PROMPT}\n\n"
            f"## Current Task from Yohan (via ROOT)\n"
            f"Execute this task completely. Use tools. Return real results."
            f"{date_line}"
        )
        messages = [{"role": "user", "content": task}]
        tool_defs = self._plugins.list_tools() if self._plugins else []

        msg_count = 1
        tool_count = 0
        tools_used: list[str] = []

        if not tool_defs:
            result = await self._llm.complete(
                system=system, messages=messages,
                model_tier="default", temperature=0.4,
            )
            return {
                "agent": "hermes", "result": result,
                "messages_exchanged": 2, "tools_executed": 0, "tools_used": [],
            }

        # Aggressive tool-use loop — 5 rounds (HERMES does more than other agents)
        working = list(messages)
        _loop_start = _time.monotonic()
        MAX_TOTAL_SECONDS = 300.0  # 5 minutes max total
        for _round in range(5):
            if _time.monotonic() - _loop_start > MAX_TOTAL_SECONDS:
                logger.warning("[hermes] Total time exceeded %.0fs — stopping tool loop", MAX_TOTAL_SECONDS)
                break
            try:
                text, tool_calls = await asyncio.wait_for(
                    self._llm.complete_with_tools(
                        system=system, messages=working,
                        tools=tool_defs, model_tier="default",
                    ),
                    timeout=120.0,
                )
            except asyncio.TimeoutError:
                return {
                    "agent": "hermes", "result": "LLM request timed out",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            except Exception as llm_err:
                logger.error("[hermes] LLM error: %s", llm_err)
                return {
                    "agent": "hermes", "result": f"LLM error: {str(llm_err)[:200]}",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            msg_count += 1
            if not tool_calls:
                return {
                    "agent": "hermes", "result": text or "Task completed (no output)",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }

            results_parts = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("input", {})
                logger.info("[hermes] Tool: %s(%s)", name, json.dumps(args)[:200])
                try:
                    result = await asyncio.wait_for(self._plugins.invoke(name, args), timeout=30.0)
                except asyncio.TimeoutError:
                    result = type('R', (), {'success': False, 'output': None, 'error': f"Tool '{name}' timed out"})()
                except Exception as tool_err:
                    result = type('R', (), {'success': False, 'output': None, 'error': str(tool_err)})()
                output = result.output if result.success else {"error": result.error}
                output = sanitize_tool_output(output)
                output_str = json.dumps(output, default=str)[:6000]
                results_parts.append(f"[{name}] → {output_str}")
                tool_count += 1
                if name not in tools_used:
                    tools_used.append(name)

            if text:
                working.append({"role": "assistant", "content": text})
            working.append({
                "role": "user",
                "content": "[TOOL RESULTS]\n" + "\n".join(results_parts),
            })
            msg_count += 1

        final = await self._llm.complete(
            system=system, messages=working,
            model_tier="default", temperature=0.4,
        )
        msg_count += 1
        return {
            "agent": "hermes", "result": final,
            "messages_exchanged": msg_count, "tools_executed": tool_count,
            "tools_used": tools_used,
        }

    async def list_skills(self) -> list[dict[str, str]]:
        """HERMES skills = the plugin tools available to it."""
        if not self._plugins:
            return []
        return [
            {"name": t["function"]["name"], "description": t["function"].get("description", "")}
            for t in self._plugins.list_tools()
        ]
