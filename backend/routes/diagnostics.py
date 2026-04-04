"""Diagnostics API — comprehensive system health check."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.diagnostics import DiagnosticsEngine

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/full")
async def run_full_diagnostic(request: Request) -> dict:
    """Run comprehensive diagnostic across all ROOT subsystems."""
    engine = DiagnosticsEngine(request.app.state)
    report = await engine.run_full()
    return report


@router.get("/quick")
async def run_quick_diagnostic(request: Request) -> dict:
    """Quick health summary — core systems + LLM only."""
    import asyncio
    engine = DiagnosticsEngine(request.app.state)
    try:
        report = await asyncio.wait_for(engine.run_full(), timeout=15.0)
    except asyncio.TimeoutError:
        return {"timestamp": "", "duration_ms": 15000, "summary": {"total": 0, "passed": 0, "failed": 0, "warnings": 1, "health_pct": 0}, "by_category": {}, "failures": [], "warnings": ["Diagnostic timed out after 15s"]}
    return {
        "timestamp": report["timestamp"],
        "duration_ms": report["duration_ms"],
        "summary": report["summary"],
        "by_category": report["by_category"],
        "failures": report["failures"],
        "warnings": report["warnings"],
    }
