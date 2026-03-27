"""System, web, file, shell, and note-taking plugin builders."""

from __future__ import annotations

import asyncio
import logging
import platform
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from ddgs import DDGS

from backend.core.plugin_engine import Plugin, PluginTool

logger = logging.getLogger("root.plugins")


def register_system_plugins(engine, memory_engine=None, skill_engine=None) -> None:
    """Register system, web, file, shell, notes, and reminder plugins."""
    _register_system_info(engine)
    _register_web_tools(engine)
    _register_file_manager(engine)
    _register_notes(engine, memory_engine)
    _register_shell(engine)
    _register_reminders(engine)


# ── System Info Plugin ──────────────────────────────────────────


def _register_system_info(engine) -> None:
    def system_info(args):
        return {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": __import__("os").cpu_count(),
            "disk_free_gb": round(shutil.disk_usage("/").free / (1024**3), 1),
            "hostname": platform.node(),
        }

    def current_time(args):
        return {"time": datetime.now(timezone.utc).isoformat(), "local": datetime.now().isoformat()}

    engine.register(Plugin(
        id="system",
        name="System Tools",
        description="System information, time, and diagnostics",
        version="1.0.0",
        category="system",
        tags=["system", "diagnostics", "time"],
        tools=[
            PluginTool(
                name="system_info",
                description="Get system information (platform, CPU, disk, hostname)",
                handler=system_info,
                parameters={"type": "object", "properties": {}},
            ),
            PluginTool(
                name="current_time",
                description="Get current UTC and local time",
                handler=current_time,
                parameters={"type": "object", "properties": {}},
            ),
        ],
    ))


# ── Web Search Plugin ──────────────────────────────────────────


def _register_web_tools(engine) -> None:
    async def web_search(args):
        query = args.get("query", "")
        if not query:
            return {"error": "query is required"}
        try:
            def _search():
                return DDGS().text(query, max_results=5)
            raw_results = await asyncio.to_thread(_search)
            results = [
                {"title": r["title"], "url": r["href"], "snippet": r.get("body", "")}
                for r in raw_results
            ]
            return {"query": query, "results": results}
        except Exception as e:
            return {"query": query, "results": [], "error": str(e)}

    async def fetch_url(args):
        url = args.get("url", "")
        if not url:
            return {"error": "url is required"}
        max_chars = int(args.get("max_chars", 20000))
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                },
            )
            raw = resp.text[:max_chars * 2]
            # Remove script/style blocks
            cleaned = re.sub(r'<(script|style)[^>]*>[\s\S]*?</\1>', '', raw, flags=re.IGNORECASE)
            # Remove HTML tags
            cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
            # Collapse whitespace
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()[:max_chars]
            return {"url": url, "status": resp.status_code, "content": cleaned, "chars": len(cleaned)}

    engine.register(Plugin(
        id="web",
        name="Web Tools",
        description="Search the web and fetch URLs",
        version="1.0.0",
        category="research",
        tags=["web", "search", "fetch", "research"],
        tools=[
            PluginTool(
                name="web_search",
                description="Search the web using DuckDuckGo. Returns top 5 results.",
                handler=web_search,
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Search query"}},
                    "required": ["query"],
                },
            ),
            PluginTool(
                name="fetch_url",
                description="Fetch a URL, strip HTML, return clean text content (up to 20K chars)",
                handler=fetch_url,
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                        "max_chars": {"type": "integer", "description": "Max chars to return (default 20000)", "default": 20000},
                    },
                    "required": ["url"],
                },
            ),
        ],
    ))


# ── File Manager Plugin ────────────────────────────────────────


def _register_file_manager(engine) -> None:
    def list_files(args):
        directory = args.get("directory", ".")
        pattern = args.get("pattern", "*")
        try:
            p = Path(directory).resolve()
            files = sorted(p.glob(pattern))[:50]
            return {
                "directory": str(p),
                "files": [{"name": f.name, "is_dir": f.is_dir(), "size": f.stat().st_size if f.is_file() else 0} for f in files],
            }
        except Exception as e:
            return {"error": str(e)}

    def read_file(args):
        path = args.get("path", "")
        if not path:
            return {"error": "path is required"}
        try:
            content = Path(path).read_text(errors="replace")[:10000]
            return {"path": path, "content": content, "truncated": len(content) >= 10000}
        except Exception as e:
            return {"error": str(e)}

    engine.register(Plugin(
        id="files",
        name="File Manager",
        description="List and read files on the local filesystem",
        version="1.0.0",
        category="system",
        tags=["files", "filesystem", "read"],
        tools=[
            PluginTool(
                name="list_files",
                description="List files in a directory with optional glob pattern",
                handler=list_files,
                parameters={
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Directory path", "default": "."},
                        "pattern": {"type": "string", "description": "Glob pattern", "default": "*"},
                    },
                },
            ),
            PluginTool(
                name="read_file",
                description="Read a file's content (first 10K chars)",
                handler=read_file,
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "File path"}},
                    "required": ["path"],
                },
            ),
        ],
    ))


# ── Note Taking Plugin ─────────────────────────────────────────


def _register_notes(engine, memory_engine) -> None:
    def add_note(args):
        content = args.get("content", "")
        tags = args.get("tags", [])
        if not content:
            return {"error": "content is required"}
        note_id = f"note_{uuid.uuid4().hex[:8]}"
        if memory_engine:
            from backend.models.memory import MemoryEntry, MemoryType
            entry = MemoryEntry(
                content=f"[Note] {content}",
                memory_type=MemoryType.OBSERVATION,
                tags=["note", *tags],
                source="quick_notes",
                confidence=0.9,
            )
            memory_engine.store(entry)
        return {"status": "created", "note_id": note_id, "content": content, "tags": tags}

    def list_notes(args):
        tag = args.get("tag", "")
        if memory_engine:
            from backend.models.memory import MemoryQuery
            query = tag or "note"
            results = memory_engine.search(MemoryQuery(query=query, limit=20, min_confidence=0.0))
            notes = [
                {"content": m.content, "tags": m.tags, "created_at": m.created_at}
                for m in results if "note" in m.tags
            ]
            return {"notes": notes}
        return {"notes": []}

    engine.register(Plugin(
        id="notes",
        name="Quick Notes",
        description="Fast note-taking with tags",
        version="1.0.0",
        category="productivity",
        tags=["notes", "productivity"],
        tools=[
            PluginTool(
                name="add_note",
                description="Add a quick note with optional tags",
                handler=add_note,
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Note content"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags"},
                    },
                    "required": ["content"],
                },
            ),
            PluginTool(
                name="list_notes",
                description="List recent notes, optionally filtered by tag",
                handler=list_notes,
                parameters={
                    "type": "object",
                    "properties": {"tag": {"type": "string", "description": "Filter by tag"}},
                },
            ),
        ],
    ))


# ── Shell Plugin ────────────────────────────────────────────────


def _register_shell(engine) -> None:
    async def run_command(args):
        cmd = args.get("command", "")
        if not cmd:
            return {"error": "command is required"}
        # Safety: block dangerous commands
        blocked = ["rm -rf", "mkfs", "dd if=", ":(){ :", "fork bomb"]
        for b in blocked:
            if b in cmd.lower():
                return {"error": f"Blocked dangerous command pattern: {b}"}
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path.home()),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            return {
                "command": cmd,
                "stdout": stdout.decode(errors="replace")[:5000],
                "stderr": stderr.decode(errors="replace")[:2000],
                "returncode": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"command": cmd, "error": "Command timed out after 30s"}
        except Exception as e:
            return {"command": cmd, "error": str(e)}

    engine.register(Plugin(
        id="shell",
        name="Shell Executor",
        description="Execute shell commands with safety guards",
        version="1.0.0",
        category="system",
        tags=["shell", "terminal", "commands"],
        tools=[
            PluginTool(
                name="run_command",
                description="Execute a shell command (30s timeout, dangerous patterns blocked)",
                handler=run_command,
                parameters={
                    "type": "object",
                    "properties": {"command": {"type": "string", "description": "Shell command to execute"}},
                    "required": ["command"],
                },
            ),
        ],
    ))


# ── Reminder / Scheduler Plugin ────────────────────────────────


def _register_reminders(engine) -> None:
    _reminders: list[dict[str, Any]] = []

    def set_reminder(args):
        text = args.get("text", "")
        minutes = args.get("minutes", 0)
        if not text:
            return {"error": "text is required"}
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        fire_at = now if minutes <= 0 else now + timedelta(minutes=minutes)
        reminder = {
            "id": f"rem_{uuid.uuid4().hex[:8]}",
            "text": text,
            "minutes": minutes,
            "created_at": now.isoformat(),
            "fire_at": fire_at.isoformat(),
            "fired": False,
        }
        _reminders.append(reminder)
        return {"status": "set", "reminder": reminder}

    def list_reminders(args):
        return {"reminders": [r for r in _reminders if not r.get("fired")]}

    engine.register(Plugin(
        id="reminders",
        name="Reminders",
        description="Set and manage reminders",
        version="1.0.0",
        category="productivity",
        tags=["reminders", "scheduling", "productivity"],
        tools=[
            PluginTool(
                name="set_reminder",
                description="Set a reminder with optional delay in minutes",
                handler=set_reminder,
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Reminder text"},
                        "minutes": {"type": "integer", "description": "Minutes from now", "default": 0},
                    },
                    "required": ["text"],
                },
            ),
            PluginTool(
                name="list_reminders",
                description="List pending reminders",
                handler=list_reminders,
                parameters={"type": "object", "properties": {}},
            ),
        ],
    ))
