"""
Prometheus and JSON metrics endpoints.
"""

from fastapi import APIRouter, Request, Response

from backend.core.metrics import MetricsRegistry

router = APIRouter(tags=["metrics"])


def _get_registry(request: Request) -> MetricsRegistry:
    """Return the shared registry from app state, creating one only if needed."""
    existing = getattr(request.app.state, "metrics", None)
    if existing is not None:
        return existing
    registry = MetricsRegistry()
    request.app.state.metrics = registry
    return registry


@router.get("/metrics")
async def prometheus_metrics(request: Request) -> Response:
    """Expose metrics in Prometheus text exposition format."""
    registry = _get_registry(request)
    return Response(
        content=registry.collect(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/api/metrics/json")
async def json_metrics(request: Request) -> dict:
    """Expose metrics as a JSON-friendly dict."""
    registry = _get_registry(request)
    return registry.to_dict()
