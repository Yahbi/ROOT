"""Sandbox Gate API — control sandbox/live mode for ROOT subsystems."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.core.sandbox_gate import SystemMode
from backend.core.action_categories import ActionCategory, LIVE_MODE_POLICIES

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


def _get_gate(request: Request):
    """Retrieve the SandboxGate from app state."""
    gate = getattr(request.app.state, "sandbox_gate", None)
    if gate is None:
        raise HTTPException(status_code=503, detail="Sandbox gate not initialized")
    return gate


# ── Request Models ─────────────────────────────────────────────


class ModeUpdate(BaseModel):
    """Request body for updating mode."""
    mode: str  # "sandbox" or "live"


class GoLiveConfirmation(BaseModel):
    """Request body for go-live with explicit confirmation."""
    confirm: bool = False


# ── Routes ─────────────────────────────────────────────────────


@router.get("/status")
async def get_status(request: Request):
    """Get full sandbox status: global mode, all system modes, stats."""
    gate = _get_gate(request)
    return gate.get_status()


@router.patch("/mode")
async def set_global_mode(request: Request, body: ModeUpdate):
    """Set the global operating mode (sandbox or live)."""
    gate = _get_gate(request)
    try:
        mode = SystemMode(body.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{body.mode}'. Must be 'sandbox' or 'live'.",
        )
    config = gate.set_global_mode(mode)
    return {
        "global_mode": config.global_mode.value,
        "updated_at": config.updated_at,
        "message": f"Global mode set to {mode.value}",
    }


@router.patch("/system/{system_id}")
async def set_system_mode(request: Request, system_id: str, body: ModeUpdate):
    """Set the mode for a specific subsystem."""
    gate = _get_gate(request)
    try:
        mode = SystemMode(body.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{body.mode}'. Must be 'sandbox' or 'live'.",
        )
    config = gate.set_system_mode(system_id, mode)
    effective = gate.get_effective_mode(system_id)
    return {
        "system_id": system_id,
        "mode": effective.value,
        "global_mode": config.global_mode.value,
        "updated_at": config.updated_at,
        "message": f"System '{system_id}' set to {mode.value}",
    }


@router.post("/go-live")
async def go_live(request: Request, body: GoLiveConfirmation):
    """Switch global mode to LIVE with explicit confirmation.

    Requires confirm=true in the body to prevent accidental activation.
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="You must set confirm=true to switch to LIVE mode. "
                   "This gives ROOT full autonomous access to all external systems.",
        )
    gate = _get_gate(request)
    config = gate.set_global_mode(SystemMode.LIVE)
    return {
        "global_mode": config.global_mode.value,
        "updated_at": config.updated_at,
        "message": "ROOT is now LIVE. All subsystems have full autonomous access.",
        "warning": "Owner notifications remain active for all decisions.",
    }


@router.get("/decisions")
async def get_decisions(
    request: Request,
    system_id: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = 50,
):
    """Get recent gate decisions with optional filters."""
    gate = _get_gate(request)
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 500")
    decisions = gate.get_decisions(system_id=system_id, mode=mode, limit=limit)
    return {"decisions": decisions, "count": len(decisions)}


@router.get("/decisions/stats")
async def get_decision_stats(request: Request):
    """Get aggregate statistics about gate decisions."""
    gate = _get_gate(request)
    return gate.get_decision_stats()


@router.get("/blocked-intents")
async def get_blocked_intents(request: Request, limit: int = 50):
    """Get recent actions blocked by sandbox mode — shows ROOT's intent."""
    gate = _get_gate(request)
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 500")
    decisions = gate.get_decisions(mode="sandbox", limit=limit)
    return {"blocked_intents": decisions, "count": len(decisions)}


@router.get("/categories")
async def get_categories(request: Request):
    """Get action category policies for live mode."""
    return {
        "categories": {
            cat.value: {
                "requires_approval": policy.requires_approval,
                "notification_level": policy.notification_level,
                "auto_execute_delay_seconds": policy.auto_execute_delay_seconds,
            }
            for cat, policy in LIVE_MODE_POLICIES.items()
        },
    }


@router.get("/pending-approvals")
async def get_pending_approvals(request: Request):
    """Get pending approval requests that require owner action."""
    approval = getattr(request.app.state, "approval", None)
    if not approval:
        return {"pending": [], "count": 0}
    pending = approval.get_pending()
    return {
        "pending": [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "action": r.action,
                "description": r.description,
                "risk_level": r.risk_level.value,
                "reason": getattr(r, "reason", None),
                "benefit": getattr(r, "benefit", None),
                "risk_analysis": getattr(r, "risk_analysis", None),
                "created_at": r.created_at,
            }
            for r in pending
        ],
        "count": len(pending),
    }


@router.post("/approve/{approval_id}")
async def approve_request(request: Request, approval_id: str):
    """Approve a pending request."""
    approval = getattr(request.app.state, "approval", None)
    if not approval:
        raise HTTPException(status_code=503, detail="Approval chain not initialized")
    try:
        result = approval.approve(approval_id, resolver="yohan")
        return {"status": "approved", "id": approval_id}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/reject/{approval_id}")
async def reject_request(request: Request, approval_id: str):
    """Reject a pending request."""
    approval = getattr(request.app.state, "approval", None)
    if not approval:
        raise HTTPException(status_code=503, detail="Approval chain not initialized")
    try:
        result = approval.reject(approval_id, resolver="yohan")
        return {"status": "rejected", "id": approval_id}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
