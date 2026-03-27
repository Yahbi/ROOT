"""API routes for Project Ecosystem — cross-project awareness."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])


@router.get("/projects")
async def list_projects(request: Request) -> JSONResponse:
    """List all tracked projects in Yohan's ecosystem."""
    eco = getattr(request.app.state, "ecosystem", None)
    if not eco:
        return JSONResponse({"error": "ecosystem not available"}, status_code=503)

    projects = eco.get_all_projects()
    return JSONResponse({
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "path": p.path,
                "type": p.project_type,
                "description": p.description,
                "tech_stack": list(p.tech_stack),
                "revenue_stream": p.revenue_stream,
                "status": p.status,
                "port": p.port,
            }
            for p in projects
        ],
        "total": len(projects),
    })


@router.get("/connections")
async def list_connections(request: Request) -> JSONResponse:
    """List all cross-project connections."""
    eco = getattr(request.app.state, "ecosystem", None)
    if not eco:
        return JSONResponse({"error": "ecosystem not available"}, status_code=503)

    return JSONResponse({
        "connections": eco.get_connections(),
        "total": len(eco.get_connections()),
    })


@router.get("/summary")
async def ecosystem_summary(request: Request) -> JSONResponse:
    """Full ecosystem overview — types, revenue streams, tech stack."""
    eco = getattr(request.app.state, "ecosystem", None)
    if not eco:
        return JSONResponse({"error": "ecosystem not available"}, status_code=503)

    return JSONResponse(eco.get_ecosystem_summary())


@router.get("/context")
async def brain_context(request: Request) -> JSONResponse:
    """Get ecosystem context string for ASTRA/Brain injection."""
    eco = getattr(request.app.state, "ecosystem", None)
    if not eco:
        return JSONResponse({"error": "ecosystem not available"}, status_code=503)

    return JSONResponse({"context": eco.get_context_for_brain()})
