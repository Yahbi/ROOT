"""
Claude Agent SDK Integration — ROOT as a Claude Code tool provider.

Provides MCP tool definitions that wrap ROOT's core API, enabling any
Claude Agent SDK user to invoke ROOT agents as subagent tools.

Usage with Claude Agent SDK:
    from claude_agent_sdk import ClaudeAgentOptions, query

    options = ClaudeAgentOptions(
        mcp_servers={
            "root": {
                "url": "http://localhost:9000/mcp",
                "transport": "streamable-http",
            }
        },
    )

Or standalone via the helper functions below for manual tool registration.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("root.claude_agent")


# ── Tool Definitions ──────────────────────────────────────────────
# These describe ROOT capabilities as Claude Agent SDK-compatible tools.
# They can be used with FastMCP's @tool decorator or served via the
# MCP server already mounted by fastapi_mcp.

CLAUDE_AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "root_chat",
        "description": (
            "Send a message to ROOT's ASTRA intelligence core. "
            "ASTRA routes to the best agent(s) from 162+ specialists across "
            "strategy, research, engineering, trading, and more."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message or question to send to ROOT",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "root_delegate",
        "description": (
            "Delegate a task to a specific ROOT agent by ID. "
            "Core agents: astra, hermes, miro, swarm, openclaw, builder, "
            "researcher, coder, writer, analyst, guardian."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID to delegate to",
                },
                "task": {
                    "type": "string",
                    "description": "The task description",
                },
            },
            "required": ["agent_id", "task"],
        },
    },
    {
        "name": "root_search_memory",
        "description": (
            "Search ROOT's knowledge base (686+ entries). "
            "Returns relevant memories with confidence scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for ROOT's memory",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "root_trading_cycle",
        "description": (
            "Run a full AI trading cycle: scan markets, generate signals, "
            "assess risk, and optionally execute trades via Alpaca."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Stock symbols to analyze (e.g. ['AAPL', 'NVDA'])",
                },
            },
            "required": [],
        },
    },
    {
        "name": "root_list_agents",
        "description": (
            "List all ROOT agents with their status, division, and capabilities. "
            "162+ agents across 10 divisions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "division": {
                    "type": "string",
                    "description": "Filter by division name (optional)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "root_council",
        "description": (
            "Convene a multi-agent council debate on a topic. "
            "Multiple agents discuss and reach consensus."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic for the council to debate",
                },
                "agents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Agent IDs to include (default: miro selects)",
                },
            },
            "required": ["topic"],
        },
    },
]


# ── Subagent Definitions ──────────────────────────────────────────
# Map ROOT's 12 core agents to Claude Agent SDK subagent definitions.

CLAUDE_SUBAGENT_DEFINITIONS: dict[str, dict[str, str]] = {
    "root-strategist": {
        "description": "Strategic intelligence — reasoning, opportunity discovery, learning",
        "prompt": "You are ASTRA, ROOT's strategic intelligence core. Route tasks to specialists and synthesize multi-agent findings.",
    },
    "root-researcher": {
        "description": "Deep research — papers, GitHub, market analysis, trend detection",
        "prompt": "You are ROOT's Researcher agent. Conduct thorough research on the given topic using web search and knowledge retrieval.",
    },
    "root-coder": {
        "description": "Software engineering — code, architecture, debugging, optimization",
        "prompt": "You are ROOT's Coder agent. Write, review, and improve code. Follow best practices and test your work.",
    },
    "root-analyst": {
        "description": "Business intelligence — data analysis, market assessment, financial modeling",
        "prompt": "You are ROOT's Analyst agent. Analyze data, assess markets, and provide quantitative insights.",
    },
    "root-trader": {
        "description": "AI trading — signal generation, risk assessment, portfolio management",
        "prompt": "You are ROOT's Trading Swarm. Research market conditions, generate signals, and assess risk.",
    },
    "root-writer": {
        "description": "Content creation — articles, documentation, marketing copy",
        "prompt": "You are ROOT's Writer agent. Create compelling, accurate content adapted to the target audience.",
    },
    "root-guardian": {
        "description": "Security & integrity — audit, compliance, safety checks",
        "prompt": "You are ROOT's Guardian agent. Monitor for security issues, alignment concerns, and system integrity.",
    },
}


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return tool definitions for Claude Agent SDK registration."""
    return CLAUDE_AGENT_TOOLS


def get_subagent_definitions() -> dict[str, dict[str, str]]:
    """Return subagent definitions for Claude Agent SDK registration."""
    return CLAUDE_SUBAGENT_DEFINITIONS
