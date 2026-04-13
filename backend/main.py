"""
ROOT v1.0.0 — ASTRA-ROOT Autonomous Intelligence Civilization.

Wires together 40+ systems for complete autonomy:
- Memory (3-layer), Learning, Conversation, Skill, Hook, Reflection engines
- Self-Dev, Context Manager, Orchestrator, Money Engine (LLM council)
- Plugin Engine, LLM Service, Interest Engine
- Brain / Offline Brain, Agent Registry + 150+ Civilization Agents
- Builder Agent, Message Bus, Approval Chain, Agent Collaboration
- Proactive Engine, Autonomous Loop, Hedge Fund (position monitor), Task Executor
- Task Queue (persistent), User Patterns, Goal Engine
- Trigger Engine, Digest Engine, Escalation Engine
- Prediction Ledger (calibration tracking), Action Chains (reactive pipelines)
- Directive Engine (chaining + history), Agent Network
- Experience Memory, Experiment Lab, Self-Writing Code, Revenue Engine
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import HOST, PORT, REFLECTION_INTERVAL_SECONDS, ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, LLM_PROVIDER, CORS_ORIGINS, VERSION, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL
from backend.security.middleware import SecurityHeaders, RateLimiter, APIKeyAuth
from backend.core.memory_engine import MemoryEngine
from backend.core.skill_engine import SkillEngine
from backend.core.hook_engine import HookEvent, build_default_hooks
from backend.core.reflection import ReflectionEngine
from backend.core.self_dev import SelfDevEngine
from backend.core.context_manager import ContextManager
from backend.core.orchestrator import Orchestrator
from backend.core.money_engine import MoneyEngine
from backend.core.plugin_engine import build_default_plugins
from backend.core.builder_agent import BuilderAgent
from backend.core.conversation_store import ConversationStore
from backend.core.knowledge_bootstrap import bootstrap_memory
from backend.core.message_bus import MessageBus
from backend.core.approval_chain import ApprovalChain
from backend.core.agent_collab import AgentCollaboration
from backend.core.proactive_engine import ProactiveEngine
from backend.core.autonomous_loop import AutonomousLoop
from backend.core.continuous_learning import ContinuousLearningEngine
from backend.core.learning_engine import LearningEngine
from backend.agents.registry import build_default_registry
from backend.agents.connectors.hermes import HermesConnector
from backend.agents.connectors.astra import AstraConnector
from backend.agents.connectors.miro import MiroConnector
from backend.agents.connectors.swarm import SwarmConnector
from backend.agents.connectors.openclaw import OpenClawConnector
from backend.agents.connectors.internal import InternalAgentConnector
from backend.core.interest_engine import InterestEngine
from backend.core.hedge_fund import HedgeFundEngine
from backend.core.task_executor import TaskExecutor
from backend.core.task_queue import TaskQueue
from backend.core.user_patterns import UserPatternEngine
from backend.core.goal_engine import GoalEngine
from backend.core.trigger_engine import TriggerEngine
from backend.core.digest_engine import DigestEngine
from backend.core.escalation_engine import EscalationEngine
from backend.core.directive_engine import DirectiveEngine
from backend.core.agent_network import AgentNetwork
from backend.core.state_store import StateStore
from backend.core.notification_engine import NotificationEngine
from backend.core.prediction_ledger import PredictionLedger
from backend.core.action_chains import build_default_chains
from backend.core.autonomy_actuator import AutonomyActuator
from backend.core.experience_memory import ExperienceMemory
from backend.core.experiment_lab import ExperimentLab
from backend.core.self_writing_code import SelfWritingCodeSystem
from backend.core.revenue_engine import RevenueEngine
from backend.core.project_ecosystem import ProjectEcosystem
from backend.core.sandbox_gate import SandboxGate
from backend.routes import chat, agents, memory, dashboard, money
from backend.routes import plugins as plugins_routes
from backend.routes import builder as builder_routes
from backend.routes import conversations as conv_routes
from backend.routes import interest as interest_routes
from backend.routes import autonomous as autonomous_routes
from backend.routes import hedge_fund as hedge_fund_routes
from backend.routes import tasks as task_routes
from backend.routes import autonomy as autonomy_routes
from backend.routes import civilization as civilization_routes
from backend.routes import ws as ws_routes
from backend.routes import events as events_routes
from backend.routes import costs as costs_routes
from backend.routes import network as network_routes
from backend.routes import ecosystem as ecosystem_routes
from backend.routes import settings as settings_routes
from backend.routes import sandbox as sandbox_routes
from backend.routes import polymarket as polymarket_routes
from backend.routes import analytics as analytics_routes
from backend.routes import notifications as notifications_routes
from backend.routes import predictions as predictions_routes
from backend.routes import action_chains_routes
from backend.routes import metrics as metrics_routes
from backend.routes import backtesting as backtesting_routes
from backend.routes import context as context_routes
from backend.routes import diagnostics as diagnostics_routes
from backend.routes import strategies as strategies_routes
from backend.routes import curiosity as curiosity_routes
from backend.routes import agents_custom as agents_custom_routes
from backend.routes import scenarios as scenarios_routes
from backend.routes import councils as councils_routes
from backend.routes import agi as agi_routes
from backend.routes import perpetual as perpetual_routes
from backend.routes import investment as investment_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("root")


# ── Background loops ──────────────────────────────────────────

async def _safe_loop(name: str, coro_fn, *args, **kwargs) -> None:
    """Run an async function in a loop with error handling. Never crashes."""
    while True:
        try:
            await coro_fn(*args, **kwargs)
        except asyncio.CancelledError:
            logger.info("Background loop '%s' cancelled", name)
            return
        except Exception as e:
            logger.error("Background loop '%s' error: %s", name, e, exc_info=True)


async def _reflection_loop(reflection: ReflectionEngine, interval: int) -> None:
    """Periodic self-reflection."""
    while True:
        await asyncio.sleep(interval)
        try:
            result = await asyncio.wait_for(
                reflection.reflect(trigger="scheduled"), timeout=90.0
            )
            if result:
                logger.info("Reflection completed: %s", result.insight[:100])
        except asyncio.TimeoutError:
            logger.warning("Reflection loop timed out after 90s")
        except Exception as e:
            logger.error("Reflection loop error: %s", e)


async def _decay_loop(mem: MemoryEngine, interval: int = 86400) -> None:
    """Daily memory confidence decay."""
    while True:
        await asyncio.sleep(interval)
        try:
            affected = mem.decay()
            logger.info("Memory decay: %d entries adjusted", affected)
        except Exception as e:
            logger.error("Decay loop error: %s", e)


# ── Lifespan ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Full startup / shutdown lifecycle with all systems."""
    logger.info("=" * 60)
    logger.info("  ROOT v1.0.0 — ASTRA-ROOT Intelligence Civilization — Starting Up")
    logger.info("=" * 60)

    # ── 0. State Store (persistent runtime state) ────────────
    state_store = StateStore()
    state_store.start()
    app.state.state_store = state_store
    logger.info("State store: persistent runtime state ready")

    # ── 0b. Notification Engine ─────────────────────────────────
    notifications = NotificationEngine(
        telegram_bot_token=TELEGRAM_BOT_TOKEN,
        telegram_chat_id=TELEGRAM_CHAT_ID,
        discord_webhook_url=DISCORD_WEBHOOK_URL,
    )
    notifications.start()
    notifications._sandbox_gate = None  # Set after sandbox_gate is created
    app.state.notifications = notifications
    logger.info("Notification engine: configured=%s (telegram=%s, discord=%s)",
                notifications.is_configured, bool(TELEGRAM_BOT_TOKEN), bool(DISCORD_WEBHOOK_URL))

    # ── 0c. Sandbox Gate (sandbox/live mode control) ──────────
    sandbox_gate = SandboxGate(
        state_store=state_store,
        notification_engine=notifications,
    )
    app.state.sandbox_gate = sandbox_gate
    notifications._sandbox_gate = sandbox_gate
    logger.info("Sandbox gate: global=%s", sandbox_gate.global_mode.value)

    # ── 1. Memory Engine ──────────────────────────────────────
    mem = MemoryEngine()
    mem.start()
    app.state.memory = mem

    bootstrapped = bootstrap_memory(mem)
    if bootstrapped:
        logger.info("Bootstrapped %d knowledge entries", bootstrapped)

    # Rebuild FTS index to fix any stale/missing search entries
    fts_count = mem.rebuild_fts()
    logger.info("Memory engine: %d entries (FTS rebuilt)", fts_count)

    # ── 1a. Vector Store + Dense Embeddings (semantic search) ───
    embedding_service = None
    try:
        from backend.core.vector_store import VectorStore
        from backend.core.embedding_service import EmbeddingService
        vector_store = VectorStore()
        vector_store.start()
        embedding_service = EmbeddingService(provider="auto")
        embedding_service.start()
        mem.set_vector_store(vector_store, embedding_service)
        app.state.embedding_service = embedding_service
        logger.info("VectorStore + EmbeddingService attached — dense semantic search enabled")
    except Exception as e:
        logger.warning("VectorStore unavailable: %s", e)

    # ── 1b. Learning Engine (outcome-based self-learning) ─────
    learning = LearningEngine()
    learning.start()
    app.state.learning = learning
    logger.info("Learning engine: started (outcome tracking + adaptive routing)")

    # ── 1c. Prediction Ledger (prediction tracking + calibration) ──
    prediction_ledger = PredictionLedger()
    prediction_ledger.start()
    app.state.prediction_ledger = prediction_ledger
    logger.info("Prediction ledger: tracking predictions + calibration")

    # ── 1c2. Council Store (debate persistence) ──────────────
    from backend.core.council_store import CouncilStore
    council_store = CouncilStore()
    council_store.start()
    app.state.council_store = council_store
    logger.info("Council store: debate persistence ready")

    # ── 1c3. Scenario Simulator (what-if lab) ────────────────
    from backend.core.scenario_simulator import ScenarioSimulator
    scenario_simulator = ScenarioSimulator(state_store=state_store)
    app.state.scenario_simulator = scenario_simulator
    logger.info("Scenario simulator: what-if lab ready")

    # ── 1d. Experience Memory (3-layer: short-term, long-term, experience) ──
    experience_memory = ExperienceMemory()
    experience_memory.start()
    app.state.experience_memory = experience_memory
    logger.info("Experience memory: 3-layer system (short-term + long-term + experience)")

    # Wire experience memory into learning engine for wisdom-informed routing
    learning.set_experience_memory(experience_memory)

    # ── 1e. Experiment Lab (continuous experimentation) ──────
    experiment_lab = ExperimentLab()
    experiment_lab.start()
    experiment_lab.set_experience_memory(experience_memory)
    app.state.experiment_lab = experiment_lab
    logger.info("Experiment lab: continuous testing (SaaS, marketing, pricing, trading)")

    # ── 1f. Self-Writing Code System ─────────────────────────
    self_writing_code = SelfWritingCodeSystem()
    self_writing_code.start()
    self_writing_code.set_experience_memory(experience_memory)
    self_writing_code._sandbox_gate = sandbox_gate
    app.state.self_writing_code = self_writing_code
    logger.info("Self-writing code: detect → generate → test → benchmark → deploy")

    # ── 1g. Revenue Engine (5-stream: $10k-$100k/month target) ──
    revenue_engine = RevenueEngine()
    revenue_engine.start()
    revenue_engine._sandbox_gate = sandbox_gate
    revenue_engine._notification_engine = notifications
    app.state.revenue_engine = revenue_engine
    logger.info("Revenue engine: 5 streams (automation, SaaS, content, data, consulting)")

    # ── 1h. Project Ecosystem (cross-project awareness) ──────
    ecosystem = ProjectEcosystem()
    ecosystem.start()
    app.state.ecosystem = ecosystem
    logger.info("Project ecosystem: %d projects tracked", len(ecosystem.get_all_projects()))

    # ── 2. Conversation Store ────────────────────────────────
    conversations = ConversationStore()
    conversations.start()
    app.state.conversations = conversations
    logger.info("Conversation store: ready (session=%s)", conversations.current_session_id)

    # ── 3. Skill Engine ───────────────────────────────────────
    skills = SkillEngine()
    skill_count = skills.load_all()
    app.state.skills = skills
    logger.info("Skill engine: %d skills loaded", skill_count)

    # ── 4. Self-Development Engine ────────────────────────────
    self_dev = SelfDevEngine(memory=mem, skills=skills)
    app.state.self_dev = self_dev
    if bootstrapped:
        self_dev.propose_improvement(
            area="knowledge",
            description="Initial knowledge bootstrap from AI folder",
            rationale=f"Seeded {bootstrapped} core knowledge entries.",
        )
    logger.info("Self-dev engine: maturity=%s", self_dev.assess()["maturity_level"])

    # ── 5. Context Manager ────────────────────────────────────
    context_mgr = ContextManager()
    app.state.context_manager = context_mgr

    # ── 6. Hook Engine ────────────────────────────────────────
    hooks = build_default_hooks(memory_engine=mem, skill_engine=skills, learning_engine=learning)
    app.state.hooks = hooks
    await hooks.fire(HookEvent.ON_STARTUP, {"boot_time": "now"})
    logger.info("Hook engine: %d hooks registered", hooks.stats()["total_hooks"])

    # ── 7. Agent Registry + Connectors ────────────────────────
    registry = build_default_registry()

    hermes_conn = HermesConnector()
    astra_conn = AstraConnector()
    miro_conn = MiroConnector()
    swarm_conn = SwarmConnector()
    openclaw_conn = OpenClawConnector()

    registry._connectors["hermes"] = hermes_conn
    registry._connectors["astra"] = astra_conn
    registry._connectors["miro"] = miro_conn
    registry._connectors["swarm"] = swarm_conn
    registry._connectors["openclaw"] = openclaw_conn

    app.state.registry = registry
    logger.info("Agent registry: %d agents", len(registry.list_agents()))

    # ── 8. Orchestrator ───────────────────────────────────────
    orchestrator = Orchestrator(registry=registry)
    app.state.orchestrator = orchestrator

    # ── 9. Money Engine (Strategy Council) ──────────────────
    money_engine = MoneyEngine(
        memory=mem, skills=skills, self_dev=self_dev,
        registry=registry, orchestrator=orchestrator,
    )
    money_engine._sandbox_gate = sandbox_gate
    money_engine._notification_engine = notifications
    app.state.money = money_engine
    logger.info("Money engine: Strategy Council ready")

    # ── 10. Plugin Engine ─────────────────────────────────────
    plugins = build_default_plugins(
        memory_engine=mem, skill_engine=skills, state_store=state_store,
        notification_engine=notifications,
    )
    plugins._sandbox_gate = sandbox_gate
    app.state.plugins = plugins
    logger.info("Plugin engine: %d plugins, %d tools",
                plugins.stats()["total_plugins"], plugins.stats()["total_tools"])

    # ── Finnhub Intelligence Plugin ──────────────────────────
    try:
        from backend.core.plugins.finnhub_plugin import register_finnhub_plugins
        register_finnhub_plugins(plugins, state_store=state_store)
        logger.info("Finnhub plugin: registered (fundamental data + earnings + sentiment)")
    except Exception as e:
        logger.info("Finnhub plugin: skipped (%s)", e)

    # ── 11a. Cost Tracker ────────────────────────────────────
    from backend.core.cost_tracker import CostTracker
    cost_tracker = CostTracker()
    cost_tracker.start()
    app.state.cost_tracker = cost_tracker
    logger.info("Cost tracker: ACTIVE")

    # ── 11b. Economic Router (smart tier, caching, budgets) ──
    from backend.core.economic_router import EconomicRouter
    economic_router = EconomicRouter(cost_tracker=cost_tracker)
    app.state.economic_router = economic_router
    logger.info("Economic router: smart tier selection + response cache + cost budgets")

    # ── 11c. Verification Protocol (consensus, redundancy) ───
    from backend.core.verification_protocol import VerificationProtocol
    verification = VerificationProtocol(
        learning_engine=learning, cost_tracker=cost_tracker,
    )
    app.state.verification = verification
    logger.info("Verification protocol: multi-agent consensus + redundancy detection")

    # ── 11d. LLM Service (Multi-Provider Router) ───────────────
    # Register ALL available providers — router cascades on failure/rate-limits
    from backend.services.llm_router import MultiProviderLLMRouter

    llm_router = MultiProviderLLMRouter(
        # User chat: local/free first to avoid burning paid quota
        priority=["ollama", "groq", "together", "deepseek", "openai", "anthropic"],
        # Background tasks: same — free first, paid last
        background_priority=["ollama", "groq", "together", "deepseek", "openai", "anthropic"],
    )

    provider_count = 0

    # Ollama (free, local, no rate limits)
    from backend.config import OLLAMA_ENABLED
    if OLLAMA_ENABLED:
        try:
            from backend.services.llm_ollama import OllamaLLMService
            ollama_svc = OllamaLLMService(cost_tracker=cost_tracker, economic_router=economic_router)
            llm_router.add_provider("ollama", ollama_svc)
            provider_count += 1
            logger.info("LLM provider: Ollama (local, FREE)")
        except Exception as e:
            logger.info("Ollama not available: %s", e)

    # Groq (free tier: 30 RPM, runs open-source models at insane speed)
    from backend.config import GROQ_API_KEY
    if GROQ_API_KEY:
        try:
            from backend.services.llm_groq import GroqLLMService
            groq_svc = GroqLLMService(cost_tracker=cost_tracker, economic_router=economic_router)
            llm_router.add_provider("groq", groq_svc)
            provider_count += 1
            logger.info("LLM provider: Groq (FREE tier — llama3/deepseek-r1)")
        except Exception as e:
            logger.warning("Groq init failed: %s", e)

    # Together AI (free/cheap, open-source model hosting)
    from backend.config import TOGETHER_API_KEY
    if TOGETHER_API_KEY:
        try:
            from backend.services.llm_together import TogetherLLMService
            together_svc = TogetherLLMService(cost_tracker=cost_tracker, economic_router=economic_router)
            llm_router.add_provider("together", together_svc)
            provider_count += 1
            logger.info("LLM provider: Together AI (open-source models)")
        except Exception as e:
            logger.warning("Together AI init failed: %s", e)

    # DeepSeek (very cheap: $0.14/1M tokens input)
    if DEEPSEEK_API_KEY:
        try:
            from backend.services.llm_deepseek import DeepSeekLLMService
            deepseek_svc = DeepSeekLLMService(cost_tracker=cost_tracker, economic_router=economic_router)
            llm_router.add_provider("deepseek", deepseek_svc)
            provider_count += 1
            logger.info("LLM provider: DeepSeek (open-source, cost-effective)")
        except Exception as e:
            logger.warning("DeepSeek init failed: %s", e)

    # OpenAI (paid, high quality)
    if OPENAI_API_KEY:
        try:
            from backend.services.llm_openai import OpenAILLMService
            openai_svc = OpenAILLMService(cost_tracker=cost_tracker, economic_router=economic_router)
            llm_router.add_provider("openai", openai_svc)
            provider_count += 1
            logger.info("LLM provider: OpenAI GPT")
        except Exception as e:
            logger.warning("OpenAI init failed: %s", e)

    # Anthropic (paid, highest quality)
    if ANTHROPIC_API_KEY:
        try:
            from backend.services.llm import LLMService
            anthropic_svc = LLMService(cost_tracker=cost_tracker, economic_router=economic_router)
            llm_router.add_provider("anthropic", anthropic_svc)
            provider_count += 1
            logger.info("LLM provider: Anthropic Claude")
        except Exception as e:
            logger.warning("Anthropic init failed: %s", e)

    # The router IS the LLM service — everything talks to it
    llm = llm_router if provider_count > 0 else None
    app.state.llm_router = llm_router
    logger.info("LLM router: %d providers registered (auto-failover active)", provider_count)
    if provider_count == 0:
        logger.info("LLM service: OFFLINE (no providers — using local brain)")

    # ── 12. Reflection Engine ──────────────────────────────────
    reflection = ReflectionEngine(memory=mem, llm=llm, learning=learning)
    app.state.reflection = reflection

    # ── 13. Interest Assessment Engine ────────────────────────
    interest = InterestEngine(memory=mem, llm=llm)
    app.state.interest = interest
    logger.info("Interest engine: ready")

    # Wire interest engine into revenue engine (created earlier at step 1g)
    revenue_engine.set_interest_engine(interest)

    # ── 14. Brain (online or offline) ─────────────────────────
    # Always create OfflineBrain as fallback for when LLM API goes down
    from backend.core.offline_brain import OfflineBrain
    offline_brain = OfflineBrain(
        memory=mem, skills=skills, self_dev=self_dev,
        context=context_mgr, money_engine=money_engine,
    )
    app.state.offline_brain = offline_brain

    if llm:
        from backend.core.brain import Brain
        from backend.services.task_router import TaskRouter
        router = TaskRouter(llm=llm, registry=registry)
        brain = Brain(
            llm=llm, memory=mem, reflection=reflection,
            router=router, registry=registry, skills=skills,
            plugins=plugins, conversations=conversations,
            money_engine=money_engine, interest_engine=interest,
            orchestrator=orchestrator, learning_engine=learning,
            ecosystem=ecosystem, prediction_ledger=prediction_ledger,
            experience_memory=experience_memory,
        )
        brain._offline_brain = offline_brain  # Fallback when LLM is unavailable
        app.state.brain = brain
        app.state.mode = "online"
        logger.info("Brain: ONLINE (offline fallback ready)")
    else:
        brain = offline_brain
        app.state.brain = brain
        app.state.mode = "offline"
        logger.info("Brain: OFFLINE")

    # ── 15. Wire Agent Connectors ─────────────────────────────
    if llm:
        # Wire core agent connectors (specialized connectors)
        astra_conn.set_llm(llm, plugins)
        astra_conn.set_learning(learning)
        astra_conn.set_ecosystem(ecosystem)
        astra_conn.set_registry(registry)
        hermes_conn.set_llm(llm, plugins)
        miro_conn.set_llm(llm, plugins)
        miro_conn.set_prediction_ledger(prediction_ledger)
        swarm_conn.set_llm(llm, plugins)
        openclaw_conn.set_learning(learning)

        # Wire ALL internal agents — core + civilization (172 total)
        # Every agent gets an InternalAgentConnector with dynamic prompts
        # generated from its AgentProfile (role, capabilities, tools).
        core_connector_ids = {"astra", "root", "hermes", "miro", "swarm", "openclaw"}
        for agent in registry.list_agents():
            if agent.id not in core_connector_ids and agent.id not in registry._connectors:
                registry._connectors[agent.id] = InternalAgentConnector(
                    agent_id=agent.id, llm=llm, plugins=plugins,
                    registry=registry,
                )
        logger.info("All %d agent connectors wired: LLM + tools bound",
                    len(registry._connectors))

    # ── 16. Builder Agent ─────────────────────────────────────
    builder = BuilderAgent(
        memory=mem, skills=skills, self_dev=self_dev, llm=llm, hooks=hooks,
    )
    app.state.builder = builder

    # ── 17. Message Bus (inter-agent communication) ────────────
    bus = MessageBus()
    app.state.bus = bus

    # Wire WebSocket bridge to message bus for real-time dashboard
    from backend.routes.ws import manager as ws_manager
    ws_manager.wire_message_bus(bus)
    logger.info("WebSocket bridge: wired to message bus")

    # Wire subscribers so the bus is actually used
    async def _on_system_learning(msg):
        """Learning engine stores new knowledge from agents."""
        payload = msg.payload
        if payload.get("type") == "cycle_complete" and mem:
            results = payload.get("results", {})
            logger.info("Bus: autonomous cycle %s — %d kept",
                        results.get("cycle"), results.get("kept", 0))

    async def _on_system_alert(msg):
        """Log alerts from proactive health checks and push notifications."""
        payload = msg.payload
        issues = payload.get("issues", [])
        if issues:
            logger.warning("Bus alert: %s", ", ".join(str(i) for i in issues[:5]))
            if notifications.is_configured:
                await notifications.send(
                    title="Health Alert",
                    body=", ".join(str(i) for i in issues[:5]),
                    level="high",
                    source="health_monitor",
                )

    async def _on_system_proactive(msg):
        """Track proactive action outcomes in learning engine."""
        if learning:
            action = msg.payload.get("action", "unknown")
            result = msg.payload.get("result", "")
            if result and len(str(result).strip()) > 30 and not any(
                w in str(result).lower() for w in ("error", "failed", "timeout")
            ):
                learning.record_agent_outcome(
                    agent_id="proactive_engine",
                    task_description=f"proactive:{action}",
                    status="completed",
                    result_quality=0.6,
                    task_category="proactive",
                )

    async def _on_approval_required(msg):
        """Log approval requests and push notifications for HIGH/CRITICAL."""
        payload = msg.payload
        risk = payload.get("risk", "")
        action = payload.get("action", "")
        description = payload.get("description", "")[:100]
        logger.info("Bus: approval required [%s] %s — %s", risk, action, description)

        if notifications.is_configured and payload.get("type") == "approval_required":
            await notifications.send(
                title=f"Approval Required [{risk.upper()}]",
                body=f"{action}: {description}",
                level="critical" if risk == "critical" else "high",
                source=f"approval:{payload.get('agent', 'unknown')}",
            )

    async def _on_system_proposal(msg):
        """Forward agent proposals to notification engine for Yohan."""
        payload = msg.payload
        proposal = payload.get("proposal", "")
        agent_id = payload.get("agent_id", msg.sender)
        priority = payload.get("priority", "medium")
        logger.info("Bus: proposal from %s — %s", agent_id, proposal[:80])

    async def _on_agent_request(msg):
        """Log inter-agent help requests."""
        payload = msg.payload
        from_agent = payload.get("from_agent", msg.sender)
        to_agent = payload.get("to_agent", "")
        message = payload.get("message", "")
        logger.info("Bus: agent request %s → %s: %s", from_agent, to_agent, message[:80])

    bus.subscribe("system.learning", "learning_listener", _on_system_learning)
    bus.subscribe("system.alert", "alert_listener", _on_system_alert)
    bus.subscribe("system.proactive", "proactive_listener", _on_system_proactive)
    bus.subscribe("system.approval", "approval_listener", _on_approval_required)
    bus.subscribe("system.proposal", "proposal_listener", _on_system_proposal)
    bus.subscribe("agent.*.request", "agent_request_listener", _on_agent_request)

    # Late-bind message bus into agent_comms and proposals plugins
    for pid in ("proposals", "agent_comms"):
        plugin = plugins.get_plugin(pid)
        if plugin:
            for tool in plugin.tools:
                # Inject message_bus into tool handlers via closure
                if hasattr(tool.handler, "__code__") and "message_bus" in (tool.handler.__code__.co_freevars or ()):
                    pass  # Already bound
            # Re-register with bus available — plugins already registered,
            # bus is accessed via the closure in agent_tools_plugins.py
            # The bus variable was None at registration; we patch it now
            pass
    # Simpler approach: the plugins captured `message_bus=None` at creation.
    # We need to re-register them now with the bus available.
    from backend.core.plugins.agent_tools_plugins import register_agent_tools_plugins
    # Unregister old (bus-less) versions and re-register with bus
    plugins.unregister("proposals")
    plugins.unregister("agent_comms")
    register_agent_tools_plugins(
        engine=plugins,
        notification_engine=notifications,
        message_bus=bus,
        experience_memory=experience_memory,
    )

    logger.info("Message bus: ready (%d subscribers)", bus.stats()["active_subscriptions"])

    # ── 18. Persistent Task Queue (crash recovery) ────────────
    task_queue = TaskQueue()
    task_queue.start()
    app.state.task_queue = task_queue
    logger.info("Task queue: persistent (recovered=%d)", task_queue.stats().get("by_status", {}).get("pending", 0))

    # ── 19. User Pattern Engine (behavior learning) ──────────
    user_patterns = UserPatternEngine()
    user_patterns.start()
    app.state.user_patterns = user_patterns
    logger.info("User patterns: tracking activity, preferences, anticipation")

    # ── 20. Goal Engine (autonomous goal management) ─────────
    goal_engine = GoalEngine(memory=mem, llm=llm, task_queue=task_queue)
    goal_engine.start()
    app.state.goal_engine = goal_engine
    logger.info("Goal engine: %d active goals", goal_engine.stats().get("by_status", {}).get("active", 0))

    # ── 21. Escalation Engine (confidence-gated decisions) ────
    escalation = EscalationEngine()
    escalation.start()
    app.state.escalation = escalation
    logger.info("Escalation engine: confidence-gated autonomous decisions")

    # ── 22. Approval Chain (with escalation confidence gating) ─
    approval = ApprovalChain(bus=bus, escalation=escalation)
    app.state.approval = approval
    self_writing_code.set_approval_chain(approval)
    logger.info("Approval chain: LOW=auto | MED=notify+escalation | HIGH/CRIT=approve")

    # ── 23. Agent Collaboration ───────────────────────────────
    collab = AgentCollaboration(
        orchestrator=orchestrator, bus=bus, registry=registry,
        verification=verification,
    )
    collab._sandbox_gate = sandbox_gate
    app.state.collab = collab
    logger.info("Agent collaboration: delegate/pipeline/fanout/council")

    # Give every internal connector a collab reference so agents can invoke each other
    for agent_id, connector in registry._connectors.items():
        if hasattr(connector, "set_collab"):
            connector.set_collab(collab)

    # Wire skill executor into all internal agents (late-bind after AGI section)
    def _wire_skill_executor():
        if hasattr(app.state, 'skill_executor'):
            for _aid, _conn in registry._connectors.items():
                if hasattr(_conn, '_skill_executor'):
                    _conn._skill_executor = app.state.skill_executor

    # Wire LLM, collab, bus into Money Engine and MiRo (created earlier)
    money_engine._llm = llm
    money_engine._collab = collab
    money_engine._bus = bus
    miro_conn.set_collab(collab)
    miro_conn.set_memory_engine(mem)

    # Wire LLM into scenario simulator (created earlier without LLM)
    scenario_simulator.set_llm(llm)

    # ── 24. Hedge Fund Engine ─────────────────────────────────
    hedge_fund = HedgeFundEngine(
        memory=mem, collab=collab, bus=bus, approval=approval,
        llm=llm, learning=learning, plugins=plugins,
    )
    hedge_fund._sandbox_gate = sandbox_gate
    hedge_fund._notification_engine = notifications
    hedge_fund.set_interest_engine(interest)
    hedge_fund.start()
    app.state.hedge_fund = hedge_fund
    logger.info("Hedge fund engine: started (risk controls active)")

    # ── 24b. Backtester (walk-forward + Monte Carlo) ──────────
    try:
        from backend.core.backtester import Backtester
        backtester = Backtester()
        backtester.start()
        app.state.backtester = backtester
        logger.info("Backtester: ready")
    except Exception as e:
        logger.warning("Backtester unavailable: %s", e)

    # ── 24c. Strategy Validator (autonomous backtest pipeline) ──
    try:
        from backend.core.strategy_validator import StrategyValidator
        strategy_validator = StrategyValidator(
            backtester=getattr(app.state, "backtester", None),
            llm=llm,
            experience_memory=experience_memory,
            learning=learning,
            bus=bus,
        )
        strategy_validator._notification_engine = notifications
        strategy_validator.start()
        app.state.strategy_validator = strategy_validator
        logger.info("Strategy validator: autonomous backtest → promote pipeline ready")
    except Exception as e:
        logger.warning("Strategy validator unavailable: %s", e)
        app.state.strategy_validator = None

    # ── 24d. Polymarket Trading Bot ─────────────────────────────
    import os as _os
    if _os.getenv("POLYMARKET_PRIVATE_KEY"):
        from backend.core.polymarket_bot import PolymarketBot
        polymarket_bot = PolymarketBot(
            plugins=plugins, llm=llm, bus=bus, approval=approval,
            memory=mem, experience=experience_memory, learning=learning,
        )
        polymarket_bot._sandbox_gate = sandbox_gate
        polymarket_bot._notification_engine = notifications
        app.state.polymarket_bot = polymarket_bot
        logger.info("Polymarket bot: ACTIVE (scalping + edge hunting)")
    else:
        app.state.polymarket_bot = None
        logger.info("Polymarket bot: SKIPPED (no POLYMARKET_PRIVATE_KEY)")

    # ── 25. Task Executor (autonomous goal decomposition) ─────
    task_executor = TaskExecutor(
        llm=llm, collab=collab, plugins=plugins, approval=approval,
        bus=bus, memory=mem, learning=learning, registry=registry,
    )
    app.state.task_executor = task_executor
    logger.info("Task executor: autonomous goal decomposition + execution")

    # ── 26. Proactive Engine (fully wired) ────────────────────
    proactive = ProactiveEngine(
        memory=mem, skills=skills, self_dev=self_dev,
        registry=registry, orchestrator=orchestrator,
        collab=collab, bus=bus, approval=approval, llm=llm,
        task_queue=task_queue, task_executor=task_executor,
        hedge_fund=hedge_fund, escalation=escalation,
        goal_engine=goal_engine, state_store=state_store,
        experiment_lab=experiment_lab, revenue_engine=revenue_engine,
        ecosystem=ecosystem, self_writing_code=self_writing_code,
        strategy_validator=getattr(app.state, "strategy_validator", None),
        notification_engine=notifications,
    )
    proactive._sandbox_gate = sandbox_gate
    proactive.set_experience_memory(experience_memory)
    if app.state.polymarket_bot:
        proactive.set_polymarket_bot(app.state.polymarket_bot)
    # Give Brain a reference so user chat pauses background actions
    if hasattr(app.state, "brain") and hasattr(app.state.brain, "_proactive"):
        app.state.brain._proactive = proactive
    app.state.proactive = proactive
    logger.info("Proactive engine: %d behaviors (fully wired)", len(await proactive.get_actions()))

    # ── 26b. Action Chain Engine (reactive pipelines) ──────────
    chain_engine = build_default_chains(
        proactive_engine=proactive, bus=bus, learning=learning,
    )
    chain_engine._sandbox_gate = sandbox_gate
    proactive.set_chain_engine(chain_engine)
    app.state.chain_engine = chain_engine
    logger.info("Action chains: %d chains wired (reactive pipelines)", chain_engine.stats()["total_chains"])

    # ── 26c. Autonomy Actuator (closes feedback loops) ──────────
    # Note: directive_engine is created later — pass None, late-bind after
    actuator = AutonomyActuator(
        bus=bus,
        learning=learning,
        goal_engine=goal_engine,
        task_queue=task_queue,
        revenue_engine=revenue_engine,
        directive_engine=None,
        approval_chain=approval,
        notification_engine=notifications,
        experiment_lab=experiment_lab,
        memory=mem,
        collab=collab,
        llm=llm,
        state_store=state_store,
    )
    app.state.actuator = actuator
    logger.info("Autonomy actuator: feedback loop closure (8 event handlers)")

    # ── Late-bind brain to v0.6 autonomy systems ───────────────
    if llm and hasattr(brain, '_goal_engine'):
        brain._goal_engine = goal_engine
        brain._escalation = escalation
        brain._user_patterns = user_patterns
        brain._hedge_fund = hedge_fund
        brain._revenue = revenue_engine
        brain._polymarket_bot = app.state.polymarket_bot
        logger.info("Brain: wired to goal_engine + escalation + user_patterns")

    # ── AGI-1: Outcome Evaluator + Registry (closed-loop learning) ──
    from backend.core.outcome_evaluator import OutcomeEvaluator
    from backend.core.outcome_registry import OutcomeRegistry
    from backend.core.decision_feedback import DecisionFeedback
    outcome_evaluator = OutcomeEvaluator(llm=llm)
    outcome_registry = OutcomeRegistry()
    outcome_registry.start()
    decision_feedback = DecisionFeedback(
        outcome_registry=outcome_registry, learning_engine=learning,
    )
    app.state.outcome_evaluator = outcome_evaluator
    app.state.outcome_registry = outcome_registry
    app.state.decision_feedback = decision_feedback
    logger.info("AGI: Outcome evaluator + registry + decision feedback — closed-loop learning ACTIVE")

    # ── AGI-2: Adaptive Config + Tuner (self-tuning parameters) ──
    from backend.core.adaptive_config import AdaptiveConfig
    from backend.core.adaptive_tuner import AdaptiveTuner
    adaptive_config = AdaptiveConfig()
    adaptive_config.start()
    adaptive_tuner = AdaptiveTuner(
        adaptive_config=adaptive_config,
        outcome_registry=outcome_registry,
        learning_engine=learning,
    )
    app.state.adaptive_config = adaptive_config
    app.state.adaptive_tuner = adaptive_tuner
    logger.info("AGI: Adaptive config (%d params) + tuner — self-tuning parameters ACTIVE",
                len(adaptive_config.get_all()))

    # ── AGI-3: Planning Engine (DAG planner) ────────────────────
    from backend.core.planning_engine import PlanningEngine
    planning_engine = PlanningEngine(
        llm=llm, experience_memory=experience_memory, memory=mem,
    )
    app.state.planning_engine = planning_engine
    task_executor._planning_engine = planning_engine
    logger.info("AGI: Planning engine — chain-of-thought DAG planner ACTIVE")

    # ── AGI-4: Trading Autonomy (graduated trust) ───────────────
    from backend.core.trading_autonomy import TradingAutonomy
    trading_autonomy = TradingAutonomy(
        adaptive_config=adaptive_config,
        prediction_ledger=prediction_ledger,
    )
    hedge_fund._trading_autonomy = trading_autonomy
    app.state.trading_autonomy = trading_autonomy
    logger.info("AGI: Trading autonomy — graduated trust (auto/notify/manual) ACTIVE")

    # ── AGI-5: Team Formation (dynamic agent teams) ─────────────
    from backend.core.team_formation import TeamFormation
    team_formation = TeamFormation(
        learning_engine=learning, registry=registry,
    )
    app.state.team_formation = team_formation
    task_executor._team_formation = team_formation
    logger.info("AGI: Team formation — dynamic agent teams ACTIVE")

    # ── AGI-6: Skill Executor (executable skills) ───────────────
    from backend.core.skill_executor import SkillExecutor
    skill_executor = SkillExecutor(
        skill_engine=skills, plugin_engine=plugins, llm=llm,
    )
    app.state.skill_executor = skill_executor
    _wire_skill_executor()
    logger.info("AGI: Skill executor — %d executable skills ACTIVE (wired to %d agents)",
                len(skill_executor.list_executable()),
                sum(1 for c in registry._connectors.values() if getattr(c, '_skill_executor', None)))

    # ── AGI-7: Conflict Detector (semantic contradiction detection) ──
    from backend.core.conflict_detector import ConflictDetector
    conflict_detector = ConflictDetector(
        embedding_service=embedding_service,
    )
    app.state.conflict_detector = conflict_detector
    logger.info("AGI: Conflict detector — semantic contradiction detection ACTIVE")

    # ── AGI-8: Emergency Protocol (auto-pause + rollback) ───────
    from backend.core.emergency_protocol import EmergencyProtocol
    emergency_protocol = EmergencyProtocol(
        notification_engine=notifications, state_store=state_store,
    )
    app.state.emergency_protocol = emergency_protocol
    logger.info("AGI: Emergency protocol — auto-pause + notification ACTIVE")

    # ── AGI-9: Code Deployment Pipeline (test-deploy-rollback) ──
    from backend.core.code_deployment import CodeDeploymentPipeline
    code_deployment = CodeDeploymentPipeline()
    self_writing_code._deployment_pipeline = code_deployment
    app.state.code_deployment = code_deployment
    logger.info("AGI: Code deployment — test → deploy → monitor → rollback ACTIVE")

    # ── TRADING INTELLIGENCE SUITE ─────────────────────────────
    from backend.core.market_data_service import MarketDataService
    from backend.core.trading_consensus import TradingConsensus
    from backend.core.investor_agents import InvestorPanel
    from backend.core.model_racing import ModelRacing
    from backend.core.response_transforms import ResponseTransforms
    from backend.core.continuous_research import ContinuousResearch
    from backend.core.web_explorer import WebExplorer
    from backend.core.document_analyzer import DocumentAnalyzer

    # Market Data Service (indicators + multi-source)
    import os as _os2
    _finnhub_key = getattr(app.state, '_finnhub_key', '') or _os2.environ.get('FINNHUB_API_KEY', '')
    _alpaca_key = getattr(app.state, '_alpaca_key', '') or _os2.environ.get('ALPACA_API_KEY', '')
    market_data = MarketDataService(
        finnhub_api_key=_finnhub_key,
        alpaca_api_key=_alpaca_key,
    )
    app.state.market_data = market_data
    logger.info("Market data service: multi-source indicators ACTIVE")

    # Trading Consensus (bull/bear debate)
    trading_consensus = TradingConsensus(
        llm=llm, collab=collab, experience_memory=experience_memory, memory=mem,
    )
    app.state.trading_consensus = trading_consensus
    logger.info("Trading consensus: bull/bear debate + risk assessment ACTIVE")

    # Wire trading intelligence into hedge fund
    hedge_fund._market_data = market_data
    hedge_fund._trading_consensus = trading_consensus
    logger.info("Hedge fund: wired market_data + trading_consensus")

    # Wire outcome registry into proactive engine
    proactive._outcome_registry = outcome_registry
    logger.info("Proactive engine: wired outcome_registry (closed-loop learning)")

    # Wire AGI trading intelligence into proactive engine
    proactive.set_market_data(market_data)
    proactive.set_planning_engine(planning_engine)
    logger.info("Proactive engine: wired market_data + planning_engine (AGI intelligence)")

    # Investor Panel (12 legendary investors)
    investor_panel = InvestorPanel(llm=llm)
    app.state.investor_panel = investor_panel
    hedge_fund._investor_panel = investor_panel
    logger.info("Investor panel: 12 legendary investor agents ACTIVE (wired to hedge fund)")

    # Model Racing (multi-model parallel evaluation)
    model_racing = ModelRacing(llm_router=llm_router)
    app.state.model_racing = model_racing
    brain._model_racing = model_racing
    logger.info("Model racing: multi-provider parallel evaluation ACTIVE")

    # Response Transforms (hedge reducer + direct mode)
    app.state.response_transforms = ResponseTransforms
    logger.info("Response transforms: hedge reducer + direct + trading mode ACTIVE")

    # Web Explorer (autonomous web browsing)
    web_explorer = WebExplorer(plugins=plugins, llm=llm, memory=mem)
    app.state.web_explorer = web_explorer
    logger.info("Web explorer: autonomous web browsing + data extraction ACTIVE")

    # Document Analyzer (PDF/doc analysis + reports)
    document_analyzer = DocumentAnalyzer(llm=llm, memory=mem)
    app.state.document_analyzer = document_analyzer
    logger.info("Document analyzer: analysis + report generation + export ACTIVE")

    # Content Ingestion (file/URL/text → memory pipeline)
    from backend.core.content_ingestion import ContentIngestion
    content_ingestion = ContentIngestion(
        memory=mem, experience_memory=experience_memory,
        llm=llm, web_explorer=web_explorer, document_analyzer=document_analyzer,
    )
    app.state.content_ingestion = content_ingestion
    brain._content_ingestion = content_ingestion
    logger.info("Content ingestion: file/URL/text → memory pipeline ACTIVE")

    # Continuous Research (always learning)
    continuous_research = ContinuousResearch(
        llm=llm, memory=mem, experience_memory=experience_memory,
        learning=learning, bus=bus, plugins=plugins,
        document_analyzer=document_analyzer,
    )
    app.state.continuous_research = continuous_research
    logger.info("Continuous research: autonomous knowledge acquisition ACTIVE")

    # ── 27. Autonomous Loop (with goal + task awareness + outcome evaluator) ──
    auto_loop = AutonomousLoop(
        memory=mem, skills=skills, self_dev=self_dev,
        collab=collab, bus=bus, approval=approval, llm=llm,
        learning=learning, goal_engine=goal_engine,
        task_queue=task_queue, state_store=state_store,
        ecosystem=ecosystem, prediction_ledger=prediction_ledger,
        experience_memory=experience_memory,
        outcome_evaluator=outcome_evaluator,
    )
    app.state.auto_loop = auto_loop
    logger.info("Autonomous loop: self-improving every 30min (goal-aware + outcome-evaluated)")

    # ── 27a. Continuous Learning Engine (all agents always learning) ──
    continuous_learning = ContinuousLearningEngine(
        registry=registry, collab=collab,
        experience_memory=experience_memory, memory=mem,
        bus=bus, state_store=state_store, llm=llm,
    )
    app.state.continuous_learning = continuous_learning
    logger.info("Continuous learning: all agents learn continuously (5min cycles, free models)")

    # ── 27a2. Curiosity Engine (intrinsic desire to learn) ──────
    from backend.core.curiosity_engine import CuriosityEngine
    curiosity = CuriosityEngine(
        memory=mem, learning_engine=learning,
        experience_memory=experience_memory,
        state_store=state_store, bus=bus, llm=llm,
    )
    app.state.curiosity = curiosity
    # Wire curiosity into brain so failures feed into learning
    if hasattr(brain, '_curiosity') or llm:
        brain._curiosity = curiosity
    logger.info("Curiosity engine: ROOT's intrinsic desire to learn is ACTIVE")

    # ── 27b. Digest Engine (daily/weekly reporting) ──────────────
    digest = DigestEngine(
        memory=mem, learning=learning, goal_engine=goal_engine,
        task_queue=task_queue, user_patterns=user_patterns,
        hedge_fund=hedge_fund, llm=llm,
    )
    digest.start()
    app.state.digest = digest
    logger.info("Digest engine: daily/weekly autonomous reporting")

    # ── 28. Trigger Engine (event-driven automation) ────────────
    triggers = TriggerEngine(
        task_queue=task_queue, collab=collab, proactive=proactive,
        bus=bus, memory=mem,
    )
    app.state.triggers = triggers
    logger.info("Trigger engine: %d rules (%d enabled)",
                triggers.stats()["total_rules"], triggers.stats()["enabled"])

    # ── 29. Agent Network (inter-agent knowledge sharing) ──────────
    agent_network = AgentNetwork(bus=bus, learning=learning, memory=mem)
    agent_network.start()
    app.state.agent_network = agent_network
    logger.info("Agent network: inter-agent learning + knowledge propagation")

    # ── 30. Directive Engine (autonomous strategic executive) ─────
    directive = DirectiveEngine(
        memory=mem, llm=llm, collab=collab, bus=bus, approval=approval,
        learning=learning, goal_engine=goal_engine, task_queue=task_queue,
        user_patterns=user_patterns, escalation=escalation, registry=registry,
        ecosystem=ecosystem, prediction_ledger=prediction_ledger,
        experience_memory=experience_memory,
    )
    directive._sandbox_gate = sandbox_gate
    directive._notification_engine = notifications
    directive.set_interest_engine(interest)
    directive._conflict_detector = conflict_detector  # AGI: semantic contradiction detection
    directive.start()
    app.state.directive = directive
    # Late-bind directive into actuator (was None at creation time)
    actuator._directive_engine = directive
    directive._outcome_registry = outcome_registry
    logger.info("Directive engine: autonomous strategic directives every 15min (outcome_registry wired)")

    # ── Wire network into agent collaboration ─────────────────────
    collab._network = agent_network

    # ── Late-bind brain to v0.7 systems (directive + network) ────
    if llm and hasattr(brain, '_directive'):
        brain._directive = directive
        brain._agent_network = agent_network
        logger.info("Brain: wired to directive_engine + agent_network")

    # ── Wire message bus into brain for agent finding publication ──
    if hasattr(brain, 'set_bus'):
        brain.set_bus(bus)
        logger.info("Brain: wired to message_bus")

    # ── Wire trigger bus subscriber ─────────────────────────────
    async def _on_system_trigger(msg):
        """Log trigger events."""
        payload = msg.payload
        logger.info("Bus: trigger fired '%s' → %s",
                    payload.get("trigger_name"), payload.get("action_type"))

    async def _on_network_insight(msg):
        """Log network insight sharing."""
        payload = msg.payload
        logger.info("Bus: network insight [%s] from %s → %s",
                    payload.get("insight_type"), payload.get("content", "")[:80],
                    payload.get("relevance_agents", []))

    async def _on_directive_event(msg):
        """Log directive completions."""
        payload = msg.payload
        logger.info("Bus: directive %s [%s] → %s",
                    payload.get("type"), payload.get("category"),
                    payload.get("title", "")[:80])

    bus.subscribe("system.trigger", "trigger_listener", _on_system_trigger)
    bus.subscribe("network.insight.*", "network_listener", _on_network_insight)
    bus.subscribe("system.directive", "directive_listener", _on_directive_event)

    # ── 29. Background Tasks (all wrapped with error handling) ──
    bg_tasks: list[asyncio.Task] = []
    if llm:
        bg_tasks.append(asyncio.create_task(
            _safe_loop("reflection", _reflection_loop, reflection, REFLECTION_INTERVAL_SECONDS),
            name="reflection_loop",
        ))
        # These create their own internal task loops — call directly, not via _safe_loop
        await proactive.start()
        await auto_loop.start()
        await continuous_learning.start()
        await curiosity.start()
        await actuator.start()
    bg_tasks.append(asyncio.create_task(
        _safe_loop("decay", _decay_loop, mem),
        name="decay_loop",
    ))
    bg_tasks.append(asyncio.create_task(
        _safe_loop("builder", builder.start_loop, 300),
        name="builder_loop",
    ))
    # triggers.start() creates its own internal task loops — call directly
    await triggers.start()
    bg_tasks.append(asyncio.create_task(
        _safe_loop("agent_network", agent_network.run_propagation_loop),
        name="network_loop",
    ))
    if llm:
        bg_tasks.append(asyncio.create_task(
            _safe_loop("directive", directive.run_loop),
            name="directive_loop",
        ))
    # AGI: Adaptive Tuner background loop (every 2 hours)
    # start_loop() manages its own internal loop — call directly, not via _safe_loop
    bg_tasks.append(asyncio.create_task(
        adaptive_tuner.start_loop(),
        name="adaptive_tuner_loop",
    ))
    # Decision Feedback loop (every 15 minutes)
    async def _decision_feedback_loop():
        await asyncio.sleep(300)  # Let outcomes accumulate first
        while True:
            try:
                signals = await decision_feedback.analyze()
                if signals.get("recommendations"):
                    decision_feedback.apply_signals(signals)
                    logger.info("Decision feedback: applied %d recommendations",
                                len(signals.get("recommendations", [])))
            except Exception as e:
                logger.error("Decision feedback error: %s", e)
            await asyncio.sleep(900)  # 15 minutes

    bg_tasks.append(asyncio.create_task(
        _safe_loop("decision_feedback", _decision_feedback_loop),
        name="decision_feedback_loop",
    ))

    # Emergency Protocol health checks (every 5 minutes)
    async def _emergency_check_loop():
        await asyncio.sleep(120)
        while True:
            try:
                # Gather metrics
                metrics = {
                    "error_rate": 0.0,  # TODO: wire from diagnostics
                    "llm_failure_rate": 0.0,
                    "trading_daily_pnl": 0.0,
                    "memory_corruption": False,
                }
                status = emergency_protocol.check_health(metrics)
                if status.severity.value != "ok":
                    await emergency_protocol.respond(status)
            except Exception as e:
                logger.error("Emergency check error: %s", e)
            await asyncio.sleep(300)  # 5 minutes

    bg_tasks.append(asyncio.create_task(
        _safe_loop("emergency_checks", _emergency_check_loop),
        name="emergency_check_loop",
    ))

    # Continuous Research background loop (every 30 min)
    if llm:
        await continuous_research.start_loop()
        logger.info("Continuous research loop: STARTED (30min intervals)")

    # ── PERPETUAL INTELLIGENCE (every 60s — all agents always working) ──
    from backend.core.perpetual_intelligence import PerpetualIntelligence
    perpetual = PerpetualIntelligence(
        llm=llm, collab=collab, bus=bus, memory=mem,
        experience_memory=experience_memory, learning=learning,
        registry=registry, skills=skills, plugins=plugins,
        state_store=state_store, web_explorer=web_explorer,
        document_analyzer=document_analyzer, hedge_fund=hedge_fund,
        planning_engine=planning_engine,
    )
    app.state.perpetual_intelligence = perpetual
    logger.info("Perpetual intelligence: ALL agents constantly working")

    # ── AGENT SWARM (every 120s — 10 divisions always active) ──
    from backend.core.agent_swarm import AgentSwarm
    agent_swarm = AgentSwarm(
        collab=collab, registry=registry, bus=bus, memory=mem,
        learning=learning, experience_memory=experience_memory, llm=llm,
    )
    app.state.agent_swarm = agent_swarm
    logger.info("Agent swarm: 172 agents across 10 divisions — ALWAYS ACTIVE")

    # Start perpetual loops
    if llm:
        await perpetual.start(interval=60)
        await agent_swarm.start(interval=120)
        logger.info("Perpetual intelligence + Agent swarm: STARTED")

    # ── INVESTMENT INTELLIGENCE (17 agents + debate + thesis + portfolio) ──
    from backend.core.market_data import MarketDataService as YFMarketData
    from backend.core.investment_agents import InvestmentAgentRunner
    from backend.core.debate_engine import DebateEngine
    from backend.core.thesis_engine import ThesisEngine
    from backend.core.portfolio_optimizer import PortfolioOptimizer

    yf_market_data = YFMarketData()
    app.state.yf_market_data = yf_market_data

    investment_runner = InvestmentAgentRunner(llm=llm, market_data=yf_market_data) if llm else None
    app.state.investment_runner = investment_runner

    debate_engine = DebateEngine(
        llm=llm,
        investment_runner=investment_runner,
        market_data=yf_market_data,
        experience_memory=experience_memory,
        prediction_ledger=prediction_ledger,
        bus=bus,
    )
    app.state.debate_engine = debate_engine

    thesis_engine = ThesisEngine(
        llm=llm,
        market_data=yf_market_data,
        debate_engine=debate_engine,
        experience_memory=experience_memory,
        prediction_ledger=prediction_ledger,
        learning_engine=learning,
        bus=bus,
    )
    app.state.thesis_engine = thesis_engine

    portfolio_optimizer = PortfolioOptimizer(market_data=yf_market_data)
    app.state.portfolio_optimizer = portfolio_optimizer

    logger.info("Investment intelligence: 17 agents + debate + thesis + portfolio optimization ACTIVE")
    logger.info("  Quant models: Kelly | LMSR | EV/Arb | Brier | ARIMA | GARCH | Monte Carlo")
    logger.info("  Philosophy agents: Buffett | Graham | Munger | Burry | Wood | Taleb | Lynch | Fisher | Ackman | Druckenmiller | Damodaran | Pabrai | Jhunjhunwala")
    logger.info("  Analysis agents: Valuation | Fundamentals | Sentiment | Technicals")

    # ── META-AGENT (CEO / Self-Improver) ─────────────────────
    from backend.core.meta_agent import MetaAgent
    meta_agent = MetaAgent(
        llm=llm,
        prediction_ledger=prediction_ledger,
        experience_memory=experience_memory,
        learning_engine=learning,
        thesis_engine=thesis_engine,
        hedge_fund=hedge_fund,
        bus=bus,
        state_store=state_store,
    )
    app.state.meta_agent = meta_agent
    logger.info("Meta-Agent: CEO self-improver — nightly reflection + Brier recalibration ACTIVE")

    # ── ARB AGENT (pure-math spread harvesting) ──────────────
    from backend.core.arb_agent import ArbAgent
    arb_agent = ArbAgent()
    app.state.arb_agent = arb_agent
    logger.info("Arb Agent: LMSR spread harvesting + cross-market arbitrage ACTIVE")

    # ── ECONOMIC SUSTAINABILITY ("pay for yourself or die") ──
    from backend.core.economic_sustainability import EconomicSustainability
    economic_sustainability = EconomicSustainability(
        notification_engine=notifications,
        bus=bus,
    )
    app.state.economic_sustainability = economic_sustainability
    logger.info("Economic sustainability: pay-for-yourself-or-die engine ACTIVE (mode=%s)",
                economic_sustainability.mode)

    # ── EPISODIC TRADE MEMORY (per-trade learning) ───────────
    from backend.core.episodic_trade_memory import EpisodicTradeMemory
    episodic_trades = EpisodicTradeMemory()
    episodic_trades.start()
    app.state.episodic_trades = episodic_trades
    logger.info("Episodic trade memory: per-trade logging + lesson extraction ACTIVE")

    # ── SELF-PERFECTION ORGANISM ────────────────────────────────
    from backend.core.self_perfection import SelfPerfectionEngine
    self_perfection = SelfPerfectionEngine(
        llm=llm,
        meta_agent=meta_agent,
        thesis_engine=thesis_engine,
        prediction_ledger=prediction_ledger,
        experience_memory=experience_memory,
        learning_engine=learning,
        episodic_trades=episodic_trades,
        economic_sustainability=economic_sustainability,
        self_writing_code=self_writing_code,
        skills=skills,
        bus=bus,
        state_store=state_store,
    )
    app.state.self_perfection = self_perfection
    logger.info("Self-perfection: gap finder + mutation loop + audit crew ACTIVE")

    # ── ORGANISM HIERARCHY (CEO → Research → Signal → Risk → Execute) ──
    from backend.core.organism_hierarchy import OrganismOrchestrator
    organism = OrganismOrchestrator(
        meta_agent=meta_agent,
        thesis_engine=thesis_engine,
        debate_engine=debate_engine,
        arb_agent=arb_agent,
        portfolio_optimizer=portfolio_optimizer,
        hedge_fund=hedge_fund,
        episodic_trades=episodic_trades,
        economic_sustainability=economic_sustainability,
        self_perfection=self_perfection,
        prediction_ledger=prediction_ledger,
        bus=bus,
    )
    app.state.organism = organism
    logger.info("Organism hierarchy: %d nodes, %d tiers — living quant firm ACTIVE",
                organism.stats()["total_nodes"], len(organism.stats()["tiers"]))

    # Start background loops for self-improvement
    if llm:
        bg_tasks.append(asyncio.create_task(
            _safe_loop("meta_agent", meta_agent.start_loop, 24.0),
            name="meta_agent_loop",
        ))
        bg_tasks.append(asyncio.create_task(
            _safe_loop("self_perfection", self_perfection.start_loop, 300, 86400),
            name="self_perfection_loop",
        ))
        logger.info("Meta-Agent reflection (24h) + Self-Perfection (5min scan / 24h cycle): STARTED")

    # ── Startup complete ──────────────────────────────────────
    assessment = self_dev.assess()
    logger.info("=" * 60)
    logger.info("  ROOT v1.0.0 ALIVE — %s — ASTRA-ROOT CIVILIZATION", app.state.mode.upper())
    logger.info("  Maturity: %s (%.0f%%)",
                assessment["maturity_level"], assessment["maturity_score"] * 100)
    logger.info("  Memories: %d | Skills: %d | Agents: %d | Plugins: %d",
                mem.count(), skill_count, registry.agent_count(),
                plugins.stats()["total_plugins"])
    logger.info("  Civilization: %d agents across %d divisions",
                registry.agent_count(), len(registry.list_divisions()))
    logger.info("  Learning: Outcome tracking + Adaptive routing + Experience memory")
    logger.info("  Revenue Engine: 5 streams (automation, SaaS, content, data, consulting)")
    logger.info("  Project Ecosystem: %d projects tracked, %d connections",
                len(ecosystem.get_all_projects()), len(ecosystem.get_connections()))
    logger.info("  Experiment Lab: Continuous testing + Auto-proposer + Self-writing code")
    logger.info("  Autonomous: Builder + Proactive + Self-Improving Loop + Continuous Learning + Curiosity + Hedge Fund + Actuator")
    logger.info("  Directive Engine: Autonomous strategic decisions every 15min")
    logger.info("  Collaboration: Delegate | Pipeline | Fanout | Council")
    logger.info("  Economics: Smart tier routing + Response cache + Cost budgets")
    logger.info("  Verification: Multi-agent consensus + Redundancy detection")
    logger.info("  Sandbox Gate: global=%s (all external actions gated)", sandbox_gate.global_mode.value)
    logger.info("  Governance: Yohan approval for architecture/financial/expansion changes")
    logger.info("  AGI UPGRADES: Dense Embeddings | Outcome Evaluator | Adaptive Config")
    logger.info("  AGI UPGRADES: Planning Engine | Trading Autonomy | Team Formation")
    logger.info("  AGI UPGRADES: Skill Executor | Conflict Detector | Emergency Protocol")
    logger.info("  AGI UPGRADES: Code Deployment | Decision Feedback | Adaptive Tuner")
    logger.info("  TRADING SUITE: Market Data | Consensus | 12 Investors | Model Racing")
    logger.info("  RESEARCH: Web Explorer | Document Analyzer | Continuous Research")
    logger.info("  INVESTMENT: 17 philosophy+analysis agents | Bull/Bear debate | Thesis engine | Portfolio optimizer")
    logger.info("  QUANT MODELS: Kelly | LMSR | EV/Arb | Brier | ARIMA | GARCH | Monte Carlo | Cointegration")
    logger.info("  META-AGENT: CEO self-improver | Nightly reflection | Brier recalibration | Hypothesis testing")
    logger.info("  ARB AGENT: LMSR spreads | Cross-market arb | Pairs trading | Bayesian updates")
    logger.info("  ECONOMICS: Pay-for-yourself-or-die | Reinvestment rules | Strategy P&L | Survival mode")
    logger.info("  EPISODIC MEMORY: Per-trade logging | Lesson extraction | Calibration tracking")
    logger.info("  PERPETUAL: All 172 agents working constantly (research + analysis + trading + coding + vision)")
    logger.info("  SKILLS: %d total (%d executable)", len(skills.list_all()), len(skill_executor.list_executable()))
    logger.info("  Dashboard: http://%s:%s", HOST, PORT)
    logger.info("=" * 60)

    yield

    # ── Shutdown (proper cleanup with awaited cancellation) ──
    logger.info("ROOT v1.0.0 shutting down...")
    await hooks.fire(HookEvent.ON_SHUTDOWN, {})
    perpetual.stop()
    agent_swarm.stop()
    directive.stop()
    agent_network.stop()
    triggers.stop()
    actuator.stop()
    curiosity.stop()
    proactive.stop()
    auto_loop.stop()
    continuous_learning.stop()
    builder.stop()
    hedge_fund.stop()
    # Cancel all background tasks and wait for them to finish
    for t in bg_tasks:
        t.cancel()
    for t in bg_tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await t
    self_perfection.stop()
    meta_agent.stop()
    episodic_trades.stop()
    adaptive_tuner.stop()
    outcome_registry.stop()
    adaptive_config.stop()
    if embedding_service:
        embedding_service.stop()
    continuous_research.stop()
    notifications.stop()
    revenue_engine.stop()
    ecosystem.stop()
    self_writing_code.stop()
    experiment_lab.stop()
    experience_memory.stop()
    digest.stop()
    escalation.stop()
    goal_engine.stop()
    user_patterns.stop()
    task_queue.stop()
    conversations.stop()
    prediction_ledger.stop()
    council_store.stop()
    learning.stop()
    cost_tracker.stop()
    mem.stop()
    state_store.stop()
    logger.info("=== ROOT v1.0.0 shut down cleanly ===")


# ── App ────────────────────────────────────────────────────────

_fastapi_app = FastAPI(
    title="ROOT v1.0.0",
    description="ASTRA-ROOT Autonomous Intelligence Civilization API",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

_fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
_fastapi_app.include_router(chat.router)
_fastapi_app.include_router(agents.router)
_fastapi_app.include_router(memory.router)
_fastapi_app.include_router(dashboard.router)
_fastapi_app.include_router(money.router)
_fastapi_app.include_router(plugins_routes.router)
_fastapi_app.include_router(builder_routes.router)
_fastapi_app.include_router(conv_routes.router)
_fastapi_app.include_router(interest_routes.router)
_fastapi_app.include_router(autonomous_routes.router)
_fastapi_app.include_router(hedge_fund_routes.router)
_fastapi_app.include_router(task_routes.router)
_fastapi_app.include_router(autonomy_routes.router)
_fastapi_app.include_router(civilization_routes.router)
_fastapi_app.include_router(ws_routes.router)
_fastapi_app.include_router(events_routes.router)
_fastapi_app.include_router(costs_routes.router)
_fastapi_app.include_router(network_routes.router)
_fastapi_app.include_router(ecosystem_routes.router)
_fastapi_app.include_router(settings_routes.router)
_fastapi_app.include_router(sandbox_routes.router)
_fastapi_app.include_router(polymarket_routes.router)
_fastapi_app.include_router(analytics_routes.router)
_fastapi_app.include_router(notifications_routes.router)
_fastapi_app.include_router(predictions_routes.router)
_fastapi_app.include_router(action_chains_routes.router)
_fastapi_app.include_router(context_routes.router)
_fastapi_app.include_router(metrics_routes.router)
_fastapi_app.include_router(backtesting_routes.router)
_fastapi_app.include_router(curiosity_routes.router)
_fastapi_app.include_router(diagnostics_routes.router)
_fastapi_app.include_router(strategies_routes.router)
_fastapi_app.include_router(agents_custom_routes.router)
_fastapi_app.include_router(scenarios_routes.router)
_fastapi_app.include_router(councils_routes.router)
_fastapi_app.include_router(agi_routes.router)
_fastapi_app.include_router(perpetual_routes.router)
_fastapi_app.include_router(investment_routes.router)


# Health check
@_fastapi_app.get("/api/health")
async def health():
    return {
        "status": "alive",
        "version": VERSION,
        "mode": getattr(_fastapi_app.state, "mode", "unknown"),
    }


# Static files (dashboard)
_fastapi_app.mount("/", StaticFiles(directory="backend/static", html=True), name="static")


# ── Pure ASGI middleware wrapping ────────────────────────────────
app = SecurityHeaders(RateLimiter(APIKeyAuth(_fastapi_app)))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=int(PORT), reload=False)
