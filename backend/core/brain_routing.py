"""
Brain routing mixin — intent detection, forced delegation, tool-use loop,
synthesis helpers, goal creation, directive context, and learning extraction.

Extracted from brain.py to keep file sizes manageable.
These methods are mixed into the Brain class via BrainRoutingMixin.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.models.agent import AgentFinding
from backend.models.memory import MemoryEntry, MemoryType

if TYPE_CHECKING:
    pass

logger = logging.getLogger("root.brain")


class BrainRoutingMixin:
    """Mixin providing routing, tool-use, synthesis, and learning helpers for Brain."""

    # ── Intent Detection & Forced Delegation ────────────────────

    _RESEARCH_KEYWORDS = (
        "research", "find", "search", "look up", "look into", "investigate",
        "analyze", "analysis", "compare", "what is", "what are", "how does",
        "how do", "tell me about", "info on", "information about", "learn about",
        "explore", "discover", "report on", "deep dive", "study", "examine",
        "assess", "evaluate", "review", "scan", "check", "monitor",
        "price", "market", "stock", "crypto", "bitcoin", "trend",
        "news", "latest", "current", "today", "opportunities",
    )

    _DIRECT_KEYWORDS = (
        "hello", "hi", "hey", "thanks", "thank you", "good morning",
        "good night", "how are you", "what can you do", "help",
        "status", "remember", "forget", "clear",
    )

    def _force_delegation_if_needed(
        self, user_message: str,
    ) -> tuple[str, list[dict]]:
        """Detect research/action intent and build subtasks when ASTRA fails to route.

        Uses specialist civilization agents for targeted tasks instead of always
        defaulting to the 6 core internal agents.
        """
        lower = user_message.lower().strip()

        # Skip if it's clearly a direct/greeting message
        if any(lower.startswith(kw) or lower == kw for kw in self._DIRECT_KEYWORDS):
            return "direct", []

        # Check for research/action intent
        has_research_intent = any(kw in lower for kw in self._RESEARCH_KEYWORDS)

        # Also trigger for longer messages (>30 chars) that aren't greetings
        is_substantive = len(lower) > 30

        if not has_research_intent and not is_substantive:
            return "direct", []

        # Build subtasks based on intent — USE SPECIALIST AGENTS
        subtasks: list[dict[str, str]] = []

        # Trading/strategy intent → full autonomous pipeline
        trading_words = ("trading", "trade", "backtest", "strategy", "stock", "crypto", "bitcoin", "invest")
        if any(w in lower for w in trading_words):
            learn_words = ("learn", "study", "understand", "explore", "discover", "research")
            if any(w in lower for w in learn_words):
                # "Learn about trading" → full pipeline: research → analyze → backtest
                return "pipeline", [
                    {
                        "agent_id": self._best_agent_for("market", "researcher"),
                        "task": f"Search the web for profitable trading strategies, current market trends, and quantitative approaches related to: {user_message}. Use web_search with multiple queries. Find specific strategies with entry/exit rules.",
                        "depends_on": None,
                    },
                    {
                        "agent_id": self._best_agent_for("algorithm_research", "algorithm_researcher"),
                        "task": f"Based on the research findings, analyze the most promising algorithmic trading strategies. Evaluate their mathematical foundations, risk/reward profiles, and implementation complexity.",
                        "depends_on": 0,
                    },
                    {
                        "agent_id": self._best_agent_for("backtesting", "backtester"),
                        "task": f"Take the top 3 strategies identified and design backtesting parameters. Calculate expected returns, max drawdown, Sharpe ratio, and win rate using historical patterns. Use calculate tool for computations.",
                        "depends_on": 1,
                    },
                    {
                        "agent_id": self._best_agent_for("analysis", "analyst"),
                        "task": f"Synthesize all findings into actionable recommendations. Which strategy should Yohan implement? What's the risk? What capital is needed? Include specific numbers.",
                        "depends_on": 2,
                    },
                ]
            # Direct trading intent
            subtasks.extend([
                {
                    "agent_id": self._best_agent_for("market", "researcher"),
                    "task": f"Search the web for current, real-time data about: {user_message}. Use web_search with multiple queries and fetch_url for details.",
                },
                {
                    "agent_id": "swarm",
                    "task": f"Analyze market conditions and generate signals for: {user_message}. Use trading tools.",
                },
                {
                    "agent_id": self._best_agent_for("analysis", "analyst"),
                    "task": f"Analyze risk and opportunity with current data. Use financial tools: {user_message}",
                },
            ])
            return "multi", subtasks

        # Market/price intent (not trading strategy)
        market_words = ("market", "price", "trend", "forecast")
        if any(w in lower for w in market_words):
            subtasks.extend([
                {
                    "agent_id": self._best_agent_for("market", "market_researcher"),
                    "task": f"Search for current market data and trends: {user_message}. Use web_search.",
                },
                {
                    "agent_id": self._best_agent_for("analysis", "analyst"),
                    "task": f"Analyze market data with financial tools: {user_message}",
                },
            ])
            return "multi", subtasks

        # Revenue/money/opportunity intent → economic engine agents
        revenue_words = ("revenue", "money", "income", "profit", "saas", "business", "startup", "product")
        if any(w in lower for w in revenue_words):
            subtasks.extend([
                {
                    "agent_id": self._best_agent_for("opportunity", "opportunity_scanner"),
                    "task": f"Scan for opportunities related to: {user_message}. Use web_search to find market gaps, demand signals, and competitor analysis.",
                },
                {
                    "agent_id": self._best_agent_for("analysis", "analyst"),
                    "task": f"Analyze the financial viability. Use calculate and financial tools: {user_message}",
                },
                {
                    "agent_id": self._best_agent_for("marketing", "marketing_strategist"),
                    "task": f"Research go-to-market strategy: {user_message}. Use web_search for market size and channels.",
                },
            ])
            return "multi", subtasks

        # Code intent
        code_words = ("code", "debug", "fix", "implement", "function", "class", "bug", "error")
        if any(w in lower for w in code_words):
            subtasks.append({
                "agent_id": self._best_agent_for("code", "coder"),
                "task": f"Handle this coding task: {user_message}. Use tools as needed.",
            })
            # Add code reviewer for quality
            if any(w in lower for w in ("review", "quality", "improve", "refactor")):
                subtasks.append({
                    "agent_id": "code_reviewer_eng",
                    "task": f"Review the code quality and suggest improvements: {user_message}",
                })
                return "multi", subtasks
            return "delegate", subtasks

        # Build intent → pipeline
        build_words = ("build", "create", "launch", "deploy", "ship")
        if any(w in lower for w in build_words):
            return "pipeline", [
                {
                    "agent_id": self._best_agent_for("research", "researcher"),
                    "task": f"Research best practices, existing solutions, and architecture patterns for: {user_message}. Use web_search.",
                    "depends_on": None,
                },
                {
                    "agent_id": self._best_agent_for("architecture", "chief_architect"),
                    "task": f"Design the architecture and implementation plan based on research findings for: {user_message}",
                    "depends_on": 0,
                },
                {
                    "agent_id": self._best_agent_for("code", "coder"),
                    "task": f"Implement the solution based on the architecture plan: {user_message}",
                    "depends_on": 1,
                },
            ]

        # Security intent → specialist agents
        security_words = ("security", "vulnerability", "hack", "breach", "secure", "audit")
        if any(w in lower for w in security_words):
            subtasks.extend([
                {
                    "agent_id": self._best_agent_for("security", "guardian"),
                    "task": f"Run security checks and monitoring: {user_message}",
                },
                {
                    "agent_id": "security_researcher",
                    "task": f"Research latest security threats and vulnerabilities related to: {user_message}. Use web_search.",
                },
            ])
            return "multi", subtasks

        # Learning intent → research pipeline
        learn_words = ("learn", "study", "understand", "explore", "master")
        if any(w in lower for w in learn_words):
            return "pipeline", [
                {
                    "agent_id": self._best_agent_for("research", "researcher"),
                    "task": f"Search the web thoroughly for: {user_message}. Use web_search with multiple queries, fetch_url for full details. Return findings with sources.",
                    "depends_on": None,
                },
                {
                    "agent_id": self._best_agent_for("knowledge", "knowledge_synthesizer"),
                    "task": f"Synthesize the research into a structured learning guide. Identify key concepts, best resources, and practical next steps.",
                    "depends_on": 0,
                },
            ]

        # Default: best general-purpose agent (learned or fallback to researcher)
        default_agent = self._best_agent_for("research", "researcher")
        subtasks.append({
            "agent_id": default_agent,
            "task": f"Search the web thoroughly for: {user_message}. Use web_search with multiple queries, fetch_url for full details. Return findings with sources and dates.",
        })

        # Add analyst for analysis-heavy requests
        analysis_words = ("analyze", "compare", "evaluate", "assess", "forecast", "predict", "opportunity")
        if any(w in lower for w in analysis_words):
            analysis_agent = self._best_agent_for("analysis", "analyst")
            subtasks.append({
                "agent_id": analysis_agent,
                "task": f"Analyze the following using tools and calculations: {user_message}",
            })
            return "multi", subtasks

        return "delegate", subtasks

    def _best_agent_for(self, category: str, fallback: str) -> str:
        """Return the best agent for a category using learning weights, or fallback."""
        if not self._learning:
            return fallback
        best = self._learning.get_best_agent_for(category)
        return best if best else fallback

    # ── Tool-Use Loop ───────────────────────────────────────────

    async def _tool_use_loop(
        self,
        system: str,
        messages: list[dict[str, str]],
        tool_defs: list[dict],
        max_rounds: int = 5,
    ) -> str:
        """LLM -> tool calls -> execute -> feed results -> repeat until done."""
        if not tool_defs or not self._plugins:
            return await self._llm.complete(
                system=system, messages=messages,
                model_tier="default", temperature=0.7,
            )

        working = list(messages)

        for _round in range(max_rounds):
            text, tool_calls = await self._llm.complete_with_tools(
                system=system, messages=working,
                tools=tool_defs, model_tier="default",
            )

            if not tool_calls:
                return text or await self._llm.complete(
                    system=system, messages=working,
                    model_tier="default", temperature=0.7,
                )

            # Execute each tool
            is_openai = getattr(self._llm, "provider", "") == "openai"
            tool_results: list[tuple[dict, str]] = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("input", {})
                logger.info("Tool call [round %d]: %s(%s)", _round + 1, name, json.dumps(args)[:200])

                result = await self._plugins.invoke(name, args)
                output = result.output if result.success else {"error": result.error}
                output_str = json.dumps(output, default=str)[:4000]
                tool_results.append((tc, output_str))
                logger.info("Tool result: %s -> %s chars", name, len(output_str))

            # Feed results back in provider-appropriate format
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
                parts = [f"**[{tc['name']}]** returned:\n```json\n{out}\n```" for tc, out in tool_results]
                working.append({
                    "role": "user",
                    "content": "[TOOL RESULTS — use this real data to answer]\n\n" + "\n\n".join(parts),
                })

        # Exhausted rounds — final completion
        return await self._llm.complete(
            system=system, messages=working,
            model_tier="default", temperature=0.7,
        )

    # ── Synthesis & Formatting Helpers ─────────────────────────

    def _fallback_synthesis(self, user_message: str, findings: list[AgentFinding]) -> str:
        """Simple concatenation fallback when ASTRA synthesis fails."""
        parts = [f"**Re: {user_message}**\n"]
        for f in findings:
            status_icon = "\u2713" if f.status == "completed" else "\u2717"
            parts.append(f"### {status_icon} {f.agent_name}\n*Task: {f.task}*\n\n{f.result}")
        return "\n\n---\n\n".join(parts)

    def _format_council_session(self, session) -> str:
        """Format Strategy Council results for display."""
        parts = [
            f"**Strategy Council \u2014 {session.total_opportunities} Opportunities Identified**\n",
            f"Agents consulted: {', '.join(session.agents_consulted)}",
            f"Session: {session.id} ({session.session_duration_seconds:.1f}s)\n",
        ]
        if session.top_recommendation:
            top = session.top_recommendation
            parts.append(f"**Top Recommendation: {top.title}**")
            parts.append(f"Confidence: **{top.confidence_score:.0%}** | Risk: {top.risk_level.value}")
            if top.estimated_monthly_revenue:
                parts.append(f"Est. revenue: **${top.estimated_monthly_revenue:,.0f}/mo**")
            parts.append(f"\n{top.description}\n")
        parts.append("---\n**All Opportunities (ranked by confidence):**\n")
        for i, opp in enumerate(session.opportunities, 1):
            revenue = f"${opp.estimated_monthly_revenue:,.0f}/mo" if opp.estimated_monthly_revenue else "TBD"
            capital = f"${opp.capital_required:,.0f}" if opp.capital_required > 0 else "Free"
            parts.append(
                f"{i}. **{opp.title}** \u2014 {opp.confidence_score:.0%} confidence\n"
                f"   Type: {opp.opportunity_type.value} | Risk: {opp.risk_level.value} | "
                f"Revenue: {revenue} | Capital: {capital}"
            )
        return "\n".join(parts)

    # ── Goal Auto-Creation ─────────────────────────────────────

    async def _maybe_create_goal(
        self, user_message: str, route: str, agents_used: list[str],
    ) -> None:
        """Detect goal-worthy intent and auto-create a goal."""
        goal_keywords = (
            "build", "create", "launch", "start", "implement", "develop",
            "automate", "optimize", "improve", "grow", "learn", "master",
            "make money", "revenue", "deploy", "ship", "scale",
        )
        lower = user_message.lower()
        if not any(kw in lower for kw in goal_keywords):
            return

        # Determine category
        category = "general"
        if any(w in lower for w in ("money", "revenue", "trade", "invest", "profit")):
            category = "trading"
        elif any(w in lower for w in ("learn", "study", "master", "understand")):
            category = "learning"
        elif any(w in lower for w in ("build", "create", "deploy", "ship", "code")):
            category = "automation"

        # Check for duplicate goals (avoid spamming)
        active = self._goal_engine.get_active_goals(limit=20)
        for goal in active:
            if BrainRoutingMixin._text_overlap(goal.title, user_message) > 0.5:
                return

        self._goal_engine.add_goal(
            title=user_message[:200],
            description=f"Auto-detected from chat. Route: {route}, agents: {', '.join(agents_used)}",
            priority=5,
            source="brain",
            category=category,
        )
        logger.info("Auto-created goal from chat: %s", user_message[:80])

    # ── Directive Context ──────────────────────────────────────

    def _build_directive_context(self) -> str:
        """Build context string showing active autonomous directives."""
        if not self._directive:
            return ""
        try:
            active = self._directive.get_active_directives()
            if not active:
                return ""
            lines = ["## Active Autonomous Directives (ROOT is working on these)"]
            for d in active[:5]:
                agents = ", ".join(d.get("assigned_agents", []))
                lines.append(
                    f"- [{d.get('priority', 5)}] **{d.get('title', '')}** "
                    f"({d.get('category', 'general')}, {d.get('status', '')}) "
                    f"\u2192 agents: {agents}"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("Failed to build directive context: %s", exc)
            return ""

    # ── Utilities ──────────────────────────────────────────────

    @staticmethod
    def _text_overlap(a: str, b: str) -> float:
        """Word overlap ratio between two strings."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    # ── Learning Extraction ────────────────────────────────────

    async def _extract_learnings(self, user_msg: str, response: str) -> None:
        """Use the fast model to extract any learnable info from the exchange."""
        prompt = f"""Analyze this exchange and extract facts worth remembering.
Return JSON array of objects, each with "content", "type" (preference|fact|goal|observation), and "tags" (list).
Return empty array [] if nothing worth remembering.

USER: {user_msg[:500]}
ASSISTANT: {response[:500]}"""

        try:
            result = await self._llm.complete(
                system="Extract memorable facts. Return only a JSON array.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                temperature=0.2,
                max_tokens=1024,
            )
            text = result.strip()
            if "```" in text:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                text = text[start:end].strip()
            items = json.loads(text)
            if not isinstance(items, list):
                return
            for item in items[:5]:
                try:
                    mt = MemoryType(item.get("type", "observation"))
                except ValueError:
                    mt = MemoryType.OBSERVATION
                self._memory.store(MemoryEntry(
                    content=item["content"],
                    memory_type=mt,
                    tags=item.get("tags", []),
                    source="auto_extract",
                ))
        except Exception as exc:
            logger.debug("Failed to extract learnings: %s", exc)
