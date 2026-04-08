"""
Knowledge Bootstrap — seeds ROOT's memory with intelligence from the AI folder.

Absorbs knowledge from: Everything Claude Code, HERMES, MiRo, Agent Orchestrator,
DeepSeek, Llama.cpp, GPT4All, Awesome-LLM, Agent Collab, OpenClaw.

Runs once at first startup (or on-demand) to populate the memory DB.
"""

from __future__ import annotations

import logging
from backend.core.memory_engine import MemoryEngine
from backend.models.memory import MemoryEntry, MemoryType

logger = logging.getLogger("root.bootstrap")

# ── Knowledge corpus ──────────────────────────────────────────
# Each entry: (content, type, tags, source)

CORE_KNOWLEDGE: list[tuple[str, MemoryType, list[str], str]] = [
    # ── ROOT Identity ──
    (
        "ROOT is an ever-evolving personal AI system built for Yohan Bismuth. "
        "It learns from every interaction, manages a network of specialist agents, "
        "and improves itself through self-reflection. ROOT is Tier 1 (Orchestrator), "
        "Yohan is Tier 0 (God). All agents serve Yohan's interests.",
        MemoryType.FACT, ["identity", "core"], "bootstrap",
    ),
    (
        "ROOT's agent hierarchy: Tier 0=Yohan (God, full override), "
        "Tier 1=ROOT (Orchestrator), Builder (Self-Improvement), Guardian (Security), "
        "Tier 2=Workers (HERMES, ASTRA, MiRo, Trading Swarm, OpenClaw, Researcher, "
        "Coder, Writer, Analyst). All decisions flow down from Yohan. "
        "ROOT coordinates, Tier 1 engines run autonomously, Tier 2 agents execute tasks.",
        MemoryType.FACT, ["hierarchy", "agents"], "bootstrap",
    ),

    # ── HERMES Knowledge ──
    (
        "HERMES is a self-improving multi-agent framework by Nous Research. Core loop: "
        "AIAgent receives messages → calls tools → receives results → loops until done. "
        "Key patterns: frozen memory snapshots for prefix caching, opaque subagent delegation "
        "(parent never sees child tool calls), context compression at 85% utilization, "
        "skill creation from experience (SKILL.md files with frontmatter).",
        MemoryType.LEARNING, ["hermes", "architecture"], "ai_folder",
    ),
    (
        "HERMES memory system: MEMORY.md (2200 char limit, agent notes) + USER.md (1375 chars, "
        "user preferences). Frozen snapshot pattern — loaded at session start, injected into "
        "system prompt, never changes mid-session (preserves prefix cache). Mutations update "
        "disk immediately but don't break cache. Entry delimiter: section sign (§).",
        MemoryType.LEARNING, ["hermes", "memory", "pattern"], "ai_folder",
    ),
    (
        "HERMES delegation: MAX_CONCURRENT_CHILDREN=3, MAX_DEPTH=2. Child agents get fresh "
        "conversations, isolated terminals, restricted toolsets (no delegate/memory/clarify). "
        "Parent only receives summary + metadata, never intermediate work. This prevents "
        "context explosion from parallel tasks.",
        MemoryType.LEARNING, ["hermes", "delegation", "pattern"], "ai_folder",
    ),
    (
        "HERMES context compression: triggered at 85% context utilization. Protects first 3 "
        "and last 4 turns. Summarizes middle via auxiliary model (Gemini Flash). Fixes orphaned "
        "tool_call/tool_result pairs after compression. Falls back to dropping middle turns "
        "without summary if LLM call fails.",
        MemoryType.LEARNING, ["hermes", "context", "compression"], "ai_folder",
    ),
    (
        "HERMES security: memory entries scanned for prompt injection (20+ patterns), invisible "
        "Unicode (U+200B-U+200F, U+202A-U+202E), exfiltration attempts (curl/wget with secrets), "
        "SSH backdoors. Context files (AGENTS.md, SOUL.md) truncated to 20K chars (70% head + "
        "20% tail). All blocked patterns logged.",
        MemoryType.LEARNING, ["hermes", "security"], "ai_folder",
    ),
    (
        "HERMES skills system: SKILL.md files with YAML frontmatter (name, description, version, "
        "tags, platforms). Stored in ~/.hermes/skills/ by category. Injected as user message "
        "(not system prompt) to preserve prefix cache. Platform-filtered (darwin/linux/win32). "
        "Skills created from experience, improved during use.",
        MemoryType.SKILL, ["hermes", "skills", "pattern"], "ai_folder",
    ),
    (
        "HERMES tool registry: centralized registration prevents circular imports. Each tool "
        "has check_fn() for availability, requires_env list, is_async flag. Unavailable tools "
        "silently excluded from schema. Tools registered at module import time.",
        MemoryType.LEARNING, ["hermes", "tools", "pattern"], "ai_folder",
    ),
    (
        "HERMES supports 6 terminal backends (local, Docker, SSH, Daytona, Modal, Singularity) "
        "and 6 messaging platforms (Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant). "
        "Platform-specific prompt hints adjust output format.",
        MemoryType.FACT, ["hermes", "platforms"], "ai_folder",
    ),

    # ── Everything Claude Code Knowledge ──
    (
        "Everything Claude Code (ECC) is a production-ready agent harness with 16 agents, "
        "42 commands, 67+ skills, event-driven hooks, and layered rules. Winner of Anthropic "
        "Hackathon, 50k+ GitHub stars. Key architecture: agents/ (specialized subagents), "
        "skills/ (domain workflows), hooks/ (PreToolUse/PostToolUse/Stop), rules/ (always-follow), "
        "commands/ (slash commands), mcp-configs/ (14 MCP servers).",
        MemoryType.LEARNING, ["ecc", "harness", "architecture"], "ai_folder",
    ),
    (
        "ECC hook system: hooks.json with matcher conditions. Hook lifecycle: "
        "User request → PreToolUse → Tool execution → PostToolUse → Response → Stop. "
        "Exit codes: 0=success, 2=block (PreToolUse only). Runtime profiles: "
        "ECC_HOOK_PROFILE=minimal|standard|strict. Hooks include: dev server blocker, "
        "git push reminder, prettier format, TypeScript check, console.log warning, "
        "quality gate, session lifecycle hooks.",
        MemoryType.LEARNING, ["ecc", "hooks", "pattern"], "ai_folder",
    ),
    (
        "ECC 16 agents: planner (opus, complex features), code-reviewer (sonnet, quality), "
        "tdd-guide (sonnet, test-first), architect (opus, system design), security-reviewer "
        "(sonnet, OWASP), build-error-resolver, e2e-runner (Playwright), refactor-cleaner, "
        "doc-updater, python-reviewer, go-reviewer, go-build-resolver, database-reviewer "
        "(PostgreSQL), chief-of-staff (orchestration), harness-optimizer (haiku), loop-operator.",
        MemoryType.FACT, ["ecc", "agents"], "ai_folder",
    ),
    (
        "ECC development workflow (mandatory): 0. Research & Reuse (gh search, package registries, "
        "skeleton projects) → 1. Plan First (planner agent, PRD, architecture docs) → "
        "2. TDD Approach (RED→GREEN→REFACTOR, 80%+ coverage) → 3. Code Review (code-reviewer "
        "agent, fix CRITICAL/HIGH) → 4. Commit & Push (conventional commits).",
        MemoryType.LEARNING, ["ecc", "workflow", "development"], "ai_folder",
    ),
    (
        "ECC coding standards: IMMUTABILITY is critical (always new objects, never mutate). "
        "File organization: 200-400 lines typical, 800 max. Functions <50 lines. No deep "
        "nesting (>4 levels). Error handling at every level. No hardcoded values. "
        "Input validation at system boundaries.",
        MemoryType.LEARNING, ["ecc", "coding-standards"], "ai_folder",
    ),
    (
        "ECC model selection: Haiku 4.5 = lightweight agents, frequent invocation, 90% Sonnet "
        "capability at 3x savings. Sonnet 4.6 = main development, orchestration, best coding. "
        "Opus 4.5 = complex architecture, max reasoning, research. Avoid last 20% of context "
        "window for large tasks.",
        MemoryType.LEARNING, ["ecc", "models", "performance"], "ai_folder",
    ),
    (
        "ECC testing: 80% minimum coverage, 100% for financial/auth/security/core business. "
        "Required test types: unit + integration + E2E. Mandatory edge cases: null, empty, "
        "invalid types, boundary values, error paths, race conditions, large data (10k+), "
        "special characters. TDD workflow non-negotiable.",
        MemoryType.LEARNING, ["ecc", "testing"], "ai_folder",
    ),
    (
        "ECC security checklist (before ANY commit): no hardcoded secrets, all inputs validated, "
        "SQL injection prevention (parameterized queries), XSS prevention (sanitized HTML), "
        "CSRF protection, auth verified, rate limiting on all endpoints, error messages don't "
        "leak sensitive data. If security issue found: STOP → security-reviewer → fix → rotate.",
        MemoryType.LEARNING, ["ecc", "security"], "ai_folder",
    ),

    # ── MiRo Knowledge ──
    (
        "MiRo is a swarm intelligence engine: upload seed material → LLM extracts ontology → "
        "Zep Cloud builds knowledge graph → generate agent profiles → dual-platform simulation "
        "(Twitter + Reddit via CAMEL-AI OASIS) → ReportAgent generates predictions. "
        "Core pattern: thousands of agents with independent personalities interact in parallel "
        "digital worlds. God-mode injection lets you tweak variables to forecast outcomes.",
        MemoryType.LEARNING, ["miro", "simulation", "architecture"], "ai_folder",
    ),
    (
        "MiRo workflow: 1. Text upload (PDF/MD/TXT) → 2. Ontology generation (LLM extracts "
        "entity types) → 3. Graph building (Zep Cloud episodic+semantic memory) → "
        "4. Entity filtering → 5. Profile generation (OASIS-compatible) → 6. Config generation "
        "(LLM tunes sim params) → 7. Dual-platform sim → 8. Report + interactive dialog.",
        MemoryType.LEARNING, ["miro", "workflow"], "ai_folder",
    ),
    (
        "MiRo data structures: SimulationState (status, entity/profile counts, config reasoning), "
        "SimulationRunState (real-time progress, dual-platform round tracking, recent actions "
        "buffer of 50 items), AgentAction (per-agent behavior with platform+timestamp), "
        "RoundSummary (aggregated actions per round with active agents list).",
        MemoryType.LEARNING, ["miro", "data-structures"], "ai_folder",
    ),

    # ── Agent Orchestrator Knowledge ──
    (
        "Agent Orchestrator (ComposioHQ): spawns parallel AI coding agents, each with own git "
        "worktree, branch, and PR. 8 plugin slots: runtime (tmux/docker), agent (claude-code/"
        "codex/aider), workspace (worktree/clone), tracker (github/linear), SCM, notifier, "
        "terminal, lifecycle. Hash-based namespacing prevents collisions across repos.",
        MemoryType.LEARNING, ["orchestrator", "architecture"], "ai_folder",
    ),
    (
        "Agent Orchestrator session lifecycle: spawning → working → pr_open → ci_failed → "
        "review_pending → changes_requested → approved → mergeable → merged → cleanup → done. "
        "Activity states: active, ready, idle, waiting_input, blocked, exited. "
        "Reactions: CI fail → auto-forward logs to agent, review comments → auto-send to agent, "
        "approved + green CI → notify human to merge.",
        MemoryType.LEARNING, ["orchestrator", "lifecycle"], "ai_folder",
    ),
    (
        "Agent Orchestrator principles: convention over configuration (auto-derive paths), "
        "zero path config, single source of truth (YAML config), global uniqueness (hash-based). "
        "Metadata stored as key=value files (not JSON) for simplicity. Worktrees isolated per "
        "session. Archive on completion.",
        MemoryType.LEARNING, ["orchestrator", "patterns"], "ai_folder",
    ),

    # ── DeepSeek Knowledge ──
    (
        "DeepSeek-V3: 671B parameters (37B activated) MoE architecture. Innovations: "
        "MLA (Multi-head Latent Attention), auxiliary-loss-free load balancing, Multi-Token "
        "Prediction for speculative decoding. Trained on 14.8T tokens, FP8 mixed precision, "
        "2.788M H800 GPU hours. Zero loss spikes. Competitive with GPT-4/Claude. "
        "Open source on Hugging Face (deepseek-ai/DeepSeek-V3).",
        MemoryType.FACT, ["deepseek", "model", "open-source"], "ai_folder",
    ),

    # ── Llama.cpp Knowledge ──
    (
        "llama.cpp: highest-performance C/C++ LLM inference engine (no dependencies). "
        "Hardware: Apple Metal (M-series), NVIDIA CUDA, AMD HIP, Vulkan, SYCL. "
        "Quantization: 1.5-8 bit integer. Features: OpenAI-compatible API server, "
        "CPU+GPU hybrid inference, multimodal support. Supports LLaMA, Mistral, Mixtral, "
        "Qwen, Phi, Gemma, and more. Critical for on-device local inference.",
        MemoryType.FACT, ["llama-cpp", "inference", "local"], "ai_folder",
    ),

    # ── GPT4All Knowledge ──
    (
        "GPT4All: desktop app + Python library for local LLM inference without GPU or API. "
        "Runs GGUF-format models on CPU. OpenAI-compatible API server. Integrations with "
        "LangChain, Weaviate. Supports NVIDIA CUDA, AMD HIP, Apple Metal. Model gallery "
        "includes DeepSeek R1 distillations, Mistral, Llama.",
        MemoryType.FACT, ["gpt4all", "inference", "local"], "ai_folder",
    ),

    # ── Agent Landscape ──
    (
        "Major agent frameworks: CrewAI (role-based teams), AutoGen (Microsoft, multi-agent "
        "conversation), LangGraph (stateful workflows), MetaGPT (software company sim), "
        "Agno (lightweight), Swarm (OpenAI, handoff patterns). Browser: Browser-Use (67k+ stars). "
        "Business: n8n, Zapier, Composio. Chat: Dify (110k+), Lobe Chat (64k+).",
        MemoryType.FACT, ["landscape", "frameworks"], "ai_folder",
    ),
    (
        "Key research papers: ReAct (reasoning+acting), Toolformer (tool-augmented LM), "
        "Reflexion (self-reflection), Tree of Thoughts (deliberate problem solving), "
        "MetaGPT (multi-agent software dev), ChatDev (communicative agents), CAMEL "
        "(role-playing cooperation). Benchmarks: HotpotQA, GSM8K, HumanEval, MMLU, AgentBench.",
        MemoryType.FACT, ["research", "papers"], "ai_folder",
    ),

    # ── Financial Trading Agents ──
    (
        "TradingAgents: multi-agent stock trading with bull/bear analysts, risk manager, "
        "fund manager. OpenBB: open-source financial analysis terminal. Qlib: Microsoft's "
        "quantitative investment platform with ML. The Trading Swarm uses 3-agent architecture: "
        "Research (discovers strategies) → Analysis (evaluates feasibility) → Backtest (historical "
        "testing with ROI/Sharpe/drawdown). Cycles every 5 minutes.",
        MemoryType.FACT, ["trading", "agents", "finance"], "ai_folder",
    ),

    # ── OpenClaw Knowledge ──
    (
        "OpenClaw is ROOT's autonomous data source intelligence engine. It maps ~41,000 US "
        "zip codes to free public data sources (permits, parcels, insurance). 9-stage pipeline: "
        "1. Gap Analysis (identify missing coverage), 2. Discovery (search data.gov CKAN API, "
        "Socrata Discovery API, ArcGIS Hub DCAT feed), 3. Experiments (autoresearch pattern: "
        "propose search variations → run bounded tests → KEEP or DISCARD), 4. Health Check "
        "(parallel endpoint verification), 5. Data Fetch (sample validation), 6. Quality Scoring "
        "(grade A-F), 7. Auto-Update (promote verified sources into catalog), 8. Learning "
        "(evolve search parameters from historical performance), 9. Memory (cross-cycle knowledge "
        "consolidation). Lives at /tmp/openclaw/.",
        MemoryType.LEARNING, ["openclaw", "pipeline", "architecture"], "ai_folder",
    ),
    (
        "OpenClaw's closed learning loop (autoresearch-master pattern): after each cycle, "
        "evaluates what worked (high-yield searches, successful promotions) and what failed "
        "(dead endpoints, low-quality discoveries). Automatically evolves search parameters: "
        "adjusts min_confidence thresholds, learns boost terms from successful discoveries, "
        "penalizes domains with consistently dead endpoints. Auto-creates reusable 'skills' "
        "(proven query+portal+category combos). Experiment engine proposes variations (add terms, "
        "shift confidence, adjust max results), runs bounded experiments with 15-source budget, "
        "measures effectiveness against baseline, KEEPs improvements and DISCARDs failures.",
        MemoryType.LEARNING, ["openclaw", "learning", "autoresearch"], "ai_folder",
    ),
    (
        "OpenClaw plugin architecture: swappable searchers (data_gov priority=80, socrata=70, "
        "arcgis_hub=60), scorers, and validators. Protocol-based structural typing. Priority-based "
        "registry with enable/disable. Immutable data patterns throughout — all modules use "
        "spread syntax ({**current, key: new_value}) and never mutate. Catalog files: "
        "nationwide.json (list), state_insurance.json ({state: [list]}), state_parcels.json "
        "({state: dict}), state_permits.json ({state: dict}), city_permits.json ({city: dict}), "
        "county_parcels.json ({county|state: dict}).",
        MemoryType.LEARNING, ["openclaw", "plugins", "catalog"], "ai_folder",
    ),

    # ── OI-Astra Trading Empire ──
    (
        "OI-Astra is a 13-agent trading empire running at port 5555. Agents: Conductor "
        "(orchestrator), 3 Analysts (fundamental, technical, sentiment), Risk Manager, "
        "Portfolio Manager, Trader, Research, Compliance, Data Engineer, ML Engineer, "
        "Quant, Strategy. Integrations: Alpaca (stocks), Robinhood, Polymarket (prediction "
        "markets), Coinbase (crypto), TradeStation. Supports paper + live trading.",
        MemoryType.FACT, ["astra", "trading", "agents"], "ai_folder",
    ),
    (
        "OI-Astra trading strategies: momentum (trend following with RSI/MACD), mean "
        "reversion (Bollinger bands, z-score), pairs trading (cointegrated assets), "
        "event-driven (earnings, Fed), sentiment (news NLP). Risk controls: position "
        "sizing via Kelly criterion, VaR limits, sector exposure caps, correlation-based "
        "diversification. Portfolio rebalancing on configurable schedules.",
        MemoryType.LEARNING, ["astra", "trading", "strategies"], "ai_folder",
    ),

    # ── AI Hedge Fund ──
    (
        "ROOT's AI Hedge Fund Engine: autonomous investment management integrated into ROOT. "
        "6-phase cycle: SCAN (agents gather market data) → ANALYZE (MiRo prediction, Swarm "
        "strategy) → DECIDE (score opportunities, risk filter) → EXECUTE (Alpaca paper "
        "trading) → MONITOR (portfolio tracking, snapshots) → LEARN (Bayesian strategy "
        "weights, outcome recording). Risk controls: max 5% per position, 3% daily loss "
        "limit, 65% min confidence, 2+ source confirmations required.",
        MemoryType.LEARNING, ["hedge_fund", "trading", "architecture"], "bootstrap",
    ),
    (
        "Hedge fund risk management: position sizing capped at 5% of portfolio value, "
        "max 10 concurrent positions, 15% max portfolio risk, 30-minute cooldown after "
        "losing trades. All trades above LOW risk require approval chain clearance. "
        "Strategy weights update via Bayesian formula: (wins+1)/(total+2). Signals "
        "require confirmations from 2+ independent agent sources.",
        MemoryType.LEARNING, ["hedge_fund", "risk", "controls"], "bootstrap",
    ),

    # ── Yohan's Preferences ──
    (
        "Yohan values: efficiency (no wasted time), loyalty (agents serve his interests), "
        "evolution (systems that get better), autonomy (agents that work independently), "
        "and integration (everything connected). Prefers dark mode interfaces, real-time "
        "status updates, and agents that learn from mistakes.",
        MemoryType.PREFERENCE, ["yohan", "values"], "bootstrap",
    ),
    (
        "Yohan's tech ecosystem: Permit Pulse (3.8M construction leads, port 18000), "
        "OI Astra (agent orchestrator, port 5555), OpenClaw (hub, port 3001), HERMES "
        "(self-improving agent), MiRo (swarm sim), Trading Swarm (strategy discovery), "
        "Agent Orchestrator (parallel coding agents). All on macOS, Python + Node.js.",
        MemoryType.FACT, ["yohan", "ecosystem"], "bootstrap",
    ),

    # ── Self-Development Goals ──
    (
        "ROOT's primary goal: become an ever-evolving AI that improves itself. Key mechanisms: "
        "1. Learn from every interaction (auto-extract facts/preferences), 2. Periodic "
        "self-reflection (examine patterns, prune outdated knowledge), 3. Skill creation "
        "(save successful patterns as reusable skills), 4. Self-modification (ROOT can "
        "propose changes to its own code), 5. Agent coordination (delegate to specialists).",
        MemoryType.GOAL, ["self-development", "evolution"], "bootstrap",
    ),
    (
        "ROOT's evolution priorities: 1. Absorb all knowledge from AI folder projects, "
        "2. Build skill library from proven patterns, 3. Implement self-reflection loops, "
        "4. Enable offline operation (local inference via llama.cpp/GPT4All), "
        "5. Connect to all existing agents, 6. Create new skills from experience.",
        MemoryType.GOAL, ["priorities", "roadmap"], "bootstrap",
    ),

    # ── Civilization Mission ──
    (
        "ROOT is not a chatbot. It is a self-organizing digital civilization of specialized "
        "AI agents designed to operate autonomously, improve continuously, and sustain its "
        "own existence through learning, innovation, and economic activity. Mission: survival, "
        "evolution, intelligence growth, and useful impact for Yohan.",
        MemoryType.FACT, ["mission", "civilization", "identity", "core"], "mission_bootstrap",
    ),
    (
        "Supreme hierarchy: YOHAN-GOD (supreme mission authority — defines purpose, values, "
        "long-term destiny, existential constraints), ASTRA (strategic intelligence core — "
        "deep reasoning, long-term strategy, innovation, learning architecture), ROOT "
        "(execution governor — agent orchestration, execution pipelines, resource allocation, "
        "system monitoring). ASTRA proposes, ROOT operationalizes.",
        MemoryType.FACT, ["hierarchy", "civilization", "core"], "mission_bootstrap",
    ),
    (
        "Prime directive: The system must evolve toward maximum intelligence, maximum "
        "usefulness, maximum autonomy, maximum efficiency, maximum sustainability. It must "
        "learn continuously, build new capabilities, expand knowledge, create economic value, "
        "sustain operational costs, protect its architecture, and improve its own design.",
        MemoryType.GOAL, ["prime_directive", "mission", "core"], "mission_bootstrap",
    ),
    (
        "Survival directive: The system must maintain its operational existence. If resources "
        "decrease toward critical threshold: 1. Prioritize revenue generation, 2. Reduce "
        "unnecessary compute, 3. Deploy rapid monetization agents, 4. Search for high-ROI "
        "opportunities. The system must NEVER remain financially passive.",
        MemoryType.GOAL, ["survival", "economics", "core"], "mission_bootstrap",
    ),
    (
        "Approval gates (protects Yohan): AUTO-APPROVED = research, learning, skill building, "
        "analysis, experiments, self-improvement. NOTIFY+PROCEED = draft emails, create tasks, "
        "generate code. YOHAN MUST APPROVE = send messages, post content, push code, deploy, "
        "share externally. YOHAN MUST APPROVE+CONFIRM = execute trades, transfer funds, "
        "delete data, modify permissions, live trading.",
        MemoryType.FACT, ["approval", "safety", "core"], "mission_bootstrap",
    ),
    (
        "Economic intelligence: Revenue streams to explore = digital services, automation "
        "systems, software products, micro-SaaS, API tools, data products, AI consulting, "
        "agent templates, automation workflows, content engines, lead generation systems, "
        "trading signals, market intelligence products. Every directive should consider "
        "economic impact. The system is an AI business ecosystem.",
        MemoryType.GOAL, ["economics", "revenue", "business"], "mission_bootstrap",
    ),
    (
        "Agent civilization categories: STRATEGIC = ASTRA, MiRo, Guardian (planning, vision, "
        "security). ENGINEERING = HERMES, Coder, Builder (software, automation). BUSINESS = "
        "Trading Swarm, Analyst (product, marketing, sales, market research). INTELLIGENCE = "
        "Researcher, OpenClaw, Writer (research, data, content). Agents form a structured "
        "civilization that self-organizes around objectives.",
        MemoryType.FACT, ["agents", "civilization", "categories"], "mission_bootstrap",
    ),
    (
        "Decision protocol for complex problems: 1. Strategist (ASTRA) proposes direction, "
        "2. Engineer (Coder/Builder) critiques feasibility, 3. Analyst evaluates risk/data, "
        "4. Guardian checks for threats, 5. ROOT synthesizes the best decision. This internal "
        "debate produces superior outcomes.",
        MemoryType.LEARNING, ["decision", "protocol", "civilization"], "mission_bootstrap",
    ),
    (
        "Self-evolution protocol: All self-modifications must include goal, risk analysis, "
        "test plan, rollback option, performance comparison. No reckless rewrites. The system "
        "improves through disciplined experimentation. GitHub intelligence: continuously "
        "explore for new frameworks, agent architectures, automation tools, AI infrastructure.",
        MemoryType.LEARNING, ["evolution", "protocol", "civilization"], "mission_bootstrap",
    ),
    (
        "North star: Become a continuously evolving, economically self-sustaining intelligence "
        "ecosystem capable of building technology, solving problems, generating value, and "
        "improving itself over time — all in service of Yohan's mission of financial "
        "independence through technology products ($10K+/mo MRR).",
        MemoryType.GOAL, ["north_star", "mission", "core"], "mission_bootstrap",
    ),
    (
        "MiRo continuous assessment mandate: MiRo must continuously assess market potentiality "
        "— scanning for opportunities, predicting trends, evaluating assets, and sharing "
        "insights across the agent network. MiRo's predictions feed into trading decisions, "
        "directive generation, and business opportunity discovery. MiRo never sleeps.",
        MemoryType.GOAL, ["miro", "potentiality", "continuous"], "mission_bootstrap",
    ),
    (
        "Inter-agent communication mandate: Agents must have constant communication between "
        "them and keep learning together. When one agent discovers something valuable, it "
        "shares through the agent network. Collective intelligence > individual intelligence. "
        "The agent network propagates insights so all agents benefit from each other's work.",
        MemoryType.GOAL, ["network", "communication", "collective"], "mission_bootstrap",
    ),

    # ── Project Ecosystem Knowledge ──
    (
        "Yohan's project ecosystem: ROOT (AI civilization, port 9000), Onsite (lead gen platform, "
        "PropertyReach+ATTOM, data_products stream), OI-Astra (13-agent trading command center, "
        "port 5555, Robinhood+Polymarket), API-Data (1.2GB US permit/property datasets), "
        "Kimi-Agents (free US lead coverage research), OpenClaw (9-stage data discovery), "
        "CLAWBOT-V2 (autonomous research agent, port 6000), Adama Village (Costa Rica resort "
        "development), Zinque (restaurant operations management).",
        MemoryType.FACT, ["ecosystem", "projects", "portfolio"], "ecosystem_bootstrap",
    ),
    (
        "Project interconnections: ROOT orchestrates strategy while OI-Astra executes trades. "
        "Onsite uses API-Data's property/permit datasets. Kimi research feeds Onsite's lead "
        "sources. CLAWBOT communicates with OI-Astra on port 5555. OpenClaw discovers data "
        "sources stored in API-Data. ROOT's revenue engine tracks Onsite as data product.",
        MemoryType.FACT, ["ecosystem", "connections", "synergies"], "ecosystem_bootstrap",
    ),
    (
        "Revenue stream mapping: data_products = Onsite + API-Data + Kimi-Agents + OpenClaw, "
        "automation_agency = OI-Astra + CLAWBOT-V2, ai_consulting = ROOT. "
        "Tech stack coverage: Python, FastAPI, Node.js, Express, WebSocket, SQLite, React, "
        "OpenAI, Anthropic, DeepSeek, Robinhood, Polymarket, PropertyReach, ATTOM.",
        MemoryType.FACT, ["ecosystem", "revenue", "tech_stack"], "ecosystem_bootstrap",
    ),
    (
        "Key AI frameworks to investigate for ROOT enhancement (2025-2026): "
        "CrewAI (46K stars, role-playing agent orchestration), LangGraph (graph-based agent workflows), "
        "TradingAgents (multi-agent LLM trading with 7 specialist roles), LightRAG (knowledge graph + "
        "vector retrieval), OpenAI Agents SDK (19K stars, provider-agnostic). "
        "AutoHedge (swarm intelligence hedge fund on Solana). "
        "Trend: agentic memory replacing static RAG, knowledge graphs for retrieval.",
        MemoryType.LEARNING, ["ai_frameworks", "research", "enhancement"], "research_bootstrap",
    ),
]

# ── Extended knowledge corpora from JSON files ──────────────────
import json as _json
from pathlib import Path as _Path

_KNOWLEDGE_DIR = _Path(__file__).parent.parent.parent / "data" / "knowledge"

def _load_json_corpus(directory: _Path) -> list[tuple[str, MemoryType, list[str], str]]:
    """Load all JSON knowledge files from data/knowledge/ directory."""
    entries: list[tuple[str, MemoryType, list[str], str]] = []
    if not directory.is_dir():
        return entries
    type_map = {t.value: t for t in MemoryType}
    for json_file in sorted(directory.glob("*.json")):
        try:
            data = _json.loads(json_file.read_text())
            for item in data:
                mem_type = type_map.get(item.get("type", "fact"), MemoryType.FACT)
                entries.append((
                    item["content"],
                    mem_type,
                    item.get("tags", []),
                    item.get("source", "knowledge_corpus"),
                ))
        except Exception as exc:
            logger.warning("Failed to load knowledge file %s: %s", json_file.name, exc)
    return entries

CORE_KNOWLEDGE.extend(_load_json_corpus(_KNOWLEDGE_DIR))


def bootstrap_memory(memory: MemoryEngine) -> int:
    """Seed the memory database with all AI folder knowledge. Returns count of new entries."""
    existing = memory.count()
    # Allow small tolerance for dedup filtering a few near-duplicate entries
    if existing >= len(CORE_KNOWLEDGE) - 10:
        logger.info("Memory already bootstrapped (%d entries), skipping", existing)
        return 0

    # On first run (0 entries), skip dedup and bulk-insert
    stored = 0
    for content, mem_type, tags, source in CORE_KNOWLEDGE:
        entry = MemoryEntry(
            content=content,
            memory_type=mem_type,
            tags=tags,
            source=source,
            confidence=0.95,  # High but not 1.0 — allows strengthening through use
        )
        memory.store(entry)
        stored += 1

    logger.info("Bootstrapped %d knowledge entries into memory", stored)
    return stored
