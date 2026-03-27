"""
Task Router — decides which agent handles a request.

Uses the LLM to classify intent and route to the best agent,
or handles it directly via ROOT's brain.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from backend.agents.registry import AgentRegistry
    from backend.services.llm import LLMService

logger = logging.getLogger("root.router")

ROUTER_SYSTEM = """You are ROOT's task router. Given a user request and the available agents,
decide how to handle it. Respond in JSON:

{
    "route": "direct" | "delegate" | "multi",
    "agent_ids": ["agent_id"],   // for delegate/multi
    "reasoning": "Why this route",
    "subtasks": [                // for multi-agent tasks
        {"agent_id": "...", "task": "..."}
    ]
}

Routes:
- "direct": ROOT handles it itself (general chat, simple questions, memory queries)
- "delegate": Send to a single specialist agent
- "multi": Break into subtasks for multiple agents"""


class TaskRouter:
    """Routes incoming requests to the appropriate agent(s)."""

    def __init__(self, llm: LLMService, registry: AgentRegistry) -> None:
        self._llm = llm
        self._registry = registry

    async def route(self, user_message: str, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Determine how to handle a user request."""
        agents = self._registry.list_agents()
        agents_desc = "\n".join(
            f"- {a.id}: {a.name} ({a.role}) — {a.description}"
            for a in agents
        )

        prompt = f"""Available agents:
{agents_desc}

User request: {user_message}

{"Context: " + json.dumps(context) if context else ""}

How should ROOT handle this?"""

        response = await self._llm.complete(
            system=ROUTER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            temperature=0.3,
        )

        try:
            text = response.strip()
            if "```" in text:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                text = text[start:end].strip()
            return json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Router JSON parse failed: %s. Response: %s", exc, response[:200])
            return {"route": "direct", "agent_ids": [], "reasoning": f"Fallback: {exc}"}
