"""Network routes — agent network graph data for 3D visualization."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Path, Query, Request

logger = logging.getLogger("root.routes.network")

router = APIRouter(prefix="/api/network", tags=["network"])

# ── Division colors for visual grouping ───────────────────────────────

_DIVISION_COLORS: dict[str, str] = {
    "core": "#FFD700",
    "Strategy Council": "#FF6B6B",
    "Research Division": "#4ECDC4",
    "Engineering Division": "#45B7D1",
    "Data & Memory Division": "#96CEB4",
    "Learning & Improvement": "#FFEAA7",
    "Economic Engine": "#DDA0DD",
    "Content Network": "#98D8C8",
    "Automation Business": "#F7DC6F",
    "Infrastructure Operations": "#BB8FCE",
    "Governance & Safety": "#E74C3C",
}

# ── Core agent IDs ────────────────────────────────────────────────────

_CORE_IDS = frozenset({
    "astra", "root", "hermes", "miro", "swarm", "openclaw",
    "builder", "researcher", "coder", "writer", "analyst", "guardian",
})

# ── Hub agents that connect to all others ─────────────────────────────

_HUB_AGENTS = frozenset({"astra", "root"})


def _agent_division(agent_id: str, division_map: dict[str, list[str]]) -> str:
    """Determine which division an agent belongs to."""
    if agent_id in _CORE_IDS:
        return "core"
    for division_name, agent_ids in division_map.items():
        if agent_id in agent_ids:
            return division_name
    return "core"


def _build_division_map(registry) -> dict[str, list[str]]:
    """Build a mapping of division name to agent IDs."""
    result: dict[str, list[str]] = {}
    divisions = registry.list_divisions()
    for division_name in divisions:
        agents = registry.list_division(division_name)
        result[division_name] = [a.id for a in agents]
    return result


def _compute_activity_level(agent_id: str, learning) -> float:
    """Compute activity level (0-1) from learning engine data."""
    if not learning:
        return 0.3

    try:
        weights = learning.get_routing_weights()
        if agent_id in weights:
            weight = weights[agent_id]
            # Normalize weight to 0-1 range (weights are typically 0.5-2.0)
            return min(1.0, max(0.1, weight / 2.0))
    except Exception as exc:
        logger.warning("Failed to compute activity level for %s: %s", agent_id, exc)

    return 0.3


def _node_size(agent_id: str, tier: int) -> float:
    """Determine node size based on tier and role."""
    if agent_id in _HUB_AGENTS:
        return 3.0
    if tier <= 1:
        return 2.0
    if agent_id in _CORE_IDS:
        return 1.5
    return 1.0


def _build_nodes(
    registry, learning, division_map: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Build node list from all registered agents."""
    agents = registry.list_agents()
    nodes: list[dict[str, Any]] = []

    for agent in agents:
        division = _agent_division(agent.id, division_map)
        activity = _compute_activity_level(agent.id, learning)

        nodes.append({
            "id": agent.id,
            "name": agent.name,
            "role": agent.role,
            "division": division,
            "tier": agent.tier,
            "status": agent.status.value,
            "capabilities": [c.name for c in agent.capabilities],
            "connections": 0,  # Filled after edges are built
            "activity_level": round(activity, 2),
            "size": _node_size(agent.id, agent.tier),
            "tasks_completed": agent.tasks_completed,
        })

    return nodes


def _build_edges(
    registry, division_map: dict[str, list[str]], agent_network,
) -> list[dict[str, Any]]:
    """Build edge list from agent relationships and network insights."""
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _add_edge(source: str, target: str, weight: float, edge_type: str) -> None:
        key = (min(source, target), max(source, target))
        if key in seen:
            return
        seen.add(key)
        edges.append({
            "source": source,
            "target": target,
            "weight": round(weight, 2),
            "type": edge_type,
        })

    all_agent_ids = {a.id for a in registry.list_agents()}

    # Hub connections: ASTRA and ROOT connect to all core agents
    core_ids = _CORE_IDS & all_agent_ids
    for hub in _HUB_AGENTS:
        if hub not in all_agent_ids:
            continue
        for core_id in core_ids:
            if core_id != hub:
                _add_edge(hub, core_id, 1.0, "core")

    # Intra-division connections: agents within the same division
    for division_name, agent_ids in division_map.items():
        valid_ids = [aid for aid in agent_ids if aid in all_agent_ids]
        for i, aid_a in enumerate(valid_ids):
            # Connect each agent to the next few in the division (not all-to-all)
            for aid_b in valid_ids[i + 1: i + 4]:
                _add_edge(aid_a, aid_b, 0.5, "division")

    # Network insight edges: agents that share knowledge
    if agent_network:
        try:
            recent_insights = agent_network.get_all_recent(limit=100)
            for insight in recent_insights:
                source = insight.get("source_agent", "")
                targets = insight.get("relevance_agents", [])
                if source not in all_agent_ids:
                    continue
                for target in targets:
                    if target in all_agent_ids and target != source:
                        _add_edge(source, target, 0.7, "insight")
        except Exception as exc:
            logger.warning("Failed to read network insights for edges: %s", exc)

    return edges


def _fill_connection_counts(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return nodes with connection counts filled in (immutable pattern)."""
    counts: dict[str, int] = {}
    for edge in edges:
        counts[edge["source"]] = counts.get(edge["source"], 0) + 1
        counts[edge["target"]] = counts.get(edge["target"], 0) + 1

    return [
        {**node, "connections": counts.get(node["id"], 0)}
        for node in nodes
    ]


def _build_division_summaries(
    division_map: dict[str, list[str]],
) -> list[dict[str, str | int]]:
    """Build division summary list with colors and counts."""
    summaries: list[dict[str, str | int]] = []

    # Core division (always present)
    summaries.append({
        "id": "core",
        "name": "Core Agents",
        "count": len(_CORE_IDS),
        "color": _DIVISION_COLORS["core"],
    })

    for division_name, agent_ids in division_map.items():
        summaries.append({
            "id": division_name,
            "name": division_name,
            "count": len(agent_ids),
            "color": _DIVISION_COLORS.get(division_name, "#AAAAAA"),
        })

    return summaries


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/graph")
async def network_graph(request: Request):
    """Return nodes and edges for the agent network 3D visualization."""
    registry = request.app.state.registry
    learning = getattr(request.app.state, "learning", None)
    agent_network = getattr(request.app.state, "agent_network", None)

    division_map = _build_division_map(registry)
    nodes = _build_nodes(registry, learning, division_map)
    edges = _build_edges(registry, division_map, agent_network)
    nodes = _fill_connection_counts(nodes, edges)
    divisions = _build_division_summaries(division_map)

    total_agents = registry.agent_count()
    division_counts = registry.list_divisions()

    return {
        "nodes": nodes,
        "edges": edges,
        "divisions": divisions,
        "stats": {
            "total_agents": total_agents,
            "total_connections": len(edges),
            "divisions": len(division_counts) + 1,  # +1 for core
        },
    }


@router.get("/activity")
async def network_activity(request: Request):
    """Get recent agent activity for live pulse animation."""
    agent_network = getattr(request.app.state, "agent_network", None)
    learning = getattr(request.app.state, "learning", None)

    recent_insights: list[dict[str, Any]] = []
    if agent_network:
        try:
            recent_insights = agent_network.get_all_recent(limit=20)
        except Exception as exc:
            logger.warning("Failed to fetch recent insights: %s", exc)

    network_stats: dict[str, Any] = {}
    if agent_network:
        try:
            network_stats = agent_network.stats()
        except Exception as exc:
            logger.warning("Failed to fetch network stats: %s", exc)

    routing_weights: dict[str, float] = {}
    if learning:
        try:
            routing_weights = learning.get_routing_weights()
        except Exception as exc:
            logger.warning("Failed to fetch routing weights: %s", exc)

    return {
        "recent_insights": recent_insights,
        "network_stats": network_stats,
        "routing_weights": routing_weights,
    }


@router.get("/agent/{agent_id}/connections")
async def agent_connections(
    request: Request,
    agent_id: str = Path(..., min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get communication details for a specific agent — who it talks to and how."""
    registry = request.app.state.registry
    agent_network = getattr(request.app.state, "agent_network", None)
    collab = getattr(request.app.state, "collab", None)
    learning = getattr(request.app.state, "learning", None)

    agent = registry.get(agent_id)
    if not agent:
        return {"connections": [], "insights_shared": [], "collaborations": []}

    division_map = _build_division_map(registry)
    all_agent_ids = {a.id for a in registry.list_agents()}

    # ── 1. Structural connections (edges from graph) ──
    edges = _build_edges(registry, division_map, agent_network)
    connected_ids: dict[str, dict[str, Any]] = {}
    for edge in edges:
        peer_id = None
        if edge["source"] == agent_id:
            peer_id = edge["target"]
        elif edge["target"] == agent_id:
            peer_id = edge["source"]
        if peer_id and peer_id in all_agent_ids:
            if peer_id not in connected_ids:
                peer = registry.get(peer_id)
                connected_ids[peer_id] = {
                    "id": peer_id,
                    "name": peer.name if peer else peer_id,
                    "role": peer.role if peer else "",
                    "division": _agent_division(peer_id, division_map),
                    "edge_types": [],
                    "insights": [],
                    "collabs": [],
                }
            connected_ids[peer_id]["edge_types"].append(edge["type"])

    # ── 2. Insights shared between this agent and peers ──
    if agent_network:
        try:
            recent = agent_network.get_all_recent(limit=200)
            for insight in recent:
                src = insight.get("source_agent", "")
                relevance = insight.get("relevance_agents", [])
                if isinstance(relevance, str):
                    try:
                        relevance = json.loads(relevance)
                    except (json.JSONDecodeError, ValueError) as parse_err:
                        logger.warning("Failed to parse relevance_agents JSON for insight: %s", parse_err)
                        relevance = []

                # Insight FROM this agent TO others
                if src == agent_id:
                    for target in relevance:
                        if target in connected_ids:
                            connected_ids[target]["insights"].append({
                                "direction": "outgoing",
                                "type": insight.get("insight_type", ""),
                                "domain": insight.get("domain", ""),
                                "content": (insight.get("content", ""))[:200],
                                "confidence": insight.get("confidence", 0),
                                "created_at": insight.get("created_at", ""),
                            })

                # Insight TO this agent FROM others
                if agent_id in relevance and src != agent_id and src in connected_ids:
                    connected_ids[src]["insights"].append({
                        "direction": "incoming",
                        "type": insight.get("insight_type", ""),
                        "domain": insight.get("domain", ""),
                        "content": (insight.get("content", ""))[:200],
                        "confidence": insight.get("confidence", 0),
                        "created_at": insight.get("created_at", ""),
                    })
        except Exception as exc:
            logger.warning("Failed to fetch insights for %s: %s", agent_id, exc)

    # ── 3. Collaboration history involving this agent ──
    if collab:
        try:
            history = collab.get_history(limit=50)
            for wf in history:
                step_agents = [s.agent_id for s in wf.steps]
                if agent_id == wf.initiator or agent_id in step_agents:
                    for step_agent in step_agents:
                        if step_agent != agent_id and step_agent in connected_ids:
                            connected_ids[step_agent]["collabs"].append({
                                "pattern": wf.pattern.value,
                                "goal": (wf.goal or "")[:150],
                                "status": wf.status.value,
                                "role": "initiator" if wf.initiator == agent_id else "participant",
                                "created_at": wf.created_at,
                            })
        except Exception as exc:
            logger.warning("Failed to fetch collab history for %s: %s", agent_id, exc)

    # ── 4. Routing weight (how often this agent is selected) ──
    routing_weight = 0.0
    if learning:
        try:
            weights = learning.get_routing_weights()
            routing_weight = weights.get(agent_id, 0.0)
        except Exception:
            logger.debug("Exception suppressed", exc_info=True)
    # Sort by richest communication (most insights + collabs), then alphabetically
    connections = sorted(
        connected_ids.values(),
        key=lambda c: (len(c["insights"]) + len(c["collabs"]), c["name"]),
        reverse=True,
    )[:limit]

    # Deduplicate edge_types per connection
    for conn in connections:
        conn["edge_types"] = list(set(conn["edge_types"]))

    return {
        "agent_id": agent_id,
        "routing_weight": round(routing_weight, 3),
        "total_connections": len(connected_ids),
        "connections": connections,
    }
