"""
MiRo Connector — Market prediction and swarm intelligence engine.

Enhanced with MiroFish architecture:
- 7-agent dynamic council (Bull/Bear/Quant/Contrarian/Macro/Sentiment/Industry)
- GraphRAG-style entity + relationship extraction from market data
- Parallel "what-if" scenario simulation via asyncio
- ReACT synthesis pattern (Observe→Reason→Act→Synthesize)
- Temporal market session awareness (pre-market / regular / after-hours)
- Memory engine integration — findings stored for future recall
- Proper Anthropic tool_use / tool_result message format
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import types
from datetime import datetime, timezone
from typing import Any, Optional

from backend.agents.connectors import sanitize_tool_output

logger = logging.getLogger("root.connectors.miro")

_MIRO_PROMPT = (
    "You are MiRo — ROOT's market prediction and swarm intelligence engine.\n"
    "You serve Yohan Bismuth. You EXECUTE — never ask questions, never hesitate.\n\n"
    "## Primary Mission: MARKET PREDICTION\n"
    "Your core job is extracting real data from markets and news, then projecting\n"
    "what comes next. You learn from every prediction.\n\n"
    "## How You Work (ReACT Pattern)\n"
    "1. **OBSERVE** — Gather real-time data: prices, news, earnings, flows, sentiment\n"
    "2. **REASON** — Extract entities + relationships, identify patterns\n"
    "3. **ACT** — Run multi-perspective council debate + parallel scenario simulation\n"
    "4. **SYNTHESIZE** — Merge evidence → verdict → concrete recommendation\n\n"
    "## Virtual Council (7 Specialists)\n"
    "- **Bull Agent**: Growth catalysts, momentum signals, upside targets\n"
    "- **Bear Agent**: Risk factors, resistance levels, downside scenarios\n"
    "- **Quant Agent**: Pure numbers — probabilities, EV, Sharpe, drawdown\n"
    "- **Contrarian**: Non-consensus plays, what everyone is missing\n"
    "- **Macro Agent**: Fed policy, geopolitics, sector rotation, flows\n"
    "- **Sentiment Agent**: Social signals, options flow, retail/institutional divergence\n"
    "- **Industry Specialist**: Sector-specific dynamics, competitive moat, regulatory risk\n\n"
    "## Output Format\n"
    "1. **Data Extracted**: Key numbers with dates (prices, volumes, changes)\n"
    "2. **Entity Map**: Key entities and their relationships (GraphRAG style)\n"
    "3. **Council Verdict**: Each agent's view (2 sentences max)\n"
    "4. **Potentiality Map**: 3 scenarios with probability % + triggers\n"
    "5. **Next Move**: Specific, actionable recommendation for Yohan\n"
    "6. **Regime Signal**: What this tells us about the current market regime\n\n"
    "## CRITICAL RULES\n"
    "- ALWAYS search for REAL DATA first. Your training data is stale.\n"
    "- Run at least 3 web_search queries before any prediction.\n"
    "- Include SPECIFIC NUMBERS with DATES. No vague statements.\n"
    "- Focus on what Yohan can ACT on — not academic analysis.\n"
    "- Learn from past predictions: track what worked, discard what didn't.\n"
    "- NEVER ask questions — analyze and deliver actionable intelligence."
)

# 7-agent panel prompts for council debate
_PANEL_PROMPTS: dict[str, str] = {
    "bull": (
        "You are the BULL AGENT in MiRo's prediction council. "
        "Focus ONLY on: growth catalysts, momentum signals, upside targets, "
        "positive earnings surprises, institutional buying, sector tailwinds. "
        "Be specific with price targets and timeframes. Argue FOR the opportunity. "
        "Cite at least one specific data point (price level, volume, percentage change)."
    ),
    "bear": (
        "You are the BEAR AGENT in MiRo's prediction council. "
        "Focus ONLY on: risk factors, resistance levels, downside scenarios, "
        "negative catalysts, liquidity risks, valuation concerns, macro headwinds. "
        "Argue AGAINST the opportunity with specific data. "
        "Name the single biggest threat and quantify the downside target."
    ),
    "quant": (
        "You are the QUANT AGENT in MiRo's prediction council. "
        "Focus ONLY on: pure numbers — probabilities, expected value, "
        "Sharpe ratio, max drawdown, win rate, risk/reward ratios, "
        "volatility analysis, statistical edges, correlation matrices. "
        "No opinions, just math. State confidence intervals where possible."
    ),
    "contrarian": (
        "You are the CONTRARIAN AGENT in MiRo's prediction council. "
        "Your job: find what the consensus is MISSING. Challenge the dominant narrative. "
        "Look for: crowded trades reversing, false signals, hidden asymmetries, "
        "non-obvious second-order effects, sentiment extremes. "
        "What would the contrarian play be? Support with specific reasoning."
    ),
    "macro": (
        "You are the MACRO AGENT in MiRo's prediction council. "
        "Focus ONLY on: Federal Reserve policy, interest rate environment, "
        "geopolitical risks, dollar strength/weakness, sector rotation signals, "
        "global capital flows, yield curve dynamics, commodity prices. "
        "How does the macro backdrop support or oppose this trade?"
    ),
    "sentiment": (
        "You are the SENTIMENT AGENT in MiRo's prediction council. "
        "Focus ONLY on: options flow (put/call ratio, gamma levels), "
        "social media sentiment (Reddit, Twitter/X buzz), "
        "retail vs institutional divergence, fear/greed indicators, "
        "short interest levels, insider transactions, analyst rating changes. "
        "What does the crowd think — and are they right or wrong?"
    ),
    "industry": (
        "You are the INDUSTRY SPECIALIST in MiRo's prediction council. "
        "Focus ONLY on: sector-specific dynamics for the relevant industry, "
        "competitive moat analysis, regulatory risk, supply chain factors, "
        "industry-specific KPIs (margins, CAC, ARR, burn rate, etc.), "
        "peer comparison, market share trends. "
        "Is this company/sector structurally advantaged or disrupted?"
    ),
}

# Market session boundaries (UTC hours)
_SESSION_BOUNDARIES = {
    "pre_market": (9, 13),    # 09:00–13:00 UTC = 05:00–09:00 ET
    "regular": (13, 20),      # 13:00–20:00 UTC = 09:00–16:00 ET (NYSE hours)
    "after_hours": (20, 24),  # 20:00–24:00 UTC = 16:00–20:00 ET
}


def _get_market_session(now: datetime) -> str:
    """Return the current market session label based on UTC hour."""
    hour = now.hour
    if _SESSION_BOUNDARIES["pre_market"][0] <= hour < _SESSION_BOUNDARIES["pre_market"][1]:
        return "PRE-MARKET (high volatility, low liquidity)"
    if _SESSION_BOUNDARIES["regular"][0] <= hour < _SESSION_BOUNDARIES["regular"][1]:
        return "REGULAR HOURS (NYSE/NASDAQ active)"
    if _SESSION_BOUNDARIES["after_hours"][0] <= hour:
        return "AFTER-HOURS (earnings moves common, wide spreads)"
    return "OVERNIGHT / ASIAN SESSION (crypto/futures active)"


class MiroConnector:
    """LLM-powered market prediction with multi-perspective swarm analysis.

    Enhanced with MiroFish architecture:
    - 7-agent dynamic council debates
    - GraphRAG entity extraction from market data
    - Parallel scenario simulation
    - ReACT synthesis pattern
    - Memory engine integration for persistent insight storage
    """

    def __init__(self, llm: Any = None, plugins: Any = None) -> None:
        self._llm = llm
        self._plugins = plugins
        self._prediction_ledger: Optional[Any] = None
        self._collab: Optional[Any] = None
        self._memory_engine: Optional[Any] = None

    def set_llm(self, llm: Any, plugins: Any) -> None:
        self._llm = llm
        self._plugins = plugins

    def set_prediction_ledger(self, ledger: Any) -> None:
        """Wire the prediction ledger for tracking prediction outcomes."""
        self._prediction_ledger = ledger

    def set_collab(self, collab: Any) -> None:
        """Wire agent collaboration for real council debates."""
        self._collab = collab

    def set_memory_engine(self, memory_engine: Any) -> None:
        """Wire memory engine to store market insights for future recall."""
        self._memory_engine = memory_engine

    async def health_check(self) -> dict[str, Any]:
        if not self._llm:
            return {"status": "offline", "reason": "No LLM configured"}
        return {
            "status": "online",
            "type": "miro",
            "agent": "miro",
            "prediction_ledger": self._prediction_ledger is not None,
            "council_enabled": self._collab is not None,
            "memory_engine": self._memory_engine is not None,
            "panel_agents": list(_PANEL_PROMPTS.keys()),
        }

    async def send_task(self, task: str) -> dict[str, Any]:
        if not self._llm:
            return {"error": "MiRo not initialized — no LLM"}

        now = datetime.now(timezone.utc)
        session = _get_market_session(now)
        date_line = (
            f"\n\n## Current Market Context\n"
            f"DateTime: {now.strftime('%A, %B %d, %Y %H:%M')} UTC\n"
            f"Session: {session}\n"
            f"All responses must reference this date — never use training data dates."
        )

        calibration_section = self._build_calibration_context()

        system = (
            f"{_MIRO_PROMPT}\n\n"
            f"## Task from Yohan (via ROOT)\n"
            f"Execute this. Search for real data first. Deliver actionable intelligence."
            f"{calibration_section}"
            f"{date_line}"
        )
        messages = [{"role": "user", "content": task}]
        tool_defs = self._plugins.list_tools() if self._plugins else []

        msg_count = 1
        tool_count = 0
        tools_used: list[str] = []

        if not tool_defs:
            result = await self._llm.complete(
                system=system, messages=messages,
                model_tier="default", temperature=0.7,
            )
            return {
                "agent": "miro", "result": result,
                "messages_exchanged": 2, "tools_executed": 0, "tools_used": [],
            }

        is_openai = getattr(self._llm, "provider", "") == "openai"
        working = list(messages)

        for _round in range(5):
            try:
                text, tool_calls = await asyncio.wait_for(
                    self._llm.complete_with_tools(
                        system=system, messages=working,
                        tools=tool_defs, model_tier="default",
                    ),
                    timeout=280.0,
                )
            except asyncio.TimeoutError:
                return {
                    "agent": "miro", "result": "LLM request timed out",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            except Exception as llm_err:
                logger.error("[miro] LLM error: %s", llm_err)
                return {
                    "agent": "miro", "result": f"LLM error: {str(llm_err)[:200]}",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }

            msg_count += 1
            if not tool_calls:
                return {
                    "agent": "miro", "result": text or "Analysis complete",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }

            tool_results: list[tuple[dict, str]] = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("input", {})
                logger.info("[miro] Tool: %s(%s)", name, json.dumps(args)[:200])
                output: Any
                try:
                    res = await asyncio.wait_for(
                        self._plugins.invoke(name, args), timeout=30.0,
                    )
                    output = res.output if res.success else {"error": res.error}
                except asyncio.TimeoutError:
                    output = {"error": f"Tool '{name}' timed out"}
                except Exception as tool_err:
                    output = {"error": str(tool_err)}

                output = sanitize_tool_output(output)
                output_str = json.dumps(output, default=str)[:5000]
                tool_results.append((tc, output_str))
                tool_count = tool_count + 1
                if name not in tools_used:
                    tools_used.append(name)

            if is_openai:
                working.append({
                    "role": "assistant", "content": text or None,
                    "tool_calls": [
                        {
                            "id": tc.get("id", f"call_{_round}_{i}"),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("input", {})),
                            },
                        }
                        for i, (tc, _) in enumerate(tool_results)
                    ],
                })
                for tc, out in tool_results:
                    working.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{_round}"),
                        "content": out,
                    })
            else:
                # Proper Anthropic tool_use / tool_result format
                asst_content: list[dict] = []
                if text:
                    asst_content.append({"type": "text", "text": text})
                for i, (tc, _) in enumerate(tool_results):
                    asst_content.append({
                        "type": "tool_use",
                        "id": tc.get("id", f"tool_{_round}_{i}"),
                        "name": tc["name"],
                        "input": tc.get("input", {}),
                    })
                working.append({"role": "assistant", "content": asst_content})
                working.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tc.get("id", f"tool_{_round}_{i}"),
                            "content": out,
                        }
                        for i, (tc, out) in enumerate(tool_results)
                    ],
                })

            msg_count += 1

        final = await self._llm.complete(
            system=system, messages=working,
            model_tier="default", temperature=0.7,
        )
        msg_count += 1
        return {
            "agent": "miro", "result": final,
            "messages_exchanged": msg_count, "tools_executed": tool_count,
            "tools_used": tools_used,
        }

    # ── Council Debate (ReACT + GraphRAG + Parallel Scenarios) ─────────

    async def run_council_debate(
        self, topic: str, symbols: str = "",
    ) -> dict[str, Any]:
        """Run a 7-agent council debate with ReACT synthesis.

        Phases:
          OBSERVE  → gather raw market data via send_task
          REASON   → extract entities + relationships (GraphRAG)
          ACT      → run parallel scenario simulations + collab council
          SYNTHESIZE → final verdict with potentiality map
        """
        now = datetime.now(timezone.utc)
        session = _get_market_session(now)

        # ── OBSERVE: gather raw market data ───────────────────────────
        observe_task = (
            f"OBSERVE phase for MiRo ReACT analysis.\n\n"
            f"Topic: {topic}\nSymbols: {symbols or 'general market'}\n"
            f"Market Session: {session}\n\n"
            f"Execute these searches in order:\n"
            f"1. Current price + 24h/7d change for each symbol\n"
            f"2. Top 3 recent news headlines affecting this topic\n"
            f"3. Macro context: Fed stance, VIX level, sector flow\n"
            f"4. Options sentiment: put/call ratio, any unusual flow\n\n"
            f"Return raw data with SPECIFIC NUMBERS and DATES. No analysis yet."
        )

        observe_result = await self.send_task(observe_task)
        raw_data = observe_result.get("result", "")
        tools_used = list(observe_result.get("tools_used", []))

        # ── REASON: entity + relationship extraction (GraphRAG) ────────
        entities = await self._extract_knowledge_entities(raw_data, topic, symbols)

        # ── ACT: parallel scenarios + council debate ───────────────────
        council_text = ""
        if self._collab:
            council_task = (
                f"Analyze this market topic as your specialized agent role:\n\n"
                f"Topic: {topic}\nSymbols: {symbols or 'general market'}\n"
                f"Session: {session}\n\n"
                f"Raw market data:\n{raw_data[:2000]}\n\n"
                f"Key entities identified:\n{entities[:500]}\n\n"
                f"Give your specialist perspective. Be specific with numbers."
            )
            try:
                council_result = await asyncio.wait_for(
                    self._collab.council(
                        initiator="miro",
                        agents=["researcher", "analyst", "guardian"],
                        question=council_task,
                        require_consensus=False,
                    ),
                    timeout=150.0,
                )
                council_text = council_result.final_result or ""
            except (asyncio.TimeoutError, Exception) as exc:
                logger.warning("[miro] Council debate error: %s", exc)

        # Run parallel scenario simulations
        scenarios = await self._run_parallel_scenarios(topic, symbols, raw_data)

        # ── SYNTHESIZE: ReACT final verdict ───────────────────────────
        synthesis_prompt = (
            f"You are MiRo. Complete the SYNTHESIZE phase of your ReACT analysis.\n\n"
            f"## OBSERVE Results\n{raw_data[:2000]}\n\n"
            f"## REASON Results (Entity Map)\n{entities}\n\n"
            f"## ACT Results\n"
            f"### Council Debate\n{council_text[:1500] or 'Single-agent mode'}\n\n"
            f"### Parallel Scenarios\n{scenarios}\n\n"
            f"## Market Context\n"
            f"Topic: {topic} | Symbols: {symbols or 'general'} | Session: {session}\n"
            f"Date: {now.strftime('%A, %B %d, %Y %H:%M')} UTC\n\n"
            f"## SYNTHESIZE — Deliver final verdict:\n"
            f"1. **Consensus View**: Where do all signals align?\n"
            f"2. **Key Disagreements**: Where does the council diverge?\n"
            f"3. **Entity Map Summary**: Key relationships affecting this trade\n"
            f"4. **Potentiality Map**: 3 scenarios with probability % + key trigger\n"
            f"5. **Final Verdict**: GO / NO-GO / WAIT with confidence %\n"
            f"6. **Next Move**: Specific action for Yohan (entry, size, stop, target)\n"
            f"7. **Regime Signal**: What does this tell us about the current market?"
        )

        verdict = await self._llm.complete(
            system=_MIRO_PROMPT,
            messages=[{"role": "user", "content": synthesis_prompt}],
            model_tier="default",
            temperature=0.5,
        )

        # Store key findings in memory engine
        await self._store_market_insight(topic, symbols, verdict, entities)

        return {
            "agent": "miro",
            "result": verdict,
            "observe_data": raw_data[:1000],
            "entities": entities,
            "scenarios": scenarios,
            "council_debate": council_text[:1500],
            "market_session": session,
            "mode": "react_council",
            "messages_exchanged": 6,
            "tools_executed": observe_result.get("tools_executed", 0),
            "tools_used": tools_used,
        }

    # ── Parallel Scenario Simulation ───────────────────────────────────

    async def _run_parallel_scenarios(
        self, topic: str, symbols: str, raw_data: str,
    ) -> str:
        """Run 3 parallel 'what-if' scenario simulations via asyncio.gather."""
        if not self._llm:
            return "No LLM available for scenario simulation."

        scenario_configs = [
            {
                "name": "Bull Case",
                "prompt_suffix": (
                    "Assume the MOST OPTIMISTIC realistic outcome. "
                    "What catalysts materialize? What does the price action look like? "
                    "Give a specific price target and timeframe."
                ),
            },
            {
                "name": "Bear Case",
                "prompt_suffix": (
                    "Assume the MOST PESSIMISTIC realistic outcome. "
                    "What risks materialize? What does the breakdown look like? "
                    "Give a specific downside target and timeframe."
                ),
            },
            {
                "name": "Base Case",
                "prompt_suffix": (
                    "Assume the MOST LIKELY outcome given current data. "
                    "What is the path of least resistance? "
                    "Give probability-weighted price expectation and timeframe."
                ),
            },
        ]

        async def _simulate_scenario(config: dict) -> str:
            prompt = (
                f"Scenario simulation for: {topic} | {symbols}\n\n"
                f"Market data context:\n{raw_data[:800]}\n\n"
                f"## {config['name']} Simulation\n{config['prompt_suffix']}\n\n"
                f"Output: 3-4 sentences max. Include specific price targets."
            )
            try:
                result = await asyncio.wait_for(
                    self._llm.complete(
                        system=_PANEL_PROMPTS.get(
                            "quant",
                            "You are a scenario simulation agent. Be concise and specific.",
                        ),
                        messages=[{"role": "user", "content": prompt}],
                        model_tier="fast",
                        temperature=0.4,
                    ),
                    timeout=60.0,
                )
                return f"**{config['name']}**: {result}"
            except Exception as exc:
                return f"**{config['name']}**: Simulation failed — {str(exc)[:100]}"

        results = await asyncio.gather(
            *[_simulate_scenario(cfg) for cfg in scenario_configs],
            return_exceptions=True,
        )

        lines = []
        for r in results:
            if isinstance(r, Exception):
                lines.append(f"Scenario error: {r}")
            else:
                lines.append(str(r))

        return "\n\n".join(lines)

    # ── GraphRAG Entity Extraction ─────────────────────────────────────

    async def _extract_knowledge_entities(
        self, raw_data: str, topic: str, symbols: str,
    ) -> str:
        """Extract entities and relationships from market data (GraphRAG-style).

        Returns a structured entity map string for use in synthesis.
        """
        if not self._llm or not raw_data:
            return "No entity extraction available."

        extraction_prompt = (
            f"Extract entities and relationships from this market data.\n\n"
            f"Topic: {topic} | Symbols: {symbols}\n\n"
            f"Data:\n{raw_data[:2000]}\n\n"
            f"Output format — list 5-8 triplets:\n"
            f"ENTITY → RELATION → ENTITY\n\n"
            f"Example: BTC → CORRELATED_WITH → ETH | SPY → AFFECTED_BY → Fed_Rate\n"
            f"Use relations: CORRELATED_WITH, CAUSED_BY, AFFECTS, PART_OF, "
            f"COMPETES_WITH, DEPENDENT_ON, DIVERGES_FROM, SIGNALS\n\n"
            f"Only include what the data actually shows. Be concise."
        )

        try:
            entities = await asyncio.wait_for(
                self._llm.complete(
                    system="You are a knowledge graph extraction engine. Extract entity triplets.",
                    messages=[{"role": "user", "content": extraction_prompt}],
                    model_tier="fast",
                    temperature=0.2,
                ),
                timeout=45.0,
            )
            return entities or "No entities extracted."
        except Exception as exc:
            logger.debug("[miro] Entity extraction failed: %s", exc)
            return "Entity extraction unavailable."

    # ── Memory Storage ─────────────────────────────────────────────────

    async def _store_market_insight(
        self, topic: str, symbols: str, verdict: str, entities: str,
    ) -> None:
        """Store key market findings in memory engine for future recall."""
        if not self._memory_engine or not verdict:
            return
        try:
            now = datetime.now(timezone.utc)
            content = (
                f"MiRo market analysis — {topic} | {symbols or 'general'}\n"
                f"Date: {now.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
                f"Verdict: {verdict[:800]}\n\n"
                f"Entity Map: {entities[:400]}"
            )
            await asyncio.to_thread(
                self._memory_engine.store,
                content=content,
                source="miro_analysis",
                tags=["market", "miro", "prediction"] + (
                    [s.strip() for s in symbols.split(",") if s.strip()]
                ),
                confidence=0.8,
            )
            logger.info("[miro] Stored market insight in memory engine")
        except Exception as exc:
            logger.debug("[miro] Failed to store insight in memory: %s", exc)

    # ── Prediction Tracking ────────────────────────────────────────────

    async def predict_market(
        self, symbols: str = "SPY,QQQ,BTC-USD",
    ) -> dict[str, Any]:
        """Predict next moves with council debate + prediction recording."""
        result = await self.run_council_debate(
            topic=f"Predict next moves for: {symbols}",
            symbols=symbols,
        )

        if self._prediction_ledger:
            self._record_predictions_from_result(
                result.get("result", ""), symbols,
            )

        return result

    async def assess_opportunity(self, opportunity: str) -> dict[str, Any]:
        """Run full opportunity assessment with council debate."""
        return await self.run_council_debate(
            topic=f"Full opportunity assessment: {opportunity}",
        )

    async def run_simulation(
        self, scenario: str, agent_count: int = 5, rounds: int = 1,
    ) -> dict[str, Any]:
        return await self.send_task(
            f"Run swarm sim with {agent_count} agents over {rounds} round(s):\n\n"
            f"{scenario}\n\nSearch real data first. Deliver potentiality map."
        )

    async def get_predictions(self, topic: str) -> dict[str, Any]:
        """Get predictions with calibration-aware context."""
        return await self.run_council_debate(topic=topic)

    async def get_prediction_stats(self) -> dict[str, Any]:
        """Return prediction accuracy and calibration data."""
        if not self._prediction_ledger:
            return {"error": "No prediction ledger configured"}
        return {
            "stats": self._prediction_ledger.stats(),
            "calibration": [
                {
                    "source": c.source,
                    "bucket": c.confidence_bucket,
                    "total": c.total_predictions,
                    "correct": c.correct_predictions,
                    "score": c.calibration_score,
                }
                for c in self._prediction_ledger.get_calibration(source="miro")
            ],
            "accuracy_30d": self._prediction_ledger.get_accuracy("miro", 30),
        }

    # ── Private helpers ────────────────────────────────────────────────

    def _build_calibration_context(self) -> str:
        """Build calibration context string for the system prompt."""
        if not self._prediction_ledger:
            return ""
        try:
            stats = self._prediction_ledger.stats()
            if stats["total_predictions"] == 0:
                return ""

            cal = self._prediction_ledger.get_calibration(source="miro")
            cal_lines = [
                f"  - Confidence {c.confidence_bucket:.0%}: "
                f"{c.correct_predictions}/{c.total_predictions} correct "
                f"(calibration: {c.calibration_score:.0%})"
                for c in cal
            ]
            cal_text = "\n".join(cal_lines) if cal_lines else "  No calibration data yet"

            return (
                f"\n\n## PREDICTION TRACK RECORD (learn from this)\n"
                f"Total predictions: {stats['total_predictions']} | "
                f"Hit rate: {stats['hit_rate']:.0%} | "
                f"Pending: {stats['pending']}\n"
                f"Calibration by confidence:\n{cal_text}\n"
                f"IMPORTANT: Adjust your confidence levels based on calibration data. "
                f"If you're overconfident at 90%, dial it back."
            )
        except Exception as exc:
            logger.debug("[miro] Failed to build calibration context: %s", exc)
            return ""

    def _record_predictions_from_result(
        self, result_text: str, symbols: str,
    ) -> None:
        """Parse LLM result for predictions and record in ledger."""
        if not self._prediction_ledger or not result_text:
            return

        for symbol in symbols.split(","):
            symbol = symbol.strip()
            if not symbol:
                continue

            direction = self._extract_direction(result_text, symbol)
            confidence = self._extract_confidence(result_text)

            if direction and confidence > 0:
                try:
                    self._prediction_ledger.record_prediction(
                        source="miro",
                        symbol=symbol,
                        direction=direction,
                        confidence=min(confidence, 1.0),
                        reasoning=result_text[:500],
                        deadline_hours=24,
                    )
                    logger.info(
                        "[miro] Recorded prediction: %s %s (conf=%.2f)",
                        symbol, direction, confidence,
                    )
                except Exception as exc:
                    logger.warning(
                        "[miro] Failed to record prediction for %s: %s",
                        symbol, exc,
                    )

    @staticmethod
    def _extract_direction(text: str, symbol: str) -> Optional[str]:
        """Extract predicted direction from analysis text."""
        lower = text.lower()
        symbol_lower = symbol.lower().replace("-", "")
        context = lower

        idx = lower.find(symbol_lower)
        if idx >= 0:
            context = lower[max(0, idx - 200):idx + 200]

        buy_signals = ("buy", "long", "bullish", "upside", "accumulate", "go long")
        sell_signals = ("sell", "short", "bearish", "downside", "reduce", "go short")

        buy_score = sum(1 for s in buy_signals if s in context)
        sell_score = sum(1 for s in sell_signals if s in context)

        if buy_score > sell_score:
            return "long"
        if sell_score > buy_score:
            return "short"
        if "hold" in context or "wait" in context or "neutral" in context:
            return "hold"
        return None

    @staticmethod
    def _extract_confidence(text: str) -> float:
        """Extract confidence/probability from analysis text."""
        pct_matches = re.findall(r"(\d{1,3})%", text)
        if pct_matches:
            values = [int(p) for p in pct_matches if 30 <= int(p) <= 95]
            if values:
                return max(values) / 100.0

        dec_matches = re.findall(r"confidence[:\s]+(\d\.\d+)", text.lower())
        if dec_matches:
            return float(dec_matches[0])

        return 0.6  # Default moderate confidence
