"""
Skill Executor — makes ROOT's procedural skills executable.

Skills are SKILL.md files with YAML frontmatter that provide procedural
knowledge.  By themselves they are documentation injected into LLM context.
The SkillExecutor bridges the gap: it combines a skill's procedural content
with the task at hand AND access to relevant plugin tools, then orchestrates
LLM-driven execution.

A skill becomes "executable" when the LLM is given both the skill's
procedural knowledge AND access to the tools it references.

Flow:
1. Look up skill from SkillEngine
2. Build a rich prompt (skill content + task + caller context)
3. Resolve any tool references from PluginEngine
4. Call LLM with skill context → execution plan + tool calls
5. Execute tool calls through PluginEngine
6. Return structured SkillResult
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("root.skill_executor")


# ── Data Models (immutable) ─────────────────────────────────────


@dataclass(frozen=True)
class SkillResult:
    """Immutable result of a skill execution."""

    skill_name: str
    task: str
    output: str
    tools_used: tuple[str, ...] = ()
    success: bool = True
    duration_ms: int = 0
    error: str = ""


# ── Skill Executor ──────────────────────────────────────────────


class SkillExecutor:
    """Orchestrates executable skills by combining procedural knowledge with tools.

    Parameters
    ----------
    skill_engine:
        SkillEngine instance for looking up skills.
    plugin_engine:
        PluginEngine instance for resolving and invoking tools.
    llm:
        LLM service for generating execution plans and reasoning.
    """

    # Keywords in skill content that hint at tool references
    _TOOL_HINT_PATTERNS: tuple[str, ...] = (
        r"tool[s]?:\s*\[([^\]]+)\]",
        r"uses?:\s*\[([^\]]+)\]",
        r"requires?:\s*\[([^\]]+)\]",
        r"plugins?:\s*\[([^\]]+)\]",
    )

    # Keywords that indicate a skill has clear executable procedures
    _PROCEDURE_INDICATORS: tuple[str, ...] = (
        "step 1", "step 2", "## steps", "## procedure", "## process",
        "## workflow", "1.", "2.", "3.", "run ", "execute ", "invoke ",
        "call ", "create ", "build ", "deploy ", "check ", "verify ",
    )

    def __init__(
        self,
        skill_engine=None,
        plugin_engine=None,
        llm=None,
    ) -> None:
        self._skill_engine = skill_engine
        self._plugin_engine = plugin_engine
        self._llm = llm

        # Stats
        self._executions = 0
        self._successes = 0
        self._failures = 0
        self._total_duration_ms = 0

    # ── Public API ───────────────────────────────────────────────

    async def execute(
        self,
        skill_name: str,
        task: str,
        context: Optional[dict[str, Any]] = None,
    ) -> SkillResult:
        """Execute a skill against a specific task.

        Parameters
        ----------
        skill_name:
            Skill key in the format "category/name".
        task:
            The task description to execute using this skill's knowledge.
        context:
            Optional additional context (prior results, constraints, etc.).

        Returns
        -------
        SkillResult with output, tools used, and timing info.
        """
        start = time.monotonic()
        self._executions += 1

        # 1. Look up skill
        if not self._skill_engine:
            return self._fail(skill_name, task, start, "No skill engine configured")

        skill = self._skill_engine.get(skill_name)
        if not skill:
            return self._fail(skill_name, task, start, f"Skill '{skill_name}' not found")

        # 2. Build execution prompt
        prompt = self._build_prompt(skill, task, context)

        # 3. Resolve tool references
        tool_refs = self._extract_tool_refs(skill.content)
        available_tools = self._resolve_tools(tool_refs)
        tool_descriptions = self._format_tool_descriptions(available_tools)

        # 4. Call LLM for execution plan
        if not self._llm:
            return self._fail(skill_name, task, start, "No LLM configured")

        try:
            plan_response = await self._llm.complete(
                system=self._build_system_prompt(skill, tool_descriptions),
                messages=[{"role": "user", "content": prompt}],
                model_tier="default",
                max_tokens=2000,
            )
        except Exception as exc:
            logger.error("LLM call failed during skill execution '%s': %s", skill_name, exc)
            return self._fail(skill_name, task, start, f"LLM error: {exc}")

        # 5. Execute any tool calls from the plan
        tools_used: list[str] = []
        tool_outputs: list[str] = []

        tool_calls = self._parse_tool_calls(plan_response)
        if tool_calls and self._plugin_engine:
            for tool_call in tool_calls:
                tool_name = tool_call.get("tool", "")
                tool_args = tool_call.get("args", {})

                if tool_name not in available_tools:
                    logger.warning(
                        "Skill '%s' tried to invoke unknown tool '%s' — skipping",
                        skill_name, tool_name,
                    )
                    continue

                try:
                    result = await self._plugin_engine.invoke(tool_name, tool_args)
                    tools_used.append(tool_name)
                    if result.success:
                        tool_outputs.append(
                            f"[{tool_name}]: {_truncate(str(result.output), 2000)}"
                        )
                    else:
                        tool_outputs.append(
                            f"[{tool_name}] ERROR: {result.error}"
                        )
                except Exception as exc:
                    logger.error("Tool '%s' invocation failed: %s", tool_name, exc)
                    tool_outputs.append(f"[{tool_name}] EXCEPTION: {exc}")

        # 6. If tools were used, do a follow-up LLM call to synthesize
        if tool_outputs:
            try:
                synthesis = await self._llm.complete(
                    system=(
                        "You are completing a skill execution. Synthesize the tool "
                        "results into a clear final output for the user's task."
                    ),
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": plan_response},
                        {
                            "role": "user",
                            "content": (
                                "Tool results:\n"
                                + "\n\n".join(tool_outputs)
                                + "\n\nSynthesize a final answer."
                            ),
                        },
                    ],
                    model_tier="fast",
                    max_tokens=1500,
                )
                output = synthesis.strip()
            except Exception as exc:
                logger.warning("Synthesis LLM call failed: %s — using raw plan", exc)
                output = plan_response.strip()
        else:
            output = plan_response.strip()

        elapsed_ms = int((time.monotonic() - start) * 1000)
        self._successes += 1
        self._total_duration_ms += elapsed_ms

        logger.info(
            "Skill '%s' executed in %dms — %d tools used",
            skill_name, elapsed_ms, len(tools_used),
        )

        return SkillResult(
            skill_name=skill_name,
            task=task,
            output=output,
            tools_used=tuple(tools_used),
            success=True,
            duration_ms=elapsed_ms,
        )

    def can_execute(self, skill_name: str) -> bool:
        """Check if a skill exists and has the resources needed for execution.

        A skill is considered executable when:
        - It exists in the skill engine
        - It has tool references that can be resolved, OR
        - It has clear procedural steps the LLM can follow
        """
        if not self._skill_engine:
            return False

        skill = self._skill_engine.get(skill_name)
        if not skill:
            return False

        # Has tool references?
        tool_refs = self._extract_tool_refs(skill.content)
        if tool_refs:
            # At least some tools must be resolvable
            available = self._resolve_tools(tool_refs)
            if available:
                return True

        # Has clear procedures?
        content_lower = skill.content.lower()
        for indicator in self._PROCEDURE_INDICATORS:
            if indicator in content_lower:
                return True

        return False

    def list_executable(self) -> list[str]:
        """List all skills that can be executed (have tool refs or clear procedures)."""
        if not self._skill_engine:
            return []

        executable: list[str] = []
        for skill in self._skill_engine.list_all():
            key = f"{skill.category}/{skill.name}"
            if self.can_execute(key):
                executable.append(key)

        return executable

    def stats(self) -> dict[str, Any]:
        """Execution statistics."""
        avg_duration = (
            round(self._total_duration_ms / self._executions)
            if self._executions > 0
            else 0
        )
        return {
            "total_executions": self._executions,
            "successes": self._successes,
            "failures": self._failures,
            "avg_duration_ms": avg_duration,
            "executable_skills": len(self.list_executable()),
        }

    # ── Internals ────────────────────────────────────────────────

    def _fail(self, skill_name: str, task: str, start: float, error: str) -> SkillResult:
        """Build a failed SkillResult and update counters."""
        elapsed_ms = int((time.monotonic() - start) * 1000)
        self._failures += 1
        self._total_duration_ms += elapsed_ms
        logger.warning("Skill execution failed '%s': %s", skill_name, error)
        return SkillResult(
            skill_name=skill_name,
            task=task,
            output="",
            success=False,
            duration_ms=elapsed_ms,
            error=error,
        )

    def _build_prompt(
        self,
        skill,
        task: str,
        context: Optional[dict[str, Any]],
    ) -> str:
        """Build the user prompt combining skill content, task, and context."""
        parts = [
            f"## Task\n{task}",
            f"\n## Skill: {skill.category}/{skill.name}",
            f"*{skill.description}*\n",
            skill.content[:4000],
        ]

        if context:
            ctx_str = "\n".join(f"- **{k}**: {v}" for k, v in context.items())
            parts.append(f"\n## Additional Context\n{ctx_str}")

        parts.append(
            "\n## Instructions\n"
            "Follow the skill's procedures to complete the task. "
            "If you need to use tools, output JSON tool calls in this format:\n"
            '```tool_calls\n[{"tool": "tool_name", "args": {"key": "value"}}]\n```\n'
            "Otherwise, produce the final output directly."
        )

        return "\n".join(parts)

    @staticmethod
    def _build_system_prompt(skill, tool_descriptions: str) -> str:
        """Build the system prompt for skill execution."""
        parts = [
            f"You are executing the '{skill.name}' skill. "
            f"This skill provides procedural knowledge for: {skill.description}",
            "\nFollow the skill's procedures precisely. Be concrete and actionable.",
        ]

        if tool_descriptions:
            parts.append(f"\n## Available Tools\n{tool_descriptions}")
            parts.append(
                "\nTo use a tool, include a ```tool_calls``` code block with JSON. "
                "You may call multiple tools."
            )

        return "\n".join(parts)

    def _extract_tool_refs(self, content: str) -> list[str]:
        """Extract tool references from skill content."""
        refs: list[str] = []
        for pattern in self._TOOL_HINT_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                tools = [t.strip().strip("'\"") for t in match.split(",")]
                refs.extend(t for t in tools if t)
        return refs

    def _resolve_tools(self, tool_refs: list[str]) -> dict[str, Any]:
        """Resolve tool references to actual plugin tools."""
        if not self._plugin_engine or not tool_refs:
            return {}

        resolved: dict[str, Any] = {}
        for ref in tool_refs:
            entry = self._plugin_engine.get_tool(ref)
            if entry:
                plugin_id, tool = entry
                resolved[ref] = tool
        return resolved

    @staticmethod
    def _format_tool_descriptions(tools: dict[str, Any]) -> str:
        """Format resolved tools into a description string for the LLM."""
        if not tools:
            return ""
        parts: list[str] = []
        for name, tool in tools.items():
            desc = getattr(tool, "description", "No description")
            params = getattr(tool, "parameters", {})
            param_str = ""
            if params:
                props = params.get("properties", {})
                if props:
                    param_str = ", ".join(
                        f"{k} ({v.get('type', '?')})"
                        for k, v in props.items()
                    )
            parts.append(f"- **{name}**: {desc}")
            if param_str:
                parts.append(f"  Parameters: {param_str}")
        return "\n".join(parts)

    @staticmethod
    def _parse_tool_calls(response: str) -> list[dict[str, Any]]:
        """Parse tool call blocks from LLM response.

        Looks for ```tool_calls ... ``` blocks containing JSON arrays.
        """
        pattern = r"```tool_calls\s*\n(.*?)\n```"
        matches = re.findall(pattern, response, re.DOTALL)
        calls: list[dict[str, Any]] = []
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, list):
                    calls.extend(parsed)
                elif isinstance(parsed, dict):
                    calls.append(parsed)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Failed to parse tool_calls block: %s", exc)
        return calls


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis indicator."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...(truncated)"
