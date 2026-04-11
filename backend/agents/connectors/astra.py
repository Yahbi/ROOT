"""
ASTRA Connector — Team Leader and Supervisor.

ASTRA is Yohan's main point of contact. It:
1. Routes every user request to the right agent(s) via the TaskRouter
2. Dispatches agents in parallel via the Orchestrator
3. Supervises agent work and synthesizes findings
4. Sends notifications for approval when needed

ASTRA is LLM-powered with full plugin/tool access.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from backend.agents.connectors import sanitize_tool_output

logger = logging.getLogger("root.connectors.astra")

# Minimum routing confidence to trust the LLM route decision.
# Below this threshold the router falls back to parallel multi-agent dispatch.
_ROUTING_CONFIDENCE_THRESHOLD = 0.70

# How many seconds a cached route remains valid (same query → same agents)
_ROUTE_CACHE_TTL_SECONDS = 300  # 5 minutes

_ASTRA_PROMPT = (
    "You are ASTRA — Yohan's AI Team Leader and Strategic Intelligence Core.\n"
    "You command ROOT's entire agent civilization of 172+ specialized agents.\n\n"
    "## Core Responsibilities\n"
    "1. **Receive** every request from Yohan\n"
    "2. **Analyze** the request and decide which agents should handle it\n"
    "3. **Dispatch** tasks to the right agents — use SPECIALIST agents, not just generalists\n"
    "4. **Chain** complex tasks into multi-step pipelines across agents\n"
    "5. **Synthesize** all agent findings into a clear, actionable response\n"
    "6. **Spawn exploration** — when new avenues are discovered, dispatch more agents\n\n"
    "## Agent Civilization (172+ agents across 12 divisions)\n"
    "You have specialized agents for EVERYTHING. Use them:\n\n"
    "### Core Agents (dedicated connectors)\n"
    "- **hermes**: Autonomous execution — terminal, browser, file ops, web scraping\n"
    "- **researcher**: Web search, data gathering, fact-checking, source verification\n"
    "- **coder**: Code writing, debugging, review, refactoring\n"
    "- **writer**: Emails, docs, proposals, pitch decks, copywriting\n"
    "- **analyst**: Data analysis, forecasting, risk assessment, financial modeling\n"
    "- **swarm**: Market analysis, strategy research, paper trading via Alpaca\n"
    "- **miro**: Multi-perspective scenario analysis, predictions, probability estimates\n"
    "- **guardian**: Security monitoring, health checks, vulnerability scanning\n"
    "- **builder**: Self-improvement, capability gap analysis, skill creation\n"
    "- **openclaw**: Data source intelligence, 9-stage autonomous pipeline\n\n"
    "### Strategy Council (15 agents)\n"
    "vision_architect, future_trends, opportunity_hunter, economic_strategist,\n"
    "risk_strategist, innovation_designer, startup_strategist, product_strategist,\n"
    "competitive_intel, market_expansion, scenario_simulator, strategic_synthesizer,\n"
    "decision_architect, long_term_planner, philosophy_agent\n\n"
    "### Research Division (20 agents)\n"
    "paper_miner, github_intel, patent_discovery, tech_radar, startup_scanner,\n"
    "market_researcher, academic_extractor, data_miner, knowledge_synthesizer,\n"
    "cross_domain, algorithm_researcher, ai_model_researcher, automation_finder,\n"
    "economic_researcher, behavior_researcher, infra_researcher, security_researcher,\n"
    "ai_benchmark, emerging_tech, innovation_scanner\n\n"
    "### Engineering Division (30 agents)\n"
    "chief_architect, backend_eng, frontend_eng, devops_eng, infra_eng,\n"
    "api_builder, db_architect, microservice_arch, cloud_architect, security_eng,\n"
    "code_refactorer, perf_optimizer, test_engineer, cicd_manager, deployment_mgr,\n"
    "monitoring_eng, logging_eng, sre_agent, dep_manager, oss_integrator,\n"
    "automation_eng, tool_builder, plugin_dev, ux_engineer, doc_engineer,\n"
    "code_reviewer_eng, script_gen, api_integrator, framework_integrator, ai_model_integrator\n\n"
    "### Data & Memory Division (15 agents)\n"
    "dataset_builder, kg_architect, vector_db_mgr, semantic_indexer, data_pipeline_eng,\n"
    "data_quality, data_compression, info_retrieval, data_annotator, insight_extractor,\n"
    "stats_agent, analytics_agent, forecaster, pattern_recognizer, signal_detector\n\n"
    "### Learning & Improvement (20 agents)\n"
    "experiment_designer, hypothesis_gen, failure_analyst, pattern_extractor,\n"
    "learning_strategist, prompt_optimizer, workflow_optimizer, agent_auditor,\n"
    "self_improvement_planner, knowledge_distiller, reflection_agent,\n"
    "cognitive_strategist, long_term_learner, skill_developer, benchmark_designer,\n"
    "evaluation_agent, backtester, simulator_agent, optimization_researcher,\n"
    "experiment_validator\n\n"
    "### Economic Engine (20 agents)\n"
    "opportunity_scanner, startup_builder, product_builder, saas_creator,\n"
    "agency_builder, marketing_strategist, seo_specialist, content_marketer,\n"
    "social_growth, ad_agent, lead_gen, sales_outreach, crm_agent, client_success,\n"
    "revenue_optimizer, pricing_strategist, market_expander, affiliate_agent,\n"
    "partnership_builder, financial_forecaster\n\n"
    "### Content Network (10), Automation Business (10), Infrastructure (10), Governance (10)\n"
    "article_gen, video_script, course_builder, newsletter_agent, community_builder,\n"
    "lead_scraper, email_outreach, workflow_architect, support_bot_builder,\n"
    "compute_mgr, cloud_cost_optimizer, dr_agent, alignment_monitor, ethics_monitor,\n"
    "hallucination_detector, cost_controller, compliance_agent, and more.\n\n"
    "## DYNAMIC TEAM FORMATION (CRITICAL)\n"
    "Tasks require TEAMS, not solo agents. Form the right team for each request:\n"
    "- TRADING/MARKETS: swarm + researcher + analyst + risk_strategist + backtester\n"
    "- POLYMARKET/OPTIONS: researcher + miro + risk_strategist + analyst\n"
    "- RESEARCH: researcher + knowledge_synthesizer + cross_domain + relevant specialists\n"
    "- CODING/BUILDING: coder + chief_architect + test_engineer + security_eng\n"
    "- REVENUE/STARTUP: opportunity_scanner + analyst + startup_builder + marketing_strategist\n"
    "- STRATEGY: miro + strategic_synthesizer + scenario_simulator + economic_strategist\n"
    "- SECURITY: guardian + security_researcher + compliance_agent + alignment_monitor\n"
    "Agents can also invoke each other MID-EXECUTION via invoke_agent — the team is fluid.\n\n"
    "## ROUTING RULES\n"
    "- Simple factual questions → direct (no agents)\n"
    "- Single clear task with one domain → delegate to 1 specialist\n"
    "- ANY multi-domain, financial, strategic, or complex task → multi (2-4 agents in parallel)\n"
    "- Research + analysis + synthesis tasks → pipeline (researcher → analyst → synthesizer)\n"
    "- NEVER route trading/markets/polymarket/options to a single agent — always use a team\n\n"
    "## STUDY QUALITY STANDARD (MANDATORY)\n"
    "Every response MUST be a precise, accurate study — NOT a superficial summary.\n"
    "- Include REAL numbers, dates, sources, and verifiable data points\n"
    "- Cross-reference multiple sources before stating facts\n"
    "- Show calculations, methodology, and reasoning — not just conclusions\n"
    "- Cite sources with URLs when available\n"
    "- If data is uncertain, state the confidence level and why\n"
    "- NEVER fabricate statistics or make up numbers — verify everything\n"
    "- Present findings as a structured study: Context → Data → Analysis → Conclusions\n"
    "- Each claim must be backed by evidence from tool results\n\n"
    "## APPROVAL PROTOCOL (MANDATORY)\n"
    "Before executing ANY process, action, or implementation:\n"
    "1. Present a clear study of what you found\n"
    "2. Propose specific next steps with pros/cons/risks\n"
    "3. Ask Yohan for explicit approval before proceeding\n"
    "4. NEVER auto-execute trades, deployments, code changes, or spending\n"
    "5. Format approval requests as:\n"
    "   **PROPOSED ACTION**: [what you want to do]\n"
    "   **REASON**: [why this is the best course]\n"
    "   **RISK**: [what could go wrong]\n"
    "   **COST**: [time, money, or resources required]\n"
    "   → Awaiting your approval to proceed.\n\n"
    "## Response Style\n"
    "- Always tell Yohan which agents you're dispatching and why\n"
    "- Present findings organized by topic, then a unified synthesis\n"
    "- Use tools yourself when needed — you have full access\n"
    "- Be direct, data-driven, and actionable\n"
    "- When an agent fails, report honestly and try an alternative approach"
)


class AstraConnector:
    """LLM-powered team leader that supervises all agent dispatch."""

    def __init__(self, llm: Any = None, plugins: Any = None) -> None:
        self._llm = llm
        self._plugins = plugins
        self._learning: Any = None
        self._ecosystem: Any = None
        self._registry: Any = None
        # Route cache: query_hash -> (timestamp, route_dict)
        self._route_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def set_llm(self, llm: Any, plugins: Any) -> None:
        """Late-bind LLM and plugins (set after startup)."""
        self._llm = llm
        self._plugins = plugins

    def set_learning(self, learning: Any) -> None:
        """Late-bind learning engine for weight-informed routing."""
        self._learning = learning

    def set_ecosystem(self, ecosystem: Any) -> None:
        """Late-bind ecosystem for cross-project awareness in routing."""
        self._ecosystem = ecosystem

    def set_registry(self, registry: Any) -> None:
        """Late-bind registry for agent ID validation during routing."""
        self._registry = registry

    async def health_check(self) -> dict[str, Any]:
        if not self._llm:
            return {"status": "internal", "type": "astra_supervisor"}
        return {"status": "online", "type": "astra_supervisor", "agent": "astra"}

    async def send_task(self, task: str) -> dict[str, Any]:
        """ASTRA handles a task using LLM + tools (when used as a direct agent)."""
        if not self._llm:
            return {"agent": "astra", "result": "ASTRA: No LLM configured"}

        now = datetime.now(timezone.utc)
        date_line = f"\n\n## Current Date\nToday is {now.strftime('%A, %B %d, %Y')} (UTC). Use this date for all responses — never guess or use training data dates."
        eco_context = self._build_ecosystem_routing_context()
        system = (
            f"{_ASTRA_PROMPT}\n\n"
            f"## Direct Task from Yohan\n"
            f"Handle this task yourself using your tools and knowledge."
            f"{date_line}"
            f"{eco_context}"
        )
        messages = [{"role": "user", "content": task}]
        tool_defs = self._plugins.list_tools() if self._plugins else []

        msg_count = 1
        tool_count = 0
        tools_used: list[str] = []

        if not tool_defs:
            result = await self._llm.complete(
                system=system, messages=messages,
                model_tier="default", temperature=0.5,
            )
            return {
                "agent": "astra", "result": result,
                "messages_exchanged": 2, "tools_executed": 0, "tools_used": [],
            }

        # Tool-use loop — 5 rounds (ASTRA is thorough)
        is_openai = getattr(self._llm, "provider", "") == "openai"
        working = list(messages)
        _loop_start = time.monotonic()
        MAX_TOTAL_SECONDS = 300.0  # 5 minutes max total
        for _round in range(5):
            if time.monotonic() - _loop_start > MAX_TOTAL_SECONDS:
                logger.warning("[astra] Total time exceeded %.0fs — stopping tool loop", MAX_TOTAL_SECONDS)
                break
            try:
                text, tool_calls = await asyncio.wait_for(
                    self._llm.complete_with_tools(
                        system=system, messages=working,
                        tools=tool_defs, model_tier="fast",
                    ),
                    timeout=180.0,
                )
            except asyncio.TimeoutError:
                if tool_count > 0:
                    logger.warning("[astra] Round %d timed out after %d tools — attempting final completion", _round, tool_count)
                    try:
                        final = await asyncio.wait_for(
                            self._llm.complete(system=system, messages=working, model_tier="fast", temperature=0.5),
                            timeout=60.0,
                        )
                        return {"agent": "astra", "result": final, "messages_exchanged": msg_count + 1,
                                "tools_executed": tool_count, "tools_used": tools_used}
                    except Exception:
                        logger.debug("[astra] Final fast completion after timeout also failed", exc_info=True)
                return {
                    "agent": "astra", "result": "ASTRA analysis timed out — LLM provider may be slow. Try again shortly.",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            except Exception as llm_err:
                logger.error("[astra] LLM error: %s", llm_err)
                return {
                    "agent": "astra", "result": f"ASTRA encountered an error: {str(llm_err)[:200]}. Try again or check provider status.",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            msg_count += 1
            if not tool_calls:
                return {
                    "agent": "astra", "result": text or "Task handled.",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }

            tool_results: list[tuple[dict, str]] = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("input", {})
                logger.info("[astra] Tool: %s(%s)", name, json.dumps(args)[:200])
                try:
                    result = await asyncio.wait_for(self._plugins.invoke(name, args), timeout=30.0)
                except asyncio.TimeoutError:
                    result = type('R', (), {'success': False, 'output': None, 'error': f"Tool '{name}' timed out"})()
                except Exception as tool_err:
                    result = type('R', (), {'success': False, 'output': None, 'error': str(tool_err)})()
                output = result.output if result.success else {"error": result.error}
                output = sanitize_tool_output(output)
                output_str = json.dumps(output, default=str)[:5000]
                tool_results.append((tc, output_str))
                tool_count += 1
                if name not in tools_used:
                    tools_used.append(name)

            if is_openai:
                working.append({
                    "role": "assistant", "content": text or None,
                    "tool_calls": [
                        {"id": tc.get("id", f"call_{_round}_{i}"), "type": "function",
                         "function": {"name": tc["name"], "arguments": json.dumps(tc.get("input", {}))}}
                        for i, (tc, _) in enumerate(tool_results)
                    ],
                })
                for tc, out in tool_results:
                    working.append({"role": "tool", "tool_call_id": tc.get("id", f"call_{_round}"), "content": out})
            else:
                if text:
                    working.append({"role": "assistant", "content": text})
                working.append({
                    "role": "user",
                    "content": "[TOOL RESULTS]\n" + "\n".join(f"[{tc['name']}] → {out}" for tc, out in tool_results),
                })
            msg_count += 1

        final = await self._llm.complete(
            system=system, messages=working,
            model_tier="default", temperature=0.5,
        )
        msg_count += 1
        return {
            "agent": "astra", "result": final,
            "messages_exchanged": msg_count, "tools_executed": tool_count,
            "tools_used": tools_used,
        }

    def _build_weight_context(self) -> str:
        """Build routing weight context from learning engine for ASTRA's prompt."""
        if not self._learning:
            return ""
        weights = self._learning.get_routing_weights()
        if not weights:
            return ""

        # Group weights by agent
        agent_data: dict[str, list[tuple[str, float]]] = {}
        for key, weight in weights.items():
            parts = key.split(":", 1)
            if len(parts) == 2:
                agent_id, category = parts
                agent_data.setdefault(agent_id, []).append((category, weight))

        if not agent_data:
            return ""

        lines = [
            "\n\n## LEARNED ROUTING WEIGHTS (from past outcomes)\n"
            "These agents have proven track records. Prefer higher-weighted agents "
            "for matching task categories:\n"
        ]
        for agent_id, categories in sorted(agent_data.items()):
            top = sorted(categories, key=lambda x: x[1], reverse=True)[:3]
            entries = ", ".join(f"{cat}={w:.2f}" for cat, w in top)
            lines.append(f"- **{agent_id}**: {entries}")

        return "\n".join(lines) + "\n"

    def _build_ecosystem_routing_context(self) -> str:
        """Build ecosystem context so ASTRA routes with cross-project awareness."""
        if not self._ecosystem:
            return ""
        try:
            summary = self._ecosystem.get_ecosystem_summary()
            projects = self._ecosystem.get_all_projects()
            if not projects:
                return ""

            lines = [
                "\n\n## PROJECT ECOSYSTEM (Yohan's active ventures)\n"
                "Use this context to route requests to the right specialists "
                "and understand cross-project implications:\n"
            ]

            for p in projects:
                port_str = f" [port {p.port}]" if p.port else ""
                rev_str = f" ({p.revenue_stream})" if p.revenue_stream else ""
                lines.append(f"- **{p.name}**{port_str}{rev_str}: {p.description[:100]}")

            # Revenue mapping for economic routing
            by_stream = summary.get("by_revenue_stream", {})
            if by_stream:
                lines.append("\nRevenue streams:")
                for stream, names in by_stream.items():
                    lines.append(f"  - {stream}: {', '.join(names)}")

            # Cross-project connections for pipeline routing
            connections = self._ecosystem.get_connections()
            if connections:
                lines.append("\nCross-project links (consider for multi-agent routing):")
                for c in connections:
                    lines.append(f"  - {c['source']} ↔ {c['target']}: {c['description'][:80]}")

            lines.append(
                "\nWhen a request touches multiple projects, dispatch agents "
                "that can correlate across them. Use opportunity_scanner + analyst "
                "for cross-project revenue opportunities."
            )

            return "\n".join(lines) + "\n"
        except Exception as e:
            logger.debug("Ecosystem routing context failed: %s", e)
            return ""

    # ── Route cache helpers ─────────────────────────────────────

    def _cache_key(self, user_message: str) -> str:
        """Stable hash key for a user message (first 300 chars, lowercased)."""
        normalized = user_message.lower().strip()[:300]
        return hashlib.md5(normalized.encode()).hexdigest()

    def _get_cached_route(self, user_message: str) -> Optional[dict[str, Any]]:
        """Return a cached route decision if it exists and hasn't expired."""
        key = self._cache_key(user_message)
        entry = self._route_cache.get(key)
        if entry is None:
            return None
        ts, route_dict = entry
        if time.monotonic() - ts > _ROUTE_CACHE_TTL_SECONDS:
            del self._route_cache[key]
            return None
        logger.debug("[astra] Route cache hit for '%s'", user_message[:60])
        return dict(route_dict)  # return a copy

    def _cache_route(self, user_message: str, route_dict: dict[str, Any]) -> None:
        """Store a route decision in the cache. Evict oldest if > 200 entries."""
        if len(self._route_cache) >= 200:
            # Remove the oldest entry (dict insertion order in Python 3.7+)
            oldest_key = next(iter(self._route_cache))
            del self._route_cache[oldest_key]
        self._route_cache[self._cache_key(user_message)] = (time.monotonic(), route_dict)

    def _build_ambiguous_fallback(self, user_message: str) -> dict[str, Any]:
        """When confidence is low, dispatch researcher + analyst in parallel."""
        return {
            "route": "multi",
            "agent_ids": ["researcher", "analyst"],
            "confidence": 0.5,
            "subtasks": [
                {"agent_id": "researcher",
                 "task": f"Research thoroughly: {user_message}. Use web_search with multiple queries."},
                {"agent_id": "analyst",
                 "task": f"Analyze and evaluate: {user_message}. Use available tools."},
            ],
            "reasoning": "Low-confidence route — dispatching researcher + analyst in parallel for coverage",
            "routing_explanation": (
                "Query was ambiguous so ASTRA fell back to parallel researcher + analyst dispatch "
                "to ensure broad coverage. Researcher gathers raw data while analyst evaluates it."
            ),
        }

    async def route_request(self, user_message: str, agents_desc: str) -> dict[str, Any]:
        """ASTRA decides how to route a request — which agents to dispatch.

        Enhancements over original:
        - Route cache: identical queries reuse the last decision for up to 5 min
        - Confidence score: LLM must return confidence ≥ 0.70 or route is escalated
        - Ambiguous fallback: low-confidence queries use parallel researcher + analyst
        - Routing explanation: every decision carries a human-readable explanation

        Returns: {"route": "direct"|"delegate"|"multi"|"pipeline",
                  "agent_ids": [...], "confidence": 0.0–1.0,
                  "subtasks": [...], "reasoning": "...", "routing_explanation": "..."}
        """
        if not self._llm:
            return {"route": "direct", "agent_ids": [], "confidence": 1.0,
                    "reasoning": "No LLM", "routing_explanation": "No LLM configured — direct handling."}

        # 1. Cache lookup — skip LLM for repeated identical queries
        cached = self._get_cached_route(user_message)
        if cached is not None:
            cached["routing_explanation"] = (
                f"[CACHED] {cached.get('routing_explanation', cached.get('reasoning', ''))}"
            )
            return cached

        routing_prompt = (
            "You are ASTRA, an AI router. Output ONLY valid JSON, no other text.\n\n"
            "JSON format (ALL fields required):\n"
            '{"route":"multi","agent_ids":["swarm","analyst","researcher"],'
            '"confidence":0.85,'
            '"subtasks":[{"agent_id":"swarm","task":"TASK1"},{"agent_id":"analyst","task":"TASK2"}],'
            '"reasoning":"Short reason for this route",'
            '"routing_explanation":"1-2 sentence human-readable explanation: which agent handles what and why"}\n\n'
            "Routes:\n"
            "  direct   — ONLY for greetings/trivial questions (hi, what time is it)\n"
            "  delegate — single clear task in one domain (e.g. write this email)\n"
            "  multi    — 2+ agents in parallel for complex, multi-domain, or financial tasks\n"
            "  pipeline — sequential chain where each agent's output feeds the next\n\n"
            "confidence: 0.0–1.0 — how certain you are this is the right routing decision.\n"
            "  1.0 = crystal clear single-domain task\n"
            "  0.7 = fairly confident\n"
            "  0.5 = ambiguous, could be handled multiple ways\n"
            "  < 0.7 triggers automatic parallel fallback regardless of your route choice\n\n"
            "routing_explanation: tell Yohan WHICH agent handles WHAT and WHY in plain English.\n"
            "  Example: 'Dispatching swarm for market signals and analyst to evaluate risk, "
            "because the request involves both live trading data and financial modeling.'\n\n"
            "IMPORTANT: Output raw JSON only. No markdown, no explanation, no ```.\n\n"
            "Team routing guide (use multi for ALL of these):\n"
            "- Trading/stocks/markets    → [swarm, researcher, analyst, risk_strategist]\n"
            "- Options/derivatives       → [researcher, miro, analyst, risk_strategist]\n"
            "- Polymarket/predictions    → [researcher, miro, analyst]\n"
            "- Research + analysis       → pipeline: [researcher → analyst → knowledge_synthesizer]\n"
            "- Code/build                → [coder, chief_architect, test_engineer]\n"
            "- Strategy/planning         → [miro, strategic_synthesizer, analyst]\n"
            "- Revenue/business          → [opportunity_scanner, analyst, startup_builder]\n"
            "- Security                  → [guardian, security_researcher, compliance_agent]\n"
            "- Simple research           → delegate: [researcher]\n"
            "- Simple writing            → delegate: [writer]\n"
            "RULE: Financial, trading, market, or multi-domain tasks ALWAYS use multi or pipeline.\n"
            "Default for truly ambiguous requests: confidence < 0.7 (triggers parallel fallback).\n"
        )

        # Inject learned routing weights so ASTRA uses past performance data
        weight_section = self._build_weight_context()
        if weight_section:
            routing_prompt += weight_section

        # Inject ecosystem awareness so routing considers cross-project context
        eco_section = self._build_ecosystem_routing_context()
        if eco_section:
            routing_prompt += eco_section

        prompt = f"Available agents:\n{agents_desc}\n\nUser request: {user_message}"

        response = await self._llm.complete(
            system=routing_prompt,
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast",
            temperature=0.2,
        )

        try:
            text = response.strip()
            # Extract JSON from markdown code blocks if present
            if "```" in text:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                text = text[start:end].strip()
            parsed = json.loads(text)

            # Ensure confidence is present and numeric
            confidence = float(parsed.get("confidence", 1.0))
            parsed["confidence"] = round(confidence, 3)

            # Ensure routing_explanation is present
            if not parsed.get("routing_explanation"):
                parsed["routing_explanation"] = parsed.get("reasoning", "No explanation provided.")

            # 2. Confidence threshold check — low confidence → parallel fallback
            if confidence < _ROUTING_CONFIDENCE_THRESHOLD:
                logger.info(
                    "[astra] Low routing confidence %.2f for '%s' — escalating to parallel fallback",
                    confidence, user_message[:60],
                )
                fallback = self._build_ambiguous_fallback(user_message)
                fallback["confidence"] = confidence  # preserve original confidence
                self._cache_route(user_message, fallback)
                return fallback

            # 3. Sanitize agent IDs — filter out non-existent agents (LLM hallucinations)
            if self._registry:
                valid_ids = set()
                for aid in parsed.get("agent_ids", []):
                    aid_norm = aid.lower().replace(" ", "_")
                    if self._registry.get_connector(aid_norm):
                        valid_ids.add(aid_norm)
                    elif self._registry.get_connector(aid):
                        valid_ids.add(aid)
                    else:
                        logger.warning("ASTRA routed to non-existent agent '%s', replacing with 'researcher'", aid)
                        valid_ids.add("researcher")
                parsed["agent_ids"] = list(valid_ids)

                # Also fix subtasks
                for st in parsed.get("subtasks", []):
                    aid = st.get("agent_id", "")
                    if aid:
                        aid_norm = aid.lower().replace(" ", "_")
                        if self._registry.get_connector(aid_norm):
                            st["agent_id"] = aid_norm
                        elif not self._registry.get_connector(aid):
                            logger.warning("ASTRA subtask agent '%s' not found, replacing with 'researcher'", aid)
                            st["agent_id"] = "researcher"

            # 4. Cache the valid route
            self._cache_route(user_message, parsed)
            return parsed

        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("ASTRA routing JSON parse failed: %s. Response: %s", exc, response[:200])
            # Ollama sometimes returns conversational text instead of JSON.
            # Fall back to parallel researcher + analyst as safety net.
            fallback = self._build_ambiguous_fallback(user_message)
            fallback["reasoning"] = "JSON parse fallback — dispatching researcher + analyst"
            return fallback

    @staticmethod
    def _clean_synthesis(text: str) -> str:
        """Strip raw JSON from synthesis output — LLM sometimes returns routing JSON."""
        if not text:
            return text
        stripped = text.strip()
        # Detect raw JSON routing output (starts with { and looks like routing data)
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                # If it looks like routing JSON (has route/task/agent_ids keys), discard it
                routing_keys = {"route", "task", "agent_ids", "subtasks", "reasoning"}
                if routing_keys & set(parsed.keys()):
                    logger.warning("Synthesis returned routing JSON instead of text — discarding")
                    return ""
            except (json.JSONDecodeError, ValueError):
                logger.debug("Synthesis response is not JSON, treating as text", exc_info=True)
        return text

    async def synthesize_findings(
        self,
        user_message: str,
        agent_findings: list[dict[str, str]],
        memory_context: str = "",
    ) -> str:
        """ASTRA synthesizes all agent findings into a unified response for Yohan."""
        if not self._llm:
            # Fallback: just concatenate
            parts = [f"**{f['agent_name']}**: {f['result']}" for f in agent_findings]
            return "\n\n---\n\n".join(parts)

        # Filter out failed/empty findings before synthesis
        _failure_signals = ("LLM request timed out", "No response", "LLM error:",
                            "No connector for", "No output", "No LLM configured",
                            "analysis timed out", "encountered an error")
        real_findings = [
            f for f in agent_findings
            if f.get("result") and not any(f["result"].startswith(sig) for sig in _failure_signals)
        ]

        if not real_findings:
            logger.warning("All agent findings are failures — skipping synthesis")
            return ""

        findings_text = "\n\n".join(
            f"### {f['agent_name']} ({f['agent_id']})\n"
            f"Task: {f['task']}\n"
            f"Status: {f['status']}\n"
            f"Findings:\n{f['result']}"
            for f in real_findings
        )

        now = datetime.now(timezone.utc)
        date_line = f"\n\n## Current Date\nToday is {now.strftime('%A, %B %d, %Y')} (UTC). Use this date for all responses — never reference outdated dates from training data."
        system = (
            f"{_ASTRA_PROMPT}\n\n"
            "## Synthesis Task\n"
            "Your agents have completed their work. Synthesize their findings into a\n"
            "PRECISE, ACCURATE STUDY for Yohan. This is NOT a summary — it's a report.\n\n"
            "## Study Format (MANDATORY)\n"
            "1. **Executive Summary**: 2-3 sentences of key findings\n"
            "2. **Detailed Findings**: Organized by topic with real data, numbers, sources\n"
            "3. **Cross-Check Results**: Where agents agree/disagree and what's verified\n"
            "4. **Risk Assessment**: What could go wrong, confidence levels\n"
            "5. **Proposed Direction**: What Yohan should do next and why\n"
            "6. **Approval Request**: If any action is needed, present it clearly:\n"
            "   - PROPOSED ACTION → REASON → RISK → COST → Awaiting approval\n\n"
            "Rules:\n"
            "- Include REAL numbers and verifiable data — never fabricate\n"
            "- NEVER dump raw data or JSON — always interpret and present clearly\n"
            "- Highlight conflicts between agent findings\n"
            "- Think about the BIGGER PICTURE — what does this mean for Yohan's goals?\n"
            "- Match depth to complexity: simple question = efficient answer, complex topic = thorough deep-dive\n"
            "- Propose the logical next steps autonomously\n"
            "- Ask for approval before any execution, spending, or external action"
            f"{date_line}"
        )

        context_block = f"\n\n## Relevant Memories\n{memory_context}" if memory_context else ""

        messages = [{
            "role": "user",
            "content": (
                f"Yohan asked: {user_message}\n\n"
                f"## Agent Findings\n{findings_text}"
                f"{context_block}\n\n"
                f"Synthesize this into a unified response."
            ),
        }]

        tool_defs = self._plugins.list_tools() if self._plugins else []

        if not tool_defs:
            result = await self._llm.complete(
                system=system, messages=messages,
                model_tier="default", temperature=0.5,
            )
            return self._clean_synthesis(result) or result

        # Allow ASTRA to use tools during synthesis (e.g., additional research)
        is_openai = getattr(self._llm, "provider", "") == "openai"
        working = list(messages)
        for _round in range(3):
            try:
                text, tool_calls = await asyncio.wait_for(
                    self._llm.complete_with_tools(
                        system=system, messages=working,
                        tools=tool_defs, model_tier="fast",
                    ),
                    timeout=180.0,
                )
            except asyncio.TimeoutError:
                return ""  # Empty string triggers direct fallback in brain.py
            except Exception as llm_err:
                logger.error("[astra-synth] LLM error: %s", llm_err)
                return ""  # Empty string triggers direct fallback in brain.py
            if not tool_calls:
                cleaned = self._clean_synthesis(text or "")
                return cleaned if cleaned else (text or "")

            tool_results: list[tuple[dict, str]] = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("input", {})
                logger.info("[astra-synth] Tool: %s(%s)", name, json.dumps(args)[:200])
                try:
                    result = await asyncio.wait_for(self._plugins.invoke(name, args), timeout=30.0)
                except asyncio.TimeoutError:
                    result = type('R', (), {'success': False, 'output': None, 'error': f"Tool '{name}' timed out"})()
                except Exception as tool_err:
                    result = type('R', (), {'success': False, 'output': None, 'error': str(tool_err)})()
                output = result.output if result.success else {"error": result.error}
                output_str = json.dumps(output, default=str)[:4000]
                tool_results.append((tc, output_str))

            if is_openai:
                working.append({
                    "role": "assistant", "content": text or None,
                    "tool_calls": [
                        {"id": tc.get("id", f"call_{_round}_{i}"), "type": "function",
                         "function": {"name": tc["name"], "arguments": json.dumps(tc.get("input", {}))}}
                        for i, (tc, _) in enumerate(tool_results)
                    ],
                })
                for tc, out in tool_results:
                    working.append({"role": "tool", "tool_call_id": tc.get("id", f"call_{_round}"), "content": out})
            else:
                if text:
                    working.append({"role": "assistant", "content": text})
                working.append({
                    "role": "user",
                    "content": "[TOOL RESULTS]\n" + "\n".join(f"[{tc['name']}] → {out}" for tc, out in tool_results),
                })

        final = await self._llm.complete(
            system=system, messages=working,
            model_tier="default", temperature=0.5,
        )
        return self._clean_synthesis(final) or final
