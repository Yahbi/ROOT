# ROOT v1.0.0 — ASTRA-ROOT Autonomous Intelligence Civilization

## Governance
- **Yohan**: Supreme authority — approves major architecture changes, large financial decisions, system expansions
- **ASTRA**: Strategic intelligence core — reasoning, opportunity discovery, learning direction
- **ROOT**: Execution governor — task routing, agent coordination, infrastructure, resource allocation
- Major decisions require Yohan approval with reason + benefit + risk analysis

## Architecture
- FastAPI backend at `backend/main.py`, port 9000
- SQLite databases: memory.db, conversations.db, learning.db, hedge_fund.db, state.db, task_queue.db, user_patterns.db, goals.db, escalation.db, triggers.db, digests.db, predictions.db, experience.db, experiments.db, self_code.db, revenue.db
- 33 SKILL.md files across 15 categories in `data/skills/`
- 686 bootstrapped knowledge entries (memory engine)
- Online brain (OpenAI/Anthropic) + Offline brain (local knowledge fallback + LLM crash recovery)
- 12 core agents + 150+ civilization agents across 10 divisions
- LLM service: 3 tiers (Haiku=fast, Sonnet=default, Opus=thinking) + exponential retry + fallback
- 11 plugins with 24 tools (including Alpaca paper trading)
- 8 autonomous background loops + directive engine + action chains
- Notification bridge: Telegram + Discord push alerts
- 3-layer memory: short-term (in-memory) + long-term (SQLite) + experience (wisdom)
- 5-stream revenue engine ($10k-$100k/month target)

## Core Systems (40+ modules)
- **Memory Engine**: SQLite + FTS5, confidence decay/strengthen, supersession, deduplication
- **Experience Memory**: 3-layer system — short-term context, long-term knowledge, experience wisdom (success/failure/strategy/lesson)
- **Learning Engine**: Interaction scoring, Bayesian routing weights (wired into ASTRA), experiment tracking
- **Skill Engine**: HERMES-style SKILL.md files with YAML frontmatter
- **Hook Engine**: 7 event-driven hooks (error learning, routing feedback, memory logging, etc.)
- **Reflection Engine**: Self-improvement + automatic action execution (routing boosts, skill creation, goal setting)
- **Self-Dev Engine**: Evolution tracking, gap analysis, skill creation, maturity scoring
- **Context Manager**: HERMES-style compression at 85% utilization
- **Orchestrator**: Parallel agent task coordination (max 3 concurrent, 120s timeout)
- **Knowledge Bootstrap**: Seeds memory from AI folder projects
- **Brain**: Central reasoning — ASTRA routing (learning-weighted) → agent dispatch → LLM → response
- **Offline Brain**: Local knowledge + skill matching (auto-fallback when LLM unavailable)
- **Agent Collaboration**: 4 patterns — delegate, pipeline, fanout, council
- **Message Bus**: Inter-agent pub/sub with wildcard topics
- **Approval Chain**: Risk-based decisions (low=auto, medium=notify+escalation, high/critical=manual) + reason/benefit/risk analysis
- **Proactive Engine**: 17 autonomous background behaviors on intervals (state persisted, action chains)
- **Autonomous Loop**: Self-improving cycle (assess → propose → execute → evaluate → learn) + LLM-generated experiments
- **Builder Agent**: Dynamic skill creation + gap filling every 5 minutes
- **Task Executor**: Autonomous goal decomposition → multi-step execution → self-correction
- **Task Queue**: Persistent task queue with crash recovery
- **Goal Engine**: Autonomous goal management, decomposition, stall detection
- **Hedge Fund Engine**: AI trading with Alpaca, signal generation, risk controls, position monitoring
- **Money Engine**: LLM-powered Strategy Council (real agent fanout) for wealth/opportunity analysis
- **Revenue Engine**: 5-stream revenue system (automation agency, micro SaaS, content network, data products, AI consulting) + financial survival system ($400/mo minimum)
- **Experiment Lab**: Continuous testing of SaaS ideas, marketing strategies, pricing models, trading strategies — successful experiments scale, failures become lessons
- **Self-Writing Code**: Engineering agents propose code improvements (detect → generate → test → benchmark → deploy) — major rewrites require Yohan approval
- **Interest Engine**: Evaluates decisions against Yohan's profile and goals
- **Plugin Engine**: 11 plugins, 24 tools (state persisted via StateStore)
- **Conversation Store**: Persistent chat sessions with SQLite
- **State Store**: Persistent runtime state for proactive actions, experiments, plugin logs
- **Notification Engine**: Push alerts via Telegram Bot API + Discord webhooks (priority-based delivery)
- **User Pattern Engine**: Behavioral learning and anticipation
- **Escalation Engine**: Confidence-gated autonomous decisions
- **Trigger Engine**: Event-driven automation rules
- **Digest Engine**: Daily/weekly autonomous reporting
- **Directive Engine**: Autonomous strategic decisions every 15min (chaining + historical feedback)
- **Agent Network**: Inter-agent knowledge sharing + propagation
- **Prediction Ledger**: Tracks predictions from MiRo/Swarm/Directive with calibration scoring per source + confidence bucket
- **Action Chain Engine**: Reactive pipelines connecting proactive behaviors (scan → trade, health → notify, etc.)
- **Security Middleware**: API key auth (timing-safe), rate limiting (100 RPM), security headers

## Agent Civilization (162+ agents)
### Core Agents (12)
ASTRA (Strategic Intelligence), ROOT (Execution Governor), HERMES (Autonomous Agent), MiRo (Potentiality Engine), Trading Swarm (Economic Agent), OpenClaw (Data Source Intelligence), Builder (Self-Improvement), Researcher (Intelligence), Coder (Software Engineer), Writer (Content & Marketing), Analyst (Business Intelligence), Guardian (Security & Integrity)

### Civilization Divisions (150 agents)
1. **Strategy Council** (15): Vision Architect, Future Trends, Opportunity Hunter, Economic/Risk Strategist, Innovation Designer, etc.
2. **Research Division** (20): Paper Miner, GitHub Intel, Patent Discovery, Tech Radar, AI Model Researcher, etc.
3. **Engineering Division** (30): Chief Architect, Backend/Frontend/DevOps/Security Engineers, Performance Optimizer, etc.
4. **Data & Memory Division** (15): Dataset Builder, Knowledge Graph Architect, Vector DB Manager, Signal Detection, etc.
5. **Learning & Improvement** (20): Experiment Designer, Failure Analyst, Prompt Optimizer, Self-Improvement Planner, etc.
6. **Economic Engine** (20): Opportunity Scanner, Startup Builder, SaaS Creator, Marketing Strategist, Revenue Optimizer, etc.
7. **Content Network** (10): Article Generator, Video Script Creator, Course Builder, Newsletter Agent, etc.
8. **Automation Business** (10): Lead Scraping, Email Outreach, Workflow Automation, Bot Builder, etc.
9. **Infrastructure Operations** (10): Compute Manager, Cloud Cost Optimizer, DR Agent, Scaling Agent, etc.
10. **Governance & Safety** (10): Alignment Monitor, Ethics Monitor, Hallucination Detector, Cost Controller, etc.

## Project structure
```
ROOT/
├── backend/
│   ├── main.py                   # FastAPI entry + lifespan wiring 40+ systems
│   ├── config.py                 # Env-driven settings (.env) + VERSION constant
│   ├── core/
│   │   ├── memory_engine.py      # SQLite + FTS5 persistent memory
│   │   ├── experience_memory.py  # 3-layer memory (short-term + long-term + experience)
│   │   ├── learning_engine.py    # Outcome tracking + adaptive routing
│   │   ├── skill_engine.py       # SKILL.md procedural memory
│   │   ├── hook_engine.py        # 7 event-driven hooks
│   │   ├── reflection.py         # Self-reflection + automatic action execution
│   │   ├── self_dev.py           # Evolution tracking & gap analysis
│   │   ├── context_manager.py    # Context compression & windowing
│   │   ├── orchestrator.py       # Parallel agent coordination
│   │   ├── knowledge_bootstrap.py # Seeds memory from AI folder
│   │   ├── brain.py              # Online brain (ASTRA routing + offline fallback)
│   │   ├── offline_brain.py      # Offline brain (local knowledge only)
│   │   ├── agent_collab.py       # Delegate/pipeline/fanout/council
│   │   ├── message_bus.py        # Inter-agent pub/sub
│   │   ├── approval_chain.py     # Risk-based approval (4 levels + governance)
│   │   ├── proactive_engine.py   # 17 autonomous behaviors (state persisted)
│   │   ├── autonomous_loop.py    # Self-improvement cycle (30min)
│   │   ├── builder_agent.py      # Dynamic skill/knowledge creation
│   │   ├── hedge_fund.py         # AI trading + Alpaca + position monitoring
│   │   ├── money_engine.py       # LLM-powered Strategy Council
│   │   ├── revenue_engine.py     # 5-stream revenue system + financial survival
│   │   ├── experiment_lab.py     # Continuous experimentation engine
│   │   ├── self_writing_code.py  # Self-writing code system (detect→test→deploy)
│   │   ├── interest_engine.py    # Interest alignment assessment
│   │   ├── plugin_engine.py      # 11 plugins, 24 tools
│   │   ├── conversation_store.py # Chat session persistence
│   │   ├── state_store.py        # Persistent runtime state (SQLite WAL)
│   │   ├── notification_engine.py # Push alerts (Telegram + Discord)
│   │   ├── task_queue.py         # Persistent task queue
│   │   ├── user_patterns.py      # Behavioral learning
│   │   ├── goal_engine.py        # Autonomous goal management
│   │   ├── escalation_engine.py  # Confidence-gated decisions
│   │   ├── trigger_engine.py     # Event-driven automation
│   │   ├── digest_engine.py      # Daily/weekly reporting
│   │   ├── directive_engine.py   # Strategic autonomous directives
│   │   ├── agent_network.py      # Inter-agent knowledge sharing
│   │   ├── prediction_ledger.py  # Prediction tracking + calibration
│   │   └── action_chains.py      # Reactive pipelines
│   ├── models/
│   │   ├── agent.py              # Agent, task, chat models (Pydantic)
│   │   └── memory.py             # Memory, reflection models
│   ├── agents/
│   │   ├── registry.py           # Agent catalog (12 core + 150 civilization)
│   │   ├── civilization.py       # 150+ civilization agents across 10 divisions
│   │   └── connectors/
│   │       ├── hermes.py         # HERMES autonomous executor
│   │       ├── astra.py          # ASTRA team leader + learning-weighted routing
│   │       ├── miro.py           # MiRo council debate + prediction tracking
│   │       ├── swarm.py          # Trading Swarm strategy research
│   │       ├── openclaw.py       # OpenClaw 9-stage data discovery
│   │       └── internal.py       # 6 internal agents
│   ├── routes/
│   │   ├── chat.py               # /api/chat
│   │   ├── agents.py             # /api/agents
│   │   ├── memory.py             # /api/memory
│   │   ├── dashboard.py          # /api/dashboard
│   │   ├── autonomous.py         # /api/autonomous
│   │   ├── hedge_fund.py         # /api/hedge-fund
│   │   ├── money.py              # /api/money + /api/money/council/online
│   │   ├── plugins.py            # /api/plugins
│   │   ├── builder.py            # /api/builder
│   │   ├── conversations.py      # /api/conversations
│   │   ├── interest.py           # /api/interest
│   │   ├── tasks.py              # /api/tasks
│   │   ├── autonomy.py           # /api/autonomy
│   │   └── civilization.py       # /api/civilization (agents, experience, experiments, revenue, code)
│   ├── security/
│   │   └── middleware.py          # Pure ASGI: API key auth + rate limiter + security headers
│   ├── services/
│   │   ├── llm.py                # Anthropic LLM (retry + LLMUnavailableError)
│   │   ├── llm_openai.py         # OpenAI LLM (retry + fallback)
│   │   └── task_router.py        # Intent routing
│   └── static/                   # Dashboard frontend (HTML/CSS/JS)
├── data/
│   ├── memory.db                 # Memories with FTS5
│   ├── conversations.db          # Chat sessions
│   ├── learning.db               # Agent outcomes + routing weights
│   ├── hedge_fund.db             # Signals, trades, portfolio snapshots
│   ├── state.db                  # Runtime state (proactive, experiments, plugins)
│   ├── task_queue.db             # Persistent task queue
│   ├── goals.db                  # Goal management
│   ├── predictions.db            # Prediction tracking + calibration
│   ├── experience.db             # Experience memory (success, failure, strategy, lesson)
│   ├── experiments.db            # Experiment lab data
│   ├── self_code.db              # Self-writing code proposals
│   ├── revenue.db                # Revenue products and transactions
│   ├── evolution_log.json        # Self-dev evolution history
│   ├── skills/                   # 33 SKILL.md files in 15 categories
│   ├── reflections/              # Reflection JSON logs
│   └── hooks/                    # Hook configs
├── tests/                        # 283 tests (pytest)
├── requirements.txt
└── .env                          # API keys + TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL
```

## Running
```bash
cd ~/Desktop/ROOT
source .venv/bin/activate
python -m backend.main         # Runs on port 9000
# Requires: OPENAI_API_KEY or ANTHROPIC_API_KEY in .env
# Optional: ALPACA_API_KEY + ALPACA_API_SECRET for paper trading
# Optional: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID for push notifications
# Optional: DISCORD_WEBHOOK_URL for Discord alerts
```

## Background Loops (autonomous)
- **Reflection**: Every 1 hour — self-reflection + insight extraction + action execution
- **Proactive Engine**: 17 behaviors (health 5min, market 30min, goals 1hr, trading 1hr, etc.) + action chains
- **Autonomous Loop**: Every 30 min — assess → propose (LLM-generated) → execute → evaluate → learn
- **Builder**: Every 5 min — gap analysis → skill creation → knowledge expansion
- **Memory Decay**: Every 24 hours — confidence decay on unused memories
- **Triggers**: Event-driven automation rules
- **Agent Network**: Inter-agent knowledge propagation
- **Directive Engine**: Strategic autonomous decisions every 15min (chaining depth 3)

## Key API Endpoints
- `POST /api/chat` — main chat (ASTRA routes with learned weights → agents → LLM → response)
- `POST /api/tasks` — submit autonomous task (goal → decompose → execute → result)
- `GET /api/tasks` — list all tasks with status
- `POST /api/autonomous/delegate` — agent-to-agent delegation
- `POST /api/autonomous/fanout` — parallel multi-agent execution
- `POST /api/autonomous/council` — multi-agent consensus
- `POST /api/hedge-fund/cycle` — full trading cycle (scan → analyze → trade)
- `POST /api/money/council/online` — LLM-powered multi-agent strategy council
- `GET /api/civilization/agents` — list all 162+ agents with divisions
- `GET /api/civilization/agents/divisions` — division breakdown
- `POST /api/civilization/experience` — record experience (success/failure/strategy/lesson)
- `GET /api/civilization/experience` — query experiences
- `POST /api/civilization/experiments` — propose experiments
- `GET /api/civilization/experiments` — list experiments by status/category
- `POST /api/civilization/code-proposals` — submit self-writing code proposals
- `POST /api/civilization/revenue/products` — add revenue products
- `GET /api/civilization/revenue/snapshot` — financial snapshot + emergency mode
- `GET /api/civilization/status` — full civilization overview
- `GET /api/dashboard/status` — full system status with agent health
- `GET /api/health` — version + mode check

## Key design decisions
- Immutable Pydantic models + frozen dataclasses (model_copy for updates)
- Memory confidence scores decay/strengthen over time
- 3-layer memory: short-term (task context) + long-term (knowledge) + experience (wisdom)
- Works fully offline using local knowledge + skill matching (auto-fallback on LLM failure)
- Pure ASGI middleware (no BaseHTTPMiddleware)
- 3-layer security: API key auth (timing-safe hmac.compare_digest) → rate limiter → security headers
- Approval chain gates risky actions + governance: architecture/financial/expansion changes require Yohan approval with reason+benefit+risk
- Learning engine uses Bayesian routing weights, wired into ASTRA's routing prompt
- Reflection actions auto-execute: routing boosts, skill creation, goal setting, knowledge gap filing
- LLM retry with exponential backoff (3 attempts) + offline brain fallback
- Runtime state persists across restarts (StateStore with SQLite WAL)
- Notification bridge pushes HIGH/CRITICAL alerts to Telegram/Discord
- Hedge fund enforces risk limits: 5% max position, 15% portfolio, 3% daily loss + position monitoring
- 150+ civilization agents across 10 divisions (Strategy, Research, Engineering, Data, Learning, Economic, Content, Automation, Infrastructure, Governance)
- Self-writing code requires Yohan approval for major rewrites
- Revenue engine tracks 5 streams with financial survival system ($400/mo minimum)
- Experiment lab: successful experiments scale, failed experiments become experience memory lessons

## v1.0.0 changelog (from v0.9.0)
- **ASTRA-ROOT Civilization**: 150+ specialized agents across 10 divisions (Strategy Council, Research, Engineering, Data & Memory, Learning & Improvement, Economic Engine, Content Network, Automation Business, Infrastructure Operations, Governance & Safety)
- **Governance Protocol**: Major architecture changes, large financial decisions, and system expansions require Yohan approval with reason+benefit+risk analysis
- **Experience Memory**: 3-layer memory system — short-term (active task context, in-memory), long-term (existing MemoryEngine), experience (success patterns, failures, strategies, lessons learned in SQLite)
- **Revenue Engine**: 5-stream automated revenue system ($10k-$100k/month target) — automation agency, micro SaaS factory, content network, data products, AI consulting — with financial survival system ($400/mo minimum) and emergency mode
- **Experiment Lab**: Continuous testing of SaaS ideas, marketing strategies, pricing models, trading strategies — propose → run → complete/fail → scale — failures become experience memory lessons
- **Self-Writing Code**: Engineering agents propose code improvements (detect inefficiency → generate → test in sandbox → benchmark → deploy if verified) — major rewrites require Yohan approval
- **Enhanced Approval Chain**: Added architecture_change, system_expansion, major_rewrite, large_financial_decision to CRITICAL actions — approval requests now include reason, benefit, risk_analysis fields
- **Civilization API**: New `/api/civilization/*` routes for agents, experience memory, experiments, code proposals, revenue, and civilization status overview
- **Agent Registry Expanded**: `register_division()`, `list_core_agents()`, `list_division()`, `list_divisions()`, `agent_count()` methods added
- **16 new SQLite databases**: experience.db, experiments.db, self_code.db, revenue.db
- **Test coverage**: 283 tests (up from 220)
- **Version bump**: 0.9.0 → 1.0.0

## v0.9.0 changelog (from v0.8.0)
- **Prediction Ledger**: New system tracking MiRo/Swarm/Directive predictions with deadlines, auto-resolution against actuals, calibration scoring per source + confidence bucket
- **Action Chain Engine**: Reactive pipelines connecting proactive behaviors (scan_markets → auto_trade, health → notify, miro → scan, goals → assess)
- **MiRo Council Debates**: Real multi-agent council via AgentCollaboration.council() instead of single-LLM virtual panel, prediction ledger integration with calibration feedback in prompts
- **Money Engine Rebuilt**: Replaced 6 hardcoded opportunity templates with LLM-powered multi-agent fanout council (swarm, miro, researcher independently evaluate)
- **Position Monitor**: Background loop checking open trades against stop-losses and take-profits via Alpaca API every 5 minutes
- **Autonomous Loop Enhanced**: LLM-generated experiment hypotheses instead of fixed templates, new trading + strategy experiment areas
- **Directive Engine Enhanced**: Directive chaining (auto-follow-up, max depth 3), historical success/failure patterns injected into LLM prompt
- **Error Handling Hardened**: Replaced 11 silent `except: pass` blocks with proper logging, replaced 11 `return {"error": ...}` with HTTPException
- **Security Fix**: Timing-safe API key comparison via `hmac.compare_digest()`
- **Version bump**: 0.8.0 → 0.9.0

## v0.8.0 changelog (from v0.7.0)
- **Learning → ASTRA wired**: Bayesian routing weights now injected into ASTRA's routing prompt
- **Brain fallback**: LLM unavailability auto-degrades to offline brain
- **LLM retry**: Exponential backoff on transient API errors (both Anthropic + OpenAI)
- **State persistence**: ProactiveAction state, experiments, plugin logs survive restarts
- **Notification engine**: Telegram + Discord push alerts for approvals and health issues
- **Reflection actions**: Reflections now auto-execute (routing boosts, skills, goals, knowledge gaps)
- **Hook engine**: +2 hooks (auto_learn_from_error, routing_feedback)
- **OpenClaw feedback**: Records cycle outcomes in learning.db
- **Version centralized**: Single `VERSION` constant in config.py
- **Test coverage**: 149 tests (up from 75)
