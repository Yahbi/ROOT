"""Shared utilities for agent connectors."""

from __future__ import annotations

from typing import Any


def sanitize_tool_output(output: Any) -> Any:
    """Detect upstream error JSON in tool output and wrap it human-readably.

    Upstream services sometimes return raw ``{"error": "..."}`` dicts that
    would otherwise be passed through verbatim to the LLM and ultimately
    to the user.  This helper detects that pattern and converts it to a
    friendlier message the LLM can reason about.
    """
    if isinstance(output, dict):
        # Single-key {"error": "..."} — classic upstream error envelope
        if "error" in output and len(output) == 1:
            msg = str(output["error"])
            return {
                "status": "upstream_error",
                "message": f"Service temporarily unavailable: {msg}",
                "original_error": msg,
            }
        # Nested error field inside a larger response — flag but keep data
        if "error" in output and output["error"]:
            output = dict(output)  # shallow copy — don't mutate
            output["_upstream_warning"] = (
                "This response contains an error field — "
                "the upstream service may be partially degraded."
            )
    return output
