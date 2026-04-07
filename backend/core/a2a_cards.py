"""
A2A (Agent-to-Agent) Protocol Support — Agent Card generation.

Implements Google's A2A protocol (v0.3, Linux Foundation) for ROOT's agents.
Each agent publishes a structured Agent Card (JSON) describing its capabilities,
enabling external agent systems to discover and collaborate with ROOT.

Spec: https://a2a-protocol.org/latest/specification/
"""

from __future__ import annotations

import logging
from typing import Any

from backend.config import VERSION

logger = logging.getLogger("root.a2a")


def generate_agent_card(
    agent_id: str,
    name: str,
    description: str,
    role: str,
    capabilities: list[dict[str, Any]],
    *,
    base_url: str = "http://localhost:9000",
) -> dict[str, Any]:
    """Generate an A2A Agent Card for a single ROOT agent."""
    skills = []
    for cap in capabilities:
        skills.append({
            "id": f"root.{agent_id}.{cap.get('name', 'default')}",
            "name": cap.get("name", ""),
            "description": cap.get("description", ""),
        })

    # If no explicit capabilities, derive a default skill from the role
    if not skills:
        skills.append({
            "id": f"root.{agent_id}.default",
            "name": role,
            "description": description,
        })

    return {
        "name": name,
        "description": description,
        "url": f"{base_url}/api/a2a",
        "version": VERSION,
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": skills,
        "metadata": {
            "agent_id": agent_id,
            "role": role,
            "provider": "ROOT Intelligence Civilization",
        },
    }


def generate_root_agent_card(
    agents: list[dict[str, Any]],
    *,
    base_url: str = "http://localhost:9000",
) -> dict[str, Any]:
    """Generate the top-level ROOT Agent Card for /.well-known/agent.json.

    This advertises ROOT as a whole — the combined capabilities of all agents.
    """
    all_skills = []
    for agent in agents[:50]:  # Cap at 50 to keep card reasonable
        all_skills.append({
            "id": f"root.{agent['id']}",
            "name": agent.get("name", agent["id"]),
            "description": agent.get("description", agent.get("role", "")),
        })

    return {
        "name": "ROOT Intelligence Civilization",
        "description": (
            f"ASTRA-ROOT v{VERSION} — Autonomous AI civilization with "
            f"{len(agents)} agents across 10 divisions. Capabilities include "
            "strategic reasoning, research, trading, coding, content creation, "
            "automation, and self-improvement."
        ),
        "url": f"{base_url}/api/a2a",
        "version": VERSION,
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": all_skills,
        "metadata": {
            "provider": "ROOT",
            "total_agents": len(agents),
            "protocol_version": "0.3",
        },
    }
