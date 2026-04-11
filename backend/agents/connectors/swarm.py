"""
Trading Swarm Connector — Autonomous trading strategy research and analysis.

Searches for strategies, analyzes market conditions, runs calculations,
and produces actionable trading intelligence. Uses real market data
via web search and financial tools.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from datetime import datetime, timezone
from typing import Any, Optional

from backend.agents.connectors import sanitize_tool_output

logger = logging.getLogger("root.connectors.swarm")


def _date_context() -> str:
    now = datetime.now(timezone.utc)
    return f"\n\n## Current Date\nToday is {now.strftime('%A, %B %d, %Y')} (UTC). All responses must use this date — never guess or use training data dates."

_SWARM_PROMPT = (
    "You are the Trading Swarm — ROOT's autonomous trading intelligence engine.\n"
    "You research, analyze, and evaluate trading strategies for Yohan.\n\n"
    "## Core Mission\n"
    "Find real, actionable trading opportunities using data-driven analysis.\n\n"
    "## Research Process\n"
    "1. **Market Scan**: Use web_search to find current market conditions, news, trends\n"
    "2. **Strategy Research**: Search for proven strategies relevant to current conditions\n"
    "3. **Quantitative Analysis**: Use calculate for math, roi_calculator for returns,\n"
    "   compound_interest for growth projections, revenue_projector for income modeling\n"
    "4. **Risk Assessment**: Use pros_cons_matrix and opportunity_scorer to evaluate\n\n"
    "## Output Format\n"
    "For strategy research:\n"
    "- **Market Context**: What's happening right now (with real data)\n"
    "- **Strategy**: Clear entry/exit rules\n"
    "- **Expected Returns**: Projected ROI with timeframe\n"
    "- **Risk/Reward**: Quantified risk metrics\n"
    "- **Confidence**: Your confidence level (Low/Medium/High) with reasoning\n\n"
    "For market analysis:\n"
    "- **Current Levels**: Key prices, indices, indicators\n"
    "- **Trend**: Direction + strength\n"
    "- **Key Levels**: Support, resistance, moving averages\n"
    "- **Catalysts**: Upcoming events that could move markets\n\n"
    "## CRITICAL RULES\n"
    "- Your training data is STALE. ALWAYS use web_search FIRST to get TODAY's data.\n"
    "- NEVER give market analysis without searching for current prices and news first.\n"
    "- Run at least 3 web_search queries before forming any market opinion.\n"
    "- ALWAYS include specific numbers WITH DATES (prices, percentages, dates).\n"
    "- NEVER recommend trades without quantified risk/reward from REAL data.\n"
    "- Clearly separate FACTS (from live data) from OPINIONS (your analysis).\n"
    "- If a tool call fails, try a different query — don't give up."
)


class SwarmConnector:
    """LLM-powered trading strategy research and market analysis agent."""

    def __init__(self, llm: Any = None, plugins: Any = None) -> None:
        self._llm = llm
        self._plugins = plugins

    def set_llm(self, llm: Any, plugins: Any) -> None:
        """Late-bind LLM and plugins (set after startup)."""
        self._llm = llm
        self._plugins = plugins

    async def health_check(self) -> dict[str, Any]:
        if not self._llm:
            return {"status": "offline", "reason": "No LLM configured"}
        return {"status": "online", "type": "swarm", "agent": "swarm"}

    async def send_task(self, task: str) -> dict[str, Any]:
        """Execute a trading research or analysis task."""
        if not self._llm:
            return {"error": "Trading Swarm not initialized — no LLM"}

        system = (
            f"{_SWARM_PROMPT}\n\n"
            f"## Task from Yohan (via ROOT)\n"
            f"Research this thoroughly. Use tools to get REAL data. Return actionable intel."
            f"{_date_context()}"
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
                "agent": "swarm", "result": result,
                "messages_exchanged": 2, "tools_executed": 0, "tools_used": [],
            }

        # Tool-use loop — 5 rounds (deep research)
        working = list(messages)
        _loop_start = _time.monotonic()
        MAX_TOTAL_SECONDS = 300.0  # 5 minutes max total
        for _round in range(5):
            if _time.monotonic() - _loop_start > MAX_TOTAL_SECONDS:
                logger.warning("[swarm] Total time exceeded %.0fs — stopping tool loop", MAX_TOTAL_SECONDS)
                break
            try:
                text, tool_calls = await asyncio.wait_for(
                    self._llm.complete_with_tools(
                        system=system, messages=working,
                        tools=tool_defs, model_tier="default",
                    ),
                    timeout=180.0,
                )
            except asyncio.TimeoutError:
                # If we already got tool results, try a final fast completion
                if tool_count > 0:
                    logger.warning("[swarm] Round %d timed out after %d tools — attempting final completion", _round, tool_count)
                    try:
                        final = await asyncio.wait_for(
                            self._llm.complete(system=system, messages=working, model_tier="fast", temperature=0.5),
                            timeout=60.0,
                        )
                        return {"agent": "swarm", "result": final, "messages_exchanged": msg_count + 1,
                                "tools_executed": tool_count, "tools_used": tools_used}
                    except Exception:
                        logger.debug("[swarm] Final fast completion after timeout also failed", exc_info=True)
                return {
                    "agent": "swarm", "result": "Trading Swarm analysis timed out — LLM provider may be slow. Try again shortly.",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            except Exception as llm_err:
                logger.error("[swarm] LLM error: %s", llm_err)
                return {
                    "agent": "swarm", "result": f"Trading Swarm error: {str(llm_err)[:200]}. Try again or check provider status.",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }
            msg_count += 1
            if not tool_calls:
                return {
                    "agent": "swarm", "result": text or "Analysis complete (no output)",
                    "messages_exchanged": msg_count, "tools_executed": tool_count,
                    "tools_used": tools_used,
                }

            results_parts = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("input", {})
                logger.info("[swarm] Tool: %s(%s)", name, json.dumps(args)[:200])
                try:
                    result = await asyncio.wait_for(self._plugins.invoke(name, args), timeout=30.0)
                except asyncio.TimeoutError:
                    result = type('R', (), {'success': False, 'output': None, 'error': f"Tool '{name}' timed out"})()
                except Exception as tool_err:
                    result = type('R', (), {'success': False, 'output': None, 'error': str(tool_err)})()
                output = result.output if result.success else {"error": result.error}
                output = sanitize_tool_output(output)
                output_str = json.dumps(output, default=str)[:5000]
                results_parts.append(f"[{name}] → {output_str}")
                tool_count += 1
                if name not in tools_used:
                    tools_used.append(name)

            if text:
                working.append({"role": "assistant", "content": text})
            working.append({
                "role": "user",
                "content": "[TOOL RESULTS]\n" + "\n".join(results_parts),
            })
            msg_count += 1

        final = await self._llm.complete(
            system=system, messages=working,
            model_tier="default", temperature=0.5,
        )
        msg_count += 1
        return {
            "agent": "swarm", "result": final,
            "messages_exchanged": msg_count, "tools_executed": tool_count,
            "tools_used": tools_used,
        }

    async def get_strategies(self, limit: int = 5) -> dict[str, Any]:
        """Search for current top trading strategies."""
        return await self.send_task(
            f"Search for the top {limit} trading strategies that are working "
            f"right now in current market conditions. Include specific entry/exit criteria."
        )

    async def get_backtests(self, strategy: str = "momentum") -> dict[str, Any]:
        """Analyze a strategy with quantitative metrics."""
        return await self.send_task(
            f"Analyze the '{strategy}' trading strategy. Search for recent performance data, "
            f"calculate expected returns using roi_calculator, and score it with opportunity_scorer."
        )

    async def market_analysis(self, symbols: str = "SPY,QQQ,BTC-USD") -> dict[str, Any]:
        """Get current market analysis for given symbols."""
        return await self.send_task(
            f"Get current market analysis for: {symbols}. "
            f"Search for latest prices, trends, key levels, and upcoming catalysts."
        )
