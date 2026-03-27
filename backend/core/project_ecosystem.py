"""
Project Ecosystem Engine — ROOT's awareness of Yohan's entire project portfolio.

Scans the Desktop for projects, extracts metadata, and stores knowledge
so ROOT can correlate across ventures, suggest synergies, and track status.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import DATA_DIR

ECOSYSTEM_DB = DATA_DIR / "ecosystem.db"

logger = logging.getLogger("root.ecosystem")


@dataclass(frozen=True)
class Project:
    """Immutable project record."""
    id: str
    name: str
    path: str
    project_type: str  # "fastapi", "node", "data", "docs", "business"
    description: str = ""
    tech_stack: tuple[str, ...] = ()
    revenue_stream: str = ""  # Maps to RevenueStream if applicable
    status: str = "active"  # "active", "archived", "idea"
    port: Optional[int] = None
    connections: tuple[str, ...] = ()  # IDs of related projects
    last_scanned: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: dict[str, Any] = field(default_factory=dict)


# ── Known projects (discovered via filesystem scan) ───────────

KNOWN_PROJECTS: list[dict[str, Any]] = [
    {
        "name": "ROOT",
        "path": "~/Desktop/ROOT",
        "project_type": "fastapi",
        "description": "162+ agent AI civilization — core autonomous intelligence system. "
                       "FastAPI backend with 40+ modules, 18 SQLite databases, 3-layer memory, "
                       "hedge fund, revenue engine, experiment lab, directive engine.",
        "tech_stack": ("Python", "FastAPI", "SQLite", "OpenAI", "Anthropic", "DeepSeek"),
        "revenue_stream": "ai_consulting",
        "port": 9000,
        "status": "active",
    },
    {
        "name": "Onsite",
        "path": "~/Desktop/Onsite",
        "project_type": "fastapi",
        "description": "Production lead generation platform — real estate lead enrichment "
                       "with PropertyReach API, ATTOM property data, Google OAuth, "
                       "census integration, geocoding. 5000 lead limit, 60-day freshness.",
        "tech_stack": ("Python", "FastAPI", "React", "PropertyReach", "ATTOM", "Socrata"),
        "revenue_stream": "data_products",
        "status": "active",
    },
    {
        "name": "OI-Astra",
        "path": "~/Desktop/OI-Astra",
        "project_type": "node",
        "description": "13-agent AI command center — strategic trading automation with "
                       "mission decomposition, real-time WebSocket ops. Robinhood + Polymarket "
                       "integration. TradingView webhooks. Stripe payments.",
        "tech_stack": ("Node.js", "Express", "WebSocket", "SQLite", "Robinhood", "Polymarket"),
        "revenue_stream": "automation_agency",
        "port": 5555,
        "status": "active",
    },
    {
        "name": "API-Data",
        "path": "~/Desktop/API",
        "project_type": "data",
        "description": "1.2GB dataset repository — US construction permit APIs by ZIP code, "
                       "property data, parcel records. 600MB+ consolidated data files. "
                       "OpenClaw all-ZIP data sources.",
        "tech_stack": ("CSV", "JSON"),
        "revenue_stream": "data_products",
        "status": "active",
    },
    {
        "name": "Kimi-Agents",
        "path": "~/Desktop/Kimi_Agent_Free US Lead Coverage",
        "project_type": "docs",
        "description": "Free US lead coverage research — commercial lead data APIs, "
                       "government data sources, web scraping strategies. Comprehensive "
                       "documentation of free public data for lead generation.",
        "tech_stack": ("Markdown",),
        "revenue_stream": "data_products",
        "status": "active",
    },
    {
        "name": "Adama-Village",
        "path": "~/Desktop/Adama",
        "project_type": "business",
        "description": "Costa Rica resort/property development — Adama Village. "
                       "Pitch deck, financial model, location documentation. "
                       "Real estate investment venture.",
        "tech_stack": ("Excel", "PowerPoint", "PDF"),
        "revenue_stream": "",
        "status": "active",
    },
    {
        "name": "Zinque",
        "path": "~/Desktop/Zinque",
        "project_type": "business",
        "description": "Restaurant operations management — health inspections, "
                       "employee management, food handler certs, compliance docs. "
                       "Active business requiring operational oversight.",
        "tech_stack": ("PDF", "Docs"),
        "revenue_stream": "",
        "status": "active",
    },
    {
        "name": "CLAWBOT-V2",
        "path": "~/Desktop/CLAWBOT_V2",
        "project_type": "node",
        "description": "Secondary autonomous research agent on port 6000 — "
                       "web research, shell execution, file access, API integrations. "
                       "Can communicate with OI-Astra.",
        "tech_stack": ("Node.js", "Express", "Anthropic"),
        "revenue_stream": "automation_agency",
        "port": 6000,
        "status": "active",
    },
    {
        "name": "OpenClaw",
        "path": "~/Desktop/openclaw",
        "project_type": "node",
        "description": "9-stage data discovery service — systematic public data source "
                       "identification and validation pipeline.",
        "tech_stack": ("Node.js", "Express"),
        "revenue_stream": "data_products",
        "status": "active",
    },
]

# ── Cross-project connections ─────────────────────────────────

PROJECT_CONNECTIONS: list[tuple[str, str, str]] = [
    ("ROOT", "OI-Astra", "ROOT orchestrates strategy, OI-Astra executes trades"),
    ("ROOT", "Onsite", "ROOT's revenue engine tracks Onsite as data product"),
    ("ROOT", "OpenClaw", "ROOT's OpenClaw agent mirrors the standalone service"),
    ("Onsite", "API-Data", "Onsite uses API-Data's property/permit datasets"),
    ("Onsite", "Kimi-Agents", "Kimi research feeds Onsite's lead sources"),
    ("OI-Astra", "CLAWBOT-V2", "CLAWBOT communicates with OI-Astra on port 5555"),
    ("API-Data", "OpenClaw", "OpenClaw discovers data sources stored in API-Data"),
    ("API-Data", "Kimi-Agents", "Kimi agents collect data catalogued in API-Data"),
]


class ProjectEcosystem:
    """Tracks and correlates Yohan's project portfolio."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or ECOSYSTEM_DB)
        self._conn: Optional[sqlite3.Connection] = None
        self._projects: dict[str, Project] = {}

    def start(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        self._load_known_projects()
        logger.info("ProjectEcosystem started: %d projects tracked", len(self._projects))

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("ProjectEcosystem not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                path TEXT NOT NULL,
                project_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                tech_stack TEXT DEFAULT '[]',
                revenue_stream TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                port INTEGER,
                connections TEXT DEFAULT '[]',
                last_scanned TEXT NOT NULL,
                metrics TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS project_events (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pe_project ON project_events(project_id);
            CREATE INDEX IF NOT EXISTS idx_pe_type ON project_events(event_type);
        """)

    def _load_known_projects(self) -> None:
        """Seed database with known projects if not already present."""
        for proj_data in KNOWN_PROJECTS:
            name = proj_data.get("name", "")
            existing = self.conn.execute(
                "SELECT id FROM projects WHERE name = ?", (name,)
            ).fetchone()

            if existing:
                self._projects[name] = self._row_to_project(
                    self.conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
                )
                continue

            proj_id = f"proj_{uuid.uuid4().hex[:8]}"
            now = datetime.now(timezone.utc).isoformat()

            self.conn.execute(
                """INSERT INTO projects
                   (id, name, path, project_type, description, tech_stack,
                    revenue_stream, status, port, connections, last_scanned, metrics)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, '{}')""",
                (
                    proj_id, name, proj_data.get("path", ""), proj_data.get("project_type", "unknown"),
                    proj_data.get("description", ""), json.dumps(proj_data.get("tech_stack", [])),
                    proj_data.get("revenue_stream", ""), proj_data.get("status", "active"),
                    proj_data.get("port"), now,
                ),
            )

            self._projects[name] = Project(
                id=proj_id, name=name, path=proj_data.get("path", ""),
                project_type=proj_data.get("project_type", "unknown"),
                description=proj_data.get("description", ""),
                tech_stack=tuple(proj_data.get("tech_stack", [])),
                revenue_stream=proj_data.get("revenue_stream", ""),
                status=proj_data.get("status", "active"),
                port=proj_data.get("port"),
                last_scanned=now,
            )

        self.conn.commit()

    # ── Queries ────────────────────────────────────────────────

    def get_all_projects(self) -> list[Project]:
        rows = self.conn.execute(
            "SELECT * FROM projects ORDER BY name"
        ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def get_project(self, name: str) -> Optional[Project]:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def get_by_revenue_stream(self, stream: str) -> list[Project]:
        rows = self.conn.execute(
            "SELECT * FROM projects WHERE revenue_stream = ?", (stream,)
        ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def get_connections(self) -> list[dict[str, str]]:
        """Return all known project interconnections."""
        return [
            {"source": src, "target": tgt, "description": desc}
            for src, tgt, desc in PROJECT_CONNECTIONS
        ]

    def get_ecosystem_summary(self) -> dict[str, Any]:
        """Full ecosystem overview for ROOT's context."""
        projects = self.get_all_projects()
        by_type = {}
        by_stream = {}
        for p in projects:
            by_type[p.project_type] = by_type.get(p.project_type, 0) + 1
            if p.revenue_stream:
                by_stream[p.revenue_stream] = by_stream.get(p.revenue_stream, [])
                by_stream[p.revenue_stream].append(p.name)

        return {
            "total_projects": len(projects),
            "by_type": by_type,
            "by_revenue_stream": by_stream,
            "connections": len(PROJECT_CONNECTIONS),
            "active_ports": {p.name: p.port for p in projects if p.port},
            "tech_stack_coverage": list(set(
                tech for p in projects for tech in p.tech_stack
            )),
        }

    def record_event(self, project_name: str, event_type: str, description: str) -> None:
        """Record a project event (deployment, update, revenue, issue)."""
        proj = self.get_project(project_name)
        if not proj:
            logger.warning("Unknown project: %s", project_name)
            return

        event_id = f"evt_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO project_events (id, project_id, event_type, description, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, proj.id, event_type, description, now),
        )
        self.conn.commit()

    def get_context_for_brain(self) -> str:
        """Generate ecosystem context string for injection into ASTRA/Brain prompts."""
        projects = self.get_all_projects()
        lines = ["Yohan's active project ecosystem:"]
        for p in projects:
            port_str = f" (port {p.port})" if p.port else ""
            rev_str = f" [{p.revenue_stream}]" if p.revenue_stream else ""
            lines.append(f"- {p.name}{port_str}{rev_str}: {p.description[:120]}")

        lines.append("\nProject connections:")
        for src, tgt, desc in PROJECT_CONNECTIONS:
            lines.append(f"- {src} ↔ {tgt}: {desc}")

        return "\n".join(lines)

    def stats(self) -> dict[str, Any]:
        return self.get_ecosystem_summary()

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        tech = json.loads(row["tech_stack"]) if row["tech_stack"] else []
        conns = json.loads(row["connections"]) if row["connections"] else []
        metrics = json.loads(row["metrics"]) if row["metrics"] else {}
        return Project(
            id=row["id"], name=row["name"], path=row["path"],
            project_type=row["project_type"],
            description=row["description"] or "",
            tech_stack=tuple(tech), revenue_stream=row["revenue_stream"] or "",
            status=row["status"] or "active", port=row["port"],
            connections=tuple(conns), last_scanned=row["last_scanned"] or "",
            metrics=metrics,
        )
