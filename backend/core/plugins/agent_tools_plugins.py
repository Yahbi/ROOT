"""Agent Creation & Communication Tools — file generation, charts, reports, proposals.

Gives agents the ability to:
- Write files (reports, code, data)
- Generate charts (matplotlib)
- Propose directions to ASTRA → Yohan (via notification engine)
- Request help from other agents (via message bus)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.plugin_engine import Plugin, PluginTool

logger = logging.getLogger("root.plugins.agent_tools")

# Base output directory for agent-generated files
OUTPUT_DIR = Path(os.environ.get("ROOT_OUTPUT_DIR", "data/agent_output"))


def register_agent_tools_plugins(
    engine,
    notification_engine=None,
    message_bus=None,
    experience_memory=None,
) -> None:
    """Register agent creation and communication tools."""
    _register_file_writer(engine)
    _register_chart_generator(engine)
    _register_report_writer(engine)
    _register_proposal_system(engine, notification_engine, message_bus)
    _register_agent_request(engine, message_bus)


# ── File Writer Plugin ─────────────────────────────────────────


def _register_file_writer(engine) -> None:
    def write_file(args: dict) -> dict:
        filename = args.get("filename", "")
        content = args.get("content", "")
        subdirectory = args.get("subdirectory", "")
        if not filename or not content:
            return {"error": "filename and content are required"}

        # Sanitize filename
        safe_name = Path(filename).name
        if not safe_name:
            return {"error": "Invalid filename"}

        # Build output path
        base = OUTPUT_DIR / subdirectory if subdirectory else OUTPUT_DIR
        base.mkdir(parents=True, exist_ok=True)
        filepath = base / safe_name

        # Prevent path traversal
        if not str(filepath.resolve()).startswith(str(OUTPUT_DIR.resolve())):
            return {"error": "Path traversal not allowed"}

        filepath.write_text(content, encoding="utf-8")
        logger.info("Agent wrote file: %s (%d chars)", filepath, len(content))
        return {
            "status": "written",
            "path": str(filepath),
            "filename": safe_name,
            "size_bytes": len(content.encode("utf-8")),
        }

    engine.register(Plugin(
        id="file_writer",
        name="File Writer",
        description="Write files to agent output directory (reports, code, data)",
        version="1.0.0",
        category="creation",
        tags=["files", "write", "create", "output"],
        tools=[
            PluginTool(
                name="write_file",
                description=(
                    "Write content to a file in the agent output directory. "
                    "Use for reports, code, data exports, or any generated content."
                ),
                handler=write_file,
                parameters={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Output filename (e.g., 'analysis.md', 'data.json')",
                        },
                        "content": {
                            "type": "string",
                            "description": "File content to write",
                        },
                        "subdirectory": {
                            "type": "string",
                            "description": "Optional subdirectory (e.g., 'reports', 'charts')",
                            "default": "",
                        },
                    },
                    "required": ["filename", "content"],
                },
            ),
        ],
    ))


# ── Chart Generator Plugin ─────────────────────────────────────


def _register_chart_generator(engine) -> None:
    def generate_chart(args: dict) -> dict:
        chart_type = args.get("chart_type", "line")
        title = args.get("title", "Chart")
        data = args.get("data", {})
        filename = args.get("filename", "")

        if not data:
            return {"error": "data is required"}

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 6))

            x_data = data.get("x", [])
            y_data = data.get("y", [])
            labels = data.get("labels", [])
            series = data.get("series", {})

            if series:
                # Multi-series
                for label, values in series.items():
                    x = list(range(len(values))) if not x_data else x_data
                    if chart_type == "bar":
                        ax.bar(x, values, label=label, alpha=0.7)
                    else:
                        ax.plot(x, values, label=label, marker="o", markersize=3)
                ax.legend()
            elif x_data and y_data:
                if chart_type == "bar":
                    ax.bar(x_data, y_data)
                elif chart_type == "scatter":
                    ax.scatter(x_data, y_data)
                elif chart_type == "pie":
                    ax.pie(y_data, labels=x_data, autopct="%1.1f%%")
                else:
                    ax.plot(x_data, y_data, marker="o", markersize=3)
            else:
                return {"error": "data must contain x/y arrays or series dict"}

            ax.set_title(title, fontsize=14, fontweight="bold")
            xlabel = data.get("xlabel")
            if xlabel:
                ax.set_xlabel(xlabel)
            ylabel = data.get("ylabel")
            if ylabel:
                ax.set_ylabel(ylabel)
            if chart_type != "pie":
                ax.grid(True, alpha=0.3)

            plt.tight_layout()

            # Save
            safe_name = filename or f"chart_{uuid.uuid4().hex[:8]}.png"
            out_dir = OUTPUT_DIR / "charts"
            out_dir.mkdir(parents=True, exist_ok=True)
            filepath = out_dir / safe_name
            fig.savefig(filepath, dpi=150, bbox_inches="tight")
            plt.close(fig)

            logger.info("Agent generated chart: %s", filepath)
            return {
                "status": "generated",
                "path": str(filepath),
                "chart_type": chart_type,
                "title": title,
            }
        except ImportError:
            return {"error": "matplotlib not installed — run: pip install matplotlib"}
        except Exception as e:
            return {"error": f"Chart generation failed: {str(e)}"}

    engine.register(Plugin(
        id="charts",
        name="Chart Generator",
        description="Generate charts and visualizations (line, bar, scatter, pie)",
        version="1.0.0",
        category="creation",
        tags=["charts", "visualization", "images", "matplotlib"],
        tools=[
            PluginTool(
                name="generate_chart",
                description=(
                    "Generate a chart image (PNG). Supports line, bar, scatter, and pie charts. "
                    "Data format: {x: [...], y: [...]} or {series: {label: [values]}}."
                ),
                handler=generate_chart,
                parameters={
                    "type": "object",
                    "properties": {
                        "chart_type": {
                            "type": "string",
                            "enum": ["line", "bar", "scatter", "pie"],
                            "description": "Chart type",
                            "default": "line",
                        },
                        "title": {
                            "type": "string",
                            "description": "Chart title",
                        },
                        "data": {
                            "type": "object",
                            "description": (
                                "Chart data. Format: {x: [...], y: [...], xlabel: '...', ylabel: '...'} "
                                "or {series: {label1: [values], label2: [values]}}"
                            ),
                        },
                        "filename": {
                            "type": "string",
                            "description": "Output filename (default: auto-generated)",
                            "default": "",
                        },
                    },
                    "required": ["title", "data"],
                },
            ),
        ],
    ))


# ── Report Writer Plugin ────────────────────────────────────────


def _register_report_writer(engine) -> None:
    def write_report(args: dict) -> dict:
        import json as _json
        title = args.get("title", "Untitled Report")
        sections = args.get("sections", [])
        filename = args.get("filename", "")
        report_format = args.get("format", "markdown")

        # LLMs sometimes pass sections as a JSON string — parse it
        if isinstance(sections, str):
            try:
                sections = _json.loads(sections)
            except (_json.JSONDecodeError, ValueError):
                sections = [{"heading": "Report", "content": sections}]

        if not sections:
            return {"error": "sections are required"}

        # Build markdown report
        now = datetime.now(timezone.utc)
        lines = [
            f"# {title}",
            f"*Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}*",
            f"*Source: ROOT Agent Civilization*",
            "",
            "---",
            "",
        ]

        for section in sections:
            if not isinstance(section, dict):
                continue
            heading = section.get("heading", "Section")
            content = section.get("content", "")
            lines.append(f"## {heading}")
            lines.append("")
            lines.append(content)
            lines.append("")

        # Add footer
        lines.extend([
            "---",
            "",
            f"*Report generated by ROOT at {now.isoformat()}*",
        ])

        report_content = "\n".join(lines)

        # Save
        safe_name = filename or f"report_{now.strftime('%Y%m%d_%H%M%S')}.md"
        out_dir = OUTPUT_DIR / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        filepath = out_dir / safe_name
        filepath.write_text(report_content, encoding="utf-8")

        logger.info("Agent wrote report: %s (%d chars)", filepath, len(report_content))
        return {
            "status": "written",
            "path": str(filepath),
            "title": title,
            "sections": len(sections),
            "size_bytes": len(report_content.encode("utf-8")),
        }

    engine.register(Plugin(
        id="reports",
        name="Report Writer",
        description="Generate structured reports (markdown with sections)",
        version="1.0.0",
        category="creation",
        tags=["reports", "documents", "writing", "output"],
        tools=[
            PluginTool(
                name="write_report",
                description=(
                    "Generate a structured report with title and sections. "
                    "Output is a markdown file saved to data/agent_output/reports/."
                ),
                handler=write_report,
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Report title",
                        },
                        "sections": {
                            "type": "array",
                            "description": "Report sections: [{heading: '...', content: '...'}]",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "heading": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["heading", "content"],
                            },
                        },
                        "filename": {
                            "type": "string",
                            "description": "Output filename (default: auto-generated)",
                            "default": "",
                        },
                    },
                    "required": ["title", "sections"],
                },
            ),
        ],
    ))


# ── Proposal System (Agent → ASTRA → Yohan) ────────────────────


def _register_proposal_system(engine, notification_engine, message_bus) -> None:
    # In-memory proposal store (also persisted via notification)
    _proposals: list[dict[str, Any]] = []

    def propose_direction(args: dict) -> dict:
        """Agent proposes a direction/action to ASTRA for Yohan's review."""
        agent_id = args.get("agent_id", "unknown")
        proposal = args.get("proposal", "")
        category = args.get("category", "general")
        priority = args.get("priority", "medium")
        reasoning = args.get("reasoning", "")
        estimated_impact = args.get("estimated_impact", "")
        risk_level = args.get("risk_level", "medium")
        requires_approval = args.get("requires_approval", True)

        if not proposal:
            return {"error": "proposal is required"}

        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        record = {
            "id": proposal_id,
            "agent_id": agent_id,
            "proposal": proposal,
            "category": category,
            "priority": priority,
            "reasoning": reasoning,
            "estimated_impact": estimated_impact,
            "risk_level": risk_level,
            "requires_approval": requires_approval,
            "status": "pending",
            "created_at": now.isoformat(),
        }
        _proposals.append(record)

        # Publish to message bus for ASTRA
        if message_bus:
            try:
                import asyncio
                msg = message_bus.create_message(
                    topic="system.proposal",
                    sender=agent_id,
                    payload=record,
                )
                asyncio.ensure_future(message_bus.publish(msg))
            except Exception as e:
                logger.error("Failed to publish proposal to bus: %s", e)

        # Send notification to Yohan
        if notification_engine:
            try:
                import asyncio
                level_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
                notif_level = level_map.get(priority, "medium")

                body = (
                    f"**From**: {agent_id}\n"
                    f"**Category**: {category}\n"
                    f"**Priority**: {priority}\n"
                    f"**Risk**: {risk_level}\n\n"
                    f"**Proposal**: {proposal}\n\n"
                    f"**Reasoning**: {reasoning}\n\n"
                    f"**Estimated Impact**: {estimated_impact}\n\n"
                )
                if requires_approval:
                    body += "⏳ *Awaiting your approval to proceed.*"
                else:
                    body += "ℹ️ *FYI — no approval needed, proceeding autonomously.*"

                asyncio.ensure_future(
                    notification_engine.send(
                        title=f"🧠 Agent Proposal: {proposal[:60]}",
                        body=body,
                        level=notif_level,
                        source=f"agent:{agent_id}",
                    )
                )
            except Exception as e:
                logger.error("Failed to send proposal notification: %s", e)

        logger.info("Agent %s proposed: %s (priority=%s)", agent_id, proposal[:80], priority)
        return {
            "status": "submitted",
            "proposal_id": proposal_id,
            "notification_sent": notification_engine is not None,
            "message": "Proposal submitted to ASTRA and Yohan has been notified.",
        }

    def list_proposals(args: dict) -> dict:
        status_filter = args.get("status", "")
        filtered = _proposals
        if status_filter:
            filtered = [p for p in _proposals if p["status"] == status_filter]
        return {"proposals": filtered[-20:], "total": len(filtered)}

    engine.register(Plugin(
        id="proposals",
        name="Direction Proposals",
        description="Agents propose directions/actions to ASTRA for Yohan's review and approval",
        version="1.0.0",
        category="communication",
        tags=["proposals", "direction", "approval", "communication"],
        tools=[
            PluginTool(
                name="propose_direction",
                description=(
                    "Propose a direction, action, or strategy to ASTRA for Yohan's review. "
                    "ASTRA will evaluate and notify Yohan. Use this when you discover "
                    "an opportunity, identify a risk, or want to suggest next steps."
                ),
                handler=propose_direction,
                parameters={
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Your agent ID (e.g., 'algorithm_researcher')",
                        },
                        "proposal": {
                            "type": "string",
                            "description": "Clear description of what you propose",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["trading", "revenue", "research", "engineering", "security", "learning", "strategy"],
                            "description": "Proposal category",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "How urgent is this proposal",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Why this is the right direction — include data",
                        },
                        "estimated_impact": {
                            "type": "string",
                            "description": "Expected outcome (e.g., '$500/month revenue', '30% efficiency gain')",
                        },
                        "risk_level": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Risk level of this proposal",
                        },
                        "requires_approval": {
                            "type": "boolean",
                            "description": "Whether Yohan needs to approve before executing",
                            "default": True,
                        },
                    },
                    "required": ["agent_id", "proposal", "category"],
                },
            ),
            PluginTool(
                name="list_proposals",
                description="List recent proposals and their status",
                handler=list_proposals,
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["pending", "approved", "rejected", "executing"],
                            "description": "Filter by status",
                        },
                    },
                },
            ),
        ],
    ))


# ── Agent Request System (inter-agent communication) ────────────


def _register_agent_request(engine, message_bus) -> None:
    def request_agent_help(args: dict) -> dict:
        """One agent requests help from another via the message bus."""
        from_agent = args.get("from_agent", "unknown")
        to_agent = args.get("to_agent", "")
        request_type = args.get("request_type", "help")
        message = args.get("message", "")
        context = args.get("context", "")

        if not to_agent or not message:
            return {"error": "to_agent and message are required"}

        request_id = f"req_{uuid.uuid4().hex[:8]}"

        # Publish to message bus
        if message_bus:
            try:
                import asyncio
                msg = message_bus.create_message(
                    topic=f"agent.{to_agent}.request",
                    sender=from_agent,
                    payload={
                        "request_id": request_id,
                        "from_agent": from_agent,
                        "to_agent": to_agent,
                        "request_type": request_type,
                        "message": message,
                        "context": context[:2000],
                    },
                )
                asyncio.ensure_future(message_bus.publish(msg))
                logger.info("Agent %s requested help from %s: %s", from_agent, to_agent, message[:80])
                return {
                    "status": "sent",
                    "request_id": request_id,
                    "message": f"Request sent to {to_agent} via message bus.",
                }
            except Exception as e:
                return {"error": f"Failed to send request: {str(e)}"}

        return {"error": "Message bus not available"}

    def broadcast_finding(args: dict) -> dict:
        """Agent broadcasts a finding to all interested agents."""
        agent_id = args.get("agent_id", "unknown")
        finding = args.get("finding", "")
        topic_tag = args.get("topic", "general")
        confidence = args.get("confidence", "medium")

        if not finding:
            return {"error": "finding is required"}

        if message_bus:
            try:
                import asyncio
                msg = message_bus.create_message(
                    topic=f"system.learning",
                    sender=agent_id,
                    payload={
                        "agent_id": agent_id,
                        "finding": finding,
                        "topic": topic_tag,
                        "confidence": confidence,
                    },
                )
                asyncio.ensure_future(message_bus.publish(msg))
                logger.info("Agent %s broadcast finding: %s", agent_id, finding[:80])
                return {"status": "broadcast", "message": "Finding shared with the civilization."}
            except Exception as e:
                return {"error": f"Broadcast failed: {str(e)}"}

        return {"error": "Message bus not available"}

    engine.register(Plugin(
        id="agent_comms",
        name="Agent Communication",
        description="Inter-agent communication — request help, broadcast findings",
        version="1.0.0",
        category="communication",
        tags=["communication", "agents", "collaboration"],
        tools=[
            PluginTool(
                name="request_agent_help",
                description=(
                    "Request help from another agent. The request is sent via the "
                    "message bus and the target agent will be notified."
                ),
                handler=request_agent_help,
                parameters={
                    "type": "object",
                    "properties": {
                        "from_agent": {
                            "type": "string",
                            "description": "Your agent ID",
                        },
                        "to_agent": {
                            "type": "string",
                            "description": "Target agent ID (e.g., 'backtester', 'analyst')",
                        },
                        "request_type": {
                            "type": "string",
                            "enum": ["help", "review", "data", "analysis", "verification"],
                            "description": "Type of request",
                        },
                        "message": {
                            "type": "string",
                            "description": "What you need from the other agent",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context (your findings so far)",
                            "default": "",
                        },
                    },
                    "required": ["from_agent", "to_agent", "message"],
                },
            ),
            PluginTool(
                name="broadcast_finding",
                description=(
                    "Broadcast a finding to all agents in the civilization. "
                    "Use when you discover something that other agents should know about."
                ),
                handler=broadcast_finding,
                parameters={
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Your agent ID",
                        },
                        "finding": {
                            "type": "string",
                            "description": "The finding to share",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Topic tag (e.g., 'trading', 'market', 'opportunity')",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Confidence level of this finding",
                        },
                    },
                    "required": ["agent_id", "finding"],
                },
            ),
            PluginTool(
                name="invoke_agent",
                description=(
                    "Synchronously invoke a specialist agent and receive their full result "
                    "before you continue. Use this to dynamically pull in teammates for "
                    "sub-tasks you need help with. Examples: invoke 'trading_swarm' for market "
                    "signals, 'analyst' for data analysis, 'coder' to write code, 'researcher' "
                    "to gather information. The agent executes and you get their answer back "
                    "immediately to incorporate in your response."
                ),
                handler=lambda args: {"status": "intercepted_by_connector"},
                parameters={
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": (
                                "Target agent ID. Examples: 'researcher', 'analyst', 'coder', "
                                "'trading_swarm', 'miro', 'writer', 'guardian', 'hermes', "
                                "or any civilization agent like 'opportunity_hunter', "
                                "'risk_strategist', 'backtester', 'signal_detector'"
                            ),
                        },
                        "task": {
                            "type": "string",
                            "description": "Complete task description for the agent — be specific and include all relevant context",
                        },
                        "context": {
                            "type": "string",
                            "description": "Your findings so far, passed as context to help the agent",
                            "default": "",
                        },
                    },
                    "required": ["agent_id", "task"],
                },
            ),
        ],
    ))
