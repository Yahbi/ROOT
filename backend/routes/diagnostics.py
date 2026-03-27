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
    engine = DiagnosticsEngine(request.app.state)
    report = await engine.run_full()
    return {
        "timestamp": report["timestamp"],
        "duration_ms": report["duration_ms"],
        "summary": report["summary"],
        "by_category": report["by_category"],
        "failures": report["failures"],
        "warnings": report["warnings"],
    }
