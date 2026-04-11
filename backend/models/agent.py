"""Immutable agent data models."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    REFLECTING = "reflecting"
    ERROR = "error"
    OFFLINE = "offline"


class AgentCapability(BaseModel):
    """A single capability an agent possesses."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentProfile(BaseModel):
    """Immutable agent definition."""

    id: str = Field(min_length=1)
    name: str
    role: str
    description: str
    tier: int = Field(default=2, ge=0, le=2)  # 0=God(Yohan), 1=ROOT, 2=Worker
    capabilities: list[AgentCapability] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    tasks_completed: int = 0
    connector_type: Optional[str] = None  # "hermes", "astra", "miro", "swarm", "internal"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRequest(BaseModel):
    """A task dispatched to an agent."""

    id: Optional[str] = None
    description: str
    assigned_to: Optional[str] = None  # Agent ID
    priority: int = 5                   # 1=critical, 10=low
    context: dict[str, Any] = Field(default_factory=dict)
    parent_task_id: Optional[str] = None
    status: str = "pending"
    result: Optional[str] = None


class AgentFinding(BaseModel):
    """Result from a single agent's work on a dispatched task."""

    agent_id: str
    agent_name: str
    task: str
    result: str
    status: str = "completed"  # completed | failed
    duration_seconds: float = 0.0
    messages_exchanged: int = 0      # LLM round-trips
    tools_executed: int = 0          # Total tool invocations
    tools_used: list[str] = Field(default_factory=list)  # Tool names used


class ChatMessage(BaseModel):
    """A message in conversation."""

    role: str                        # "user" (Yohan) or "assistant" (ROOT)
    content: str
    agent_id: Optional[str] = None   # Which agent responded
    memories_used: list[str] = Field(default_factory=list)
    agents_used: list[str] = Field(default_factory=list)
    agent_findings: list[AgentFinding] = Field(default_factory=list)
    route: str = "direct"            # direct | delegate | multi
    timestamp: Optional[str] = None
    total_messages_exchanged: int = 0
    total_tools_executed: int = 0
    routing_reasoning: str = ""         # ASTRA's short reasoning for the route
    routing_explanation: str = ""       # Human-readable explanation of routing decision
    routing_confidence: float = 1.0     # ASTRA's confidence in the routing (0.0–1.0)
    response_quality_score: float = 0.0 # Self-evaluated quality score (0.0–1.0)
