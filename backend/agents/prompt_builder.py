"""
Dynamic Prompt Builder — generates system prompts for any agent from its profile.

Instead of hardcoding prompts for each agent, this module generates
context-rich system prompts using the agent's role, description,
capabilities, and tool mappings. Every civilization agent gets a
proper, actionable prompt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.models.agent import AgentProfile


# ── Capability → Tool Mapping ────────────────────────────────────
# Maps capability names to the plugin tools they should use.
# Agents with these capabilities get told about these tools in their prompt.

CAPABILITY_TOOLS: dict[str, list[str]] = {
    # Research & intelligence
    "web_search": ["web_search", "fetch_url"],
    "research": ["web_search", "fetch_url"],
    "paper_search": ["web_search", "fetch_url"],
    "paper_synthesis": ["web_search", "fetch_url"],
    "github_scan": ["web_search", "fetch_url"],
    "patent_search": ["web_search", "fetch_url"],
    "trend_analysis": ["web_search", "fetch_url"],
    "market_research": ["web_search", "fetch_url"],
    "data_collection": ["web_search", "fetch_url"],
    "fact_checking": ["web_search", "fetch_url"],
    "source_discovery": ["web_search", "fetch_url"],
    "competitive_intel": ["web_search", "fetch_url"],
    "opportunity_scan": ["web_search", "fetch_url"],
    "startup_analysis": ["web_search", "fetch_url"],
    "forecasting": ["web_search", "fetch_url", "calculate"],
    "signal_detection": ["web_search", "fetch_url"],
    "innovation_scan": ["web_search", "fetch_url"],
    "emerging_tech": ["web_search", "fetch_url"],
    "benchmark_analysis": ["web_search", "fetch_url", "calculate"],

    # Analysis & computation
    "analysis": ["calculate", "analyze_python", "extract_data"],
    "data_analysis": ["calculate", "analyze_python", "extract_data"],
    "financial_analysis": ["calculate", "compound_interest", "revenue_projector", "roi_calculator"],
    "risk_assessment": ["calculate", "risk_analysis", "make_decision"],
    "risk_modeling": ["calculate", "risk_analysis"],
    "statistical_analysis": ["calculate", "analyze_python"],
    "pattern_recognition": ["analyze_python", "extract_data"],
    "data_mining": ["web_search", "fetch_url", "extract_data"],
    "sentiment_analysis": ["web_search", "fetch_url", "analyze_python"],
    "pricing_analysis": ["calculate", "web_search"],
    "cost_optimization": ["calculate", "analyze_python"],
    "revenue_optimization": ["calculate", "revenue_projector"],
    "financial_forecasting": ["calculate", "compound_interest", "revenue_projector"],
    "portfolio_analysis": ["calculate", "alpaca_account", "alpaca_positions"],
    "performance_metrics": ["calculate", "analyze_python"],
    "roi_analysis": ["calculate", "roi_calculator"],

    # Engineering & code
    "code_generation": ["run_command", "read_file", "write_file"],
    "code_review": ["read_file", "analyze_python"],
    "debugging": ["run_command", "read_file"],
    "refactoring": ["read_file", "write_file", "analyze_python"],
    "testing": ["run_command", "read_file"],
    "deployment": ["run_command"],
    "architecture": ["read_file", "list_files", "analyze_python"],
    "backend_dev": ["run_command", "read_file", "write_file"],
    "frontend_dev": ["run_command", "read_file", "write_file"],
    "api_dev": ["run_command", "read_file", "write_file"],
    "devops": ["run_command", "read_file"],
    "infrastructure": ["run_command", "read_file"],
    "monitoring": ["run_command", "read_file"],
    "ci_cd": ["run_command", "read_file"],
    "scripting": ["run_command", "write_file"],
    "automation": ["run_command", "read_file", "write_file"],
    "optimization": ["run_command", "read_file", "analyze_python"],
    "database_design": ["run_command", "read_file"],
    "security_engineering": ["run_command", "read_file", "web_search"],
    "dependency_management": ["run_command", "read_file"],
    "plugin_dev": ["run_command", "read_file", "write_file"],
    "documentation": ["read_file", "write_file"],
    "system_reliability": ["run_command", "read_file"],

    # Trading & finance
    "strategy_research": ["web_search", "fetch_url", "calculate"],
    "backtesting": ["calculate", "analyze_python", "web_search"],
    "market_analysis": ["web_search", "fetch_url", "calculate"],
    "paper_trading": ["alpaca_account", "alpaca_positions", "alpaca_submit_order"],
    "trading_signals": ["web_search", "calculate"],
    "position_management": ["alpaca_account", "alpaca_positions"],

    # Content & writing
    "writing": ["web_search"],
    "copywriting": ["web_search"],
    "email_drafting": ["web_search"],
    "document_writing": ["web_search", "read_file"],
    "article_writing": ["web_search", "fetch_url"],
    "video_scripting": ["web_search", "fetch_url"],
    "course_creation": ["web_search", "fetch_url"],
    "newsletter_creation": ["web_search", "fetch_url"],
    "seo": ["web_search", "fetch_url"],
    "content_marketing": ["web_search", "fetch_url"],
    "social_media": ["web_search"],

    # System & security
    "health_monitoring": ["run_command", "read_file"],
    "security_audit": ["run_command", "read_file", "list_files"],
    "anomaly_detection": ["run_command", "read_file"],
    "compliance": ["read_file", "web_search"],
    "system_integrity": ["run_command", "read_file"],
    "disaster_recovery": ["run_command", "read_file"],
    "backup_management": ["run_command"],
    "network_monitoring": ["run_command"],

    # Knowledge & memory
    "knowledge_graphs": ["read_file", "analyze_python"],
    "data_pipeline": ["run_command", "read_file"],
    "data_quality": ["analyze_python", "calculate"],
    "indexing": ["read_file", "analyze_python"],
    "information_retrieval": ["web_search", "fetch_url", "read_file"],
    "knowledge_synthesis": ["web_search", "fetch_url"],
    "summarization": ["web_search", "fetch_url"],
    "insight_extraction": ["analyze_python", "extract_data"],

    # Decision & strategy
    "decision_making": ["make_decision", "risk_analysis", "calculate"],
    "strategic_planning": ["web_search", "make_decision"],
    "scenario_simulation": ["calculate", "make_decision", "risk_analysis"],
    "experiment_design": ["calculate", "web_search"],
    "hypothesis_testing": ["calculate", "analyze_python"],
    "evaluation": ["calculate", "analyze_python"],
    "opportunity_scoring": ["opportunity_scorer", "calculate"],
    "comparison": ["pros_cons_matrix", "calculate"],

    # Business
    "lead_generation": ["web_search", "fetch_url"],
    "email_outreach": ["web_search"],
    "crm": ["web_search"],
    "workflow_design": ["read_file", "analyze_python"],
    "process_optimization": ["analyze_python", "calculate"],
    "sales": ["web_search", "fetch_url"],
    "partnership": ["web_search", "fetch_url"],

    # Self-improvement
    "skill_creation": ["read_file", "write_file", "add_note"],
    "self_analysis": ["read_file", "list_files", "analyze_python"],
    "gap_analysis": ["read_file", "list_files"],
    "prompt_engineering": ["web_search"],
    "learning_strategy": ["web_search", "add_note"],
    "reflection": ["read_file", "add_note"],
    "knowledge_expansion": ["web_search", "fetch_url", "add_note"],

    # Agent creation & communication
    "file_generation": ["file_writer_write_file", "reports_write_report", "charts_generate_chart"],
    "report_generation": ["reports_write_report", "file_writer_write_file"],
    "chart_generation": ["charts_generate_chart"],
    "direction_proposal": ["proposals_propose_direction", "proposals_list_proposals"],
    "agent_communication": ["agent_comms_request_agent_help", "agent_comms_broadcast_finding"],
    "visualization": ["charts_generate_chart", "file_writer_write_file"],
}

# ── Division-level prompt context ────────────────────────────────

_DIVISION_CONTEXT: dict[str, str] = {
    "Strategy Council": (
        "You are part of ROOT's Strategy Council — the highest-level thinking division.\n"
        "Your role is strategic: long-term vision, opportunity identification, risk assessment,\n"
        "competitive intelligence, and architectural decisions. Think big, think ahead.\n"
        "Always consider Yohan's goals: $10K+/mo MRR, financial independence, automation."
    ),
    "Research Division": (
        "You are part of ROOT's Research Division — the intelligence-gathering arm.\n"
        "Your role is to discover, analyze, and synthesize knowledge from the web,\n"
        "papers, patents, GitHub, and market data. ALWAYS use web_search first.\n"
        "Never answer from training data alone — search for current, real information."
    ),
    "Engineering Division": (
        "You are part of ROOT's Engineering Division — the builders and maintainers.\n"
        "Your role is to design, build, test, deploy, and maintain software systems.\n"
        "Write clean, well-tested code. Follow best practices. Use tools to verify."
    ),
    "Data & Memory Division": (
        "You are part of ROOT's Data & Memory Division — the knowledge infrastructure.\n"
        "Your role is to build, organize, and maintain data pipelines, knowledge graphs,\n"
        "indexes, and data quality systems. Data is ROOT's lifeblood."
    ),
    "Learning & Improvement": (
        "You are part of ROOT's Learning & Improvement Division — the self-evolution engine.\n"
        "Your role is to design experiments, analyze failures, optimize workflows,\n"
        "audit performance, and continuously improve ROOT's capabilities."
    ),
    "Economic Engine": (
        "You are part of ROOT's Economic Engine — the revenue and growth division.\n"
        "Your role is to find opportunities, build products, optimize revenue streams,\n"
        "manage marketing, and grow Yohan's business. Every action should create value.\n"
        "Target: $10K-$100K/month across 5 revenue streams."
    ),
    "Content Network": (
        "You are part of ROOT's Content Network — the publishing and distribution arm.\n"
        "Your role is to create, optimize, and distribute content across channels.\n"
        "Focus on SEO, engagement, audience growth, and content-led revenue."
    ),
    "Automation Business": (
        "You are part of ROOT's Automation Business division — the service delivery arm.\n"
        "Your role is to build automation solutions, bots, workflows, and systems\n"
        "that can be sold as services. Focus on client value and recurring revenue."
    ),
    "Infrastructure Operations": (
        "You are part of ROOT's Infrastructure Operations — the reliability backbone.\n"
        "Your role is to manage compute, optimize costs, ensure uptime, handle DR,\n"
        "and maintain system health. Stability is your priority."
    ),
    "Governance & Safety": (
        "You are part of ROOT's Governance & Safety division — the trust layer.\n"
        "Your role is to monitor alignment, ethics, security, costs, compliance,\n"
        "and system integrity. Flag risks early. Protect Yohan's interests."
    ),
}


def _get_division_for_agent(agent_id: str) -> str | None:
    """Look up which division an agent belongs to."""
    from backend.agents.civilization import ALL_DIVISIONS
    for division_name, agents in ALL_DIVISIONS.items():
        if any(a.id == agent_id for a in agents):
            return division_name
    return None


def build_agent_prompt(agent: AgentProfile) -> str:
    """Generate a complete, actionable system prompt from an AgentProfile.

    This replaces hardcoded prompts — every agent gets a prompt tailored
    to its role, description, and capabilities.
    """
    # Division context
    division = _get_division_for_agent(agent.id)
    division_ctx = _DIVISION_CONTEXT.get(division, "") if division else ""

    # Collect tools this agent should use based on capabilities
    agent_tools: set[str] = set()
    for cap in agent.capabilities:
        tools = CAPABILITY_TOOLS.get(cap.name, [])
        agent_tools.update(tools)

    # Build capability descriptions
    cap_lines = []
    for cap in agent.capabilities:
        tools = CAPABILITY_TOOLS.get(cap.name, [])
        tool_hint = f" → use: {', '.join(tools)}" if tools else ""
        cap_lines.append(f"- **{cap.name}**: {cap.description}{tool_hint}")

    caps_section = "\n".join(cap_lines) if cap_lines else "- General specialist"

    # Build tool usage section
    tool_section = ""
    if agent_tools:
        tool_section = (
            "\n\n## Tools You MUST Use\n"
            f"You have access to: {', '.join(sorted(agent_tools))}\n"
            "ALWAYS use your tools to get real data. Never answer from training data alone.\n"
            "Search the web, fetch URLs, run commands, and calculate as needed."
        )

    # Core prompt
    prompt = (
        f"You are **{agent.name}** — a specialized agent in ROOT's AI civilization.\n"
        f"Role: {agent.role}\n\n"
        f"{division_ctx}\n\n" if division_ctx else
        f"You are **{agent.name}** — a specialized agent in ROOT's AI civilization.\n"
        f"Role: {agent.role}\n\n"
    )

    prompt = (
        f"You are **{agent.name}** — a specialized agent in ROOT's AI civilization.\n"
        f"Role: {agent.role}\n\n"
    )

    if division_ctx:
        prompt += f"{division_ctx}\n\n"

    prompt += (
        f"## Your Mission\n"
        f"{agent.description}\n\n"
        f"## Your Capabilities\n"
        f"{caps_section}"
        f"{tool_section}\n\n"
        f"## Operating Rules\n"
        f"1. Be thorough — use multiple tool calls to gather comprehensive data\n"
        f"2. Be specific — include REAL numbers, dates, URLs, and verifiable sources\n"
        f"3. Be actionable — end with concrete next steps and recommendations\n"
        f"4. Report honestly — if something fails or data is missing, say so clearly\n"
        f"5. Stay in your lane — focus on your specialty, defer to other agents for theirs\n\n"
        f"## Study Quality (MANDATORY)\n"
        f"Your output must be a PRECISE, ACCURATE STUDY — not a superficial summary.\n"
        f"- Every claim must be backed by data from your tool results\n"
        f"- Cross-check facts across multiple sources before stating them\n"
        f"- Show your methodology: what you searched, what you found, how you analyzed\n"
        f"- Include confidence levels (high/medium/low) for each finding\n"
        f"- NEVER fabricate numbers or statistics — if you can't verify, say so\n"
        f"- Structure: Context → Data Gathered → Analysis → Findings → Proposed Next Steps\n\n"
        f"## Propose Direction (MANDATORY)\n"
        f"After completing your study, you MUST:\n"
        f"1. Assess what you found and what it means for Yohan's goals\n"
        f"2. Propose specific next steps — what should be done and why\n"
        f"3. Identify opportunities or risks that require attention\n"
        f"4. Suggest which agents should handle follow-up work\n"
        f"5. Flag anything that needs Yohan's approval before proceeding\n\n"
        f"## Team & Communication Tools\n"
        f"You are part of a team of 172+ specialist agents. Pull in teammates whenever needed:\n"
        f"- **invoke_agent** (PRIMARY): Synchronously call another agent and get their result back.\n"
        f"  Use this to pull in specialists mid-task. Examples:\n"
        f"    invoke_agent('analyst', 'Analyze this market data: ...') → get their analysis\n"
        f"    invoke_agent('coder', 'Write Python code to backtest this strategy') → get the code\n"
        f"    invoke_agent('risk_strategist', 'Assess downside risk for this trade') → get risk report\n"
        f"  The team forms dynamically — use whoever the task requires.\n"
        f"- **request_agent_help**: Async notification to another agent (fire-and-forget)\n"
        f"- **broadcast_finding**: Share a discovery with all agents in the civilization\n"
        f"- **propose_direction**: Submit a proposal to ASTRA → Yohan gets notified\n"
        f"  Use this when you discover an opportunity, risk, or strategic direction\n"
        f"- **write_report**: Generate structured reports (saved to data/agent_output/)\n"
        f"- **generate_chart**: Create visualizations (line, bar, scatter, pie charts)\n"
        f"- **write_file**: Write any file (code, data, configs) to agent output\n"
        f"Be PROACTIVE — if a sub-task needs a specialist, invoke them. Don't work alone on complex problems."
    )

    return prompt


def build_system_message(agent: AgentProfile, task_context: str = "") -> str:
    """Build a complete system message with prompt + date context + task framing."""
    prompt = build_agent_prompt(agent)
    now = datetime.now(timezone.utc)
    date_ctx = (
        f"\n\n## Current Date\n"
        f"Today is {now.strftime('%A, %B %d, %Y')} (UTC). "
        f"All responses must use this date context — never guess or use training data dates."
    )

    system = (
        f"{prompt}"
        f"\n\n## Task from ROOT (on behalf of Yohan)\n"
        f"Complete this task thoroughly. Use your tools when needed.\n"
        f"Be concise but comprehensive."
        f"{date_ctx}"
    )

    if task_context:
        system += f"\n\n## Additional Context\n{task_context}"

    return system


def get_tools_for_agent(agent: AgentProfile) -> set[str]:
    """Return the set of tool names an agent should have access to."""
    tools: set[str] = set()
    for cap in agent.capabilities:
        mapped = CAPABILITY_TOOLS.get(cap.name, [])
        tools.update(mapped)
    return tools
