"""Standard API response envelope for ROOT.

All API endpoints should return responses wrapped in this envelope
for consistent error handling and metadata across the platform.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Response metadata."""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])


class APIResponse(BaseModel):
    """Standard API response envelope.

    Usage:
        return APIResponse.ok(data={"items": [...]})
        return APIResponse.error("Not found", status=404)
    """
    success: bool
    data: Any = None
    error_message: Optional[str] = Field(None, alias="error")
    meta: ResponseMeta = Field(default_factory=ResponseMeta)

    model_config = {"populate_by_name": True}

    @classmethod
    def ok(cls, data: Any = None, **kwargs: Any) -> "APIResponse":
        return cls(success=True, data=data, **kwargs)

    @classmethod
    def fail(cls, message: str, **kwargs: Any) -> "APIResponse":
        return cls(success=False, error_message=message, **kwargs)
