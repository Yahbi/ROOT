"""
OpenClaw Connector — HTTP-based connector to the OpenClaw data discovery gateway.

OpenClaw is a Node.js service (Express) that provides:
  - Lead data management (permits, parcels, building records)
  - AI chat interface (forwards to OI-Astra or OpenAI)
  - Service health monitoring (permit-pulse, oi-astra, adama)
  - CSV export of enriched building/permit data

The deep-search subsystem (Python scripts) handles autonomous data discovery:
  - OpenStreetMap building scraping
  - Geocoding via BAN (Base d'Adresses Nationale)
  - Company lookup via recherche-entreprises API
  - Spatial join with fuel stations & ICPE data

This connector lets ROOT command OpenClaw as a Tier 2 agent via HTTP.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from backend.config import OPENCLAW_URL

logger = logging.getLogger("root.connectors.openclaw")

# Timeout for HTTP requests to OpenClaw
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class OpenClawConnector:
    """Connector for ROOT to command OpenClaw via its HTTP API."""

    def __init__(self) -> None:
        self._available: bool | None = None
        self._learning = None  # Late-bound LearningEngine
        self._base_url: str = OPENCLAW_URL.rstrip("/")

    def set_learning(self, learning) -> None:
        """Late-bind learning engine for outcome tracking."""
        self._learning = learning

    async def health_check(self) -> dict[str, Any]:
        """Check if OpenClaw gateway is reachable."""
        available = await self._check_available()
        if available:
            return {"status": "online", "type": "openclaw", "agent": "openclaw"}
        return {
            "status": "offline",
            "reason": f"OpenClaw not reachable at {self._base_url}",
        }

    async def send_task(self, task: str) -> dict[str, Any]:
        """Route a task description to the appropriate OpenClaw operation.

        Supported intents (parsed from natural language):
        - "status" / "health" / "services"  → service health check
        - "leads" / "data" / "buildings"     → fetch lead summary
        - "export" / "download" / "csv"      → export lead data
        - "reload" / "refresh"               → reload CSV data
        - "stats" / "report" / "summary"     → system statistics
        - "chat" / "ask" / "query"           → forward to AI chat
        - anything else                      → forward to AI chat
        """
        # Reset availability cache so we recheck each task
        self._available = None
        available = await self._check_available()
        if not available:
            return {"error": f"OpenClaw not available at {self._base_url}"}

        task_lower = task.lower()

        try:
            if any(kw in task_lower for kw in ("service", "health", "ping", "alive")):
                return await self._get_services()

            if any(kw in task_lower for kw in ("lead", "data", "building", "permit", "parcel")):
                return await self._get_leads_summary()

            if any(kw in task_lower for kw in ("export", "download", "csv")):
                return await self._get_leads_summary()

            if any(kw in task_lower for kw in ("reload", "refresh", "reindex")):
                return await self._reload_leads()

            if any(kw in task_lower for kw in ("stats", "report", "summary", "status")):
                return await self._get_stats()

            # Default: forward to OpenClaw's AI chat
            return await self._chat(task)

        except Exception as exc:
            logger.error("OpenClaw task failed: %s", exc)
            if self._learning:
                self._learning.record_agent_outcome(
                    agent_id="openclaw",
                    task_description=f"task failed: {task[:100]}",
                    status="failed",
                    result_quality=0.0,
                    task_category="data_discovery",
                    error_message=str(exc)[:300],
                )
            return {"error": f"OpenClaw execution failed: {exc}"}

    # ── HTTP operations ────────────────────────────────────────────

    async def _check_available(self) -> bool:
        """Check if OpenClaw gateway responds to /api/health."""
        if self._available is not None:
            return self._available

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{self._base_url}/api/health")
                self._available = resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            self._available = False

        return self._available

    async def _get(self, path: str) -> dict[str, Any]:
        """GET request to OpenClaw API."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self._base_url}{path}")
            resp.raise_for_status()
            data = resp.json()
            return self._check_upstream_error(data)

    async def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST request to OpenClaw API."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{self._base_url}{path}", json=json or {})
            resp.raise_for_status()
            data = resp.json()
            return self._check_upstream_error(data)

    @staticmethod
    def _check_upstream_error(data: dict[str, Any]) -> dict[str, Any]:
        """Detect upstream errors forwarded through OpenClaw and raise cleanly."""
        if isinstance(data, dict) and "error" in data and len(data) == 1:
            raise RuntimeError(f"OpenClaw upstream error: {data['error']}")
        return data

    async def _get_services(self) -> dict[str, Any]:
        """Get OpenClaw service status."""
        data = await self._get("/api/services")
        services = data.get("services", [])
        lines = ["## OpenClaw Services\n"]
        for svc in services:
            status = svc.get("status", "unknown")
            name = svc.get("name", "?")
            url = svc.get("url", "?")
            lines.append(f"- **{name}**: {status} ({url})")

        return self._format_result("\n".join(lines), raw=data, tool="openclaw_services")

    async def _get_leads_summary(self) -> dict[str, Any]:
        """Get leads/data summary from OpenClaw."""
        data = await self._get("/api/leads/summary")
        lines = ["## OpenClaw Data Summary\n"]
        for key, value in data.items():
            if isinstance(value, (int, float)):
                lines.append(f"- **{key}**: {value:,}")
            else:
                lines.append(f"- **{key}**: {value}")

        return self._format_result("\n".join(lines), raw=data, tool="openclaw_leads")

    async def _reload_leads(self) -> dict[str, Any]:
        """Reload CSV data in OpenClaw."""
        data = await self._post("/api/leads/reload")
        return self._format_result(
            f"OpenClaw data reloaded: {data}",
            raw=data,
            tool="openclaw_reload",
        )

    async def _get_stats(self) -> dict[str, Any]:
        """Get OpenClaw system statistics."""
        data = await self._get("/api/stats")
        lines = ["## OpenClaw Statistics\n"]
        for key, value in data.items():
            lines.append(f"- **{key}**: {value}")

        return self._format_result("\n".join(lines), raw=data, tool="openclaw_stats")

    async def _chat(self, message: str) -> dict[str, Any]:
        """Forward a message to OpenClaw's AI chat."""
        data = await self._post("/api/chat", json={"message": message})
        reply = data.get("reply", data.get("response", str(data)))

        if self._learning:
            self._learning.record_agent_outcome(
                agent_id="openclaw",
                task_description=f"chat: {message[:100]}",
                status="completed",
                result_quality=0.6,
                task_category="data_discovery",
            )

        return self._format_result(
            str(reply)[:5000],
            raw=data,
            tool="openclaw_chat",
        )

    # ── Convenience methods (callable directly by orchestrator) ────

    async def run_gaps(self) -> dict[str, Any]:
        """Get data coverage gaps."""
        return await self._get_leads_summary()

    async def run_discovery(self) -> dict[str, Any]:
        """Trigger data discovery."""
        return await self._chat("discover new data sources for permits and parcels")

    async def run_health(self) -> dict[str, Any]:
        """Check service health."""
        return await self._get_services()

    async def run_scoring(self) -> dict[str, Any]:
        """Get data quality stats."""
        return await self._get_stats()

    async def run_experiments(self) -> dict[str, Any]:
        """Run experiment cycle."""
        return await self._chat("run experiment cycle for data quality improvement")

    async def run_full(self, dry_run: bool = False) -> dict[str, Any]:
        """Run a full status + data summary cycle."""
        services = await self._get_services()
        summary = await self._get_leads_summary()
        stats = await self._get_stats()

        combined = (
            f"{services.get('result', '')}\n\n"
            f"{summary.get('result', '')}\n\n"
            f"{stats.get('result', '')}"
        )

        return self._format_result(
            combined,
            raw={
                "services": services.get("raw", {}),
                "leads": summary.get("raw", {}),
                "stats": stats.get("raw", {}),
            },
            tool="openclaw_full_cycle",
        )

    # ── Formatting ────────────────────────────────────────────────

    @staticmethod
    def _format_result(
        text: str,
        raw: dict[str, Any] | None = None,
        tool: str = "openclaw",
    ) -> dict[str, Any]:
        """Standard result envelope."""
        return {
            "agent": "openclaw",
            "result": text,
            "raw": raw or {},
            "messages_exchanged": 0,
            "tools_executed": 1,
            "tools_used": [tool],
        }
