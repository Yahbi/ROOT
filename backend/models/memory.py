"""Immutable memory data models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    OBSERVATION = "observation"      # Something ROOT noticed
    LEARNING = "learning"            # A lesson learned from experience
    PREFERENCE = "preference"        # Yohan's preference
    SKILL = "skill"                  # A capability ROOT acquired
    REFLECTION = "reflection"        # Self-reflection insight
    FACT = "fact"                    # Verified factual knowledge
    GOAL = "goal"                    # Active goal or objective
    ERROR = "error"                  # Mistake to avoid repeating


class MemoryEntry(BaseModel):
    """Single memory entry — immutable after creation."""

    id: Optional[str] = None
    content: str
    memory_type: MemoryType
    tags: list[str] = Field(default_factory=list)
    source: str = "root"             # Which agent/system created it
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)  # 0.0–1.0, decays or strengthens over time
    access_count: int = 0            # How often this memory was retrieved
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed: Optional[str] = None
    superseded_by: Optional[str] = None  # ID of newer memory that replaces this


class MemoryQuery(BaseModel):
    """Query to search memories."""

    query: str
    memory_type: Optional[MemoryType] = None
    tags: list[str] = Field(default_factory=list)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = 20
    hybrid: bool = True  # Use hybrid FTS5+vector search when vector store is available


class Reflection(BaseModel):
    """A self-reflection entry — ROOT examining its own behavior."""

    id: Optional[str] = None
    trigger: str                     # What prompted the reflection
    observation: str                 # What ROOT observed about itself
    insight: str                     # The conclusion drawn
    action: Optional[str] = None     # What ROOT will do differently
    memories_referenced: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Enhanced fields added in v1.1
    topic: Optional[str] = None                   # Reflection topic/domain
    depth: str = "standard"                       # "standard" | "deep"
    quality_score: Optional[float] = None         # 0.0–1.0 actionability+impact rating
    quality_rationale: Optional[str] = None       # Why this score was given
    evidence: list[str] = Field(default_factory=list)   # Evidence items gathered (deep mode)
    parent_reflection_id: Optional[str] = None    # Previous reflection this chains from
    chain_depth: int = 0                          # How deep in a reflection chain
    archived: bool = False                        # Whether this has been archived
    key_takeaway: Optional[str] = None            # Summary takeaway for archive
    trend_tags: list[str] = Field(default_factory=list)  # Detected trend labels
