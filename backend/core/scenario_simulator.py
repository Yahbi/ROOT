"""
Scenario Simulator — What-If Lab for MiRo's potentiality engine.

Runs N parallel LLM-powered agents using MiRo's panel prompts (Bull, Bear,
Quant, Contrarian, Macro, Sentiment, Industry) to simulate hypothetical
market scenarios. Results are stored in state.db via StateStore.

Each simulation produces a potentiality map with Bull/Base/Bear scenarios
and probability weights, synthesized across 1-3 rounds.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.scenario_simulator")

# Panel prompts imported from MiRo connector
_SCENARIO_PANELS: dict[str, str] = {
    "bull": (
        "You are the BULL analyst. Focus on growth catalysts, momentum signals, "
        "upside targets, positive earnings surprises, institutional buying. "
        "Argue FOR the opportunity with specific price targets and timeframes."
    ),
    "bear": (
        "You are the BEAR analyst. Focus on risk factors, resistance levels, "
        "downside scenarios, negative catalysts, liquidity risks. "
        "Argue AGAINST with specific downside targets."
    ),
    "quant": (
        "You are the QUANT analyst. Pure numbers only — probabilities, expected value, "
        "Sharpe ratio, max drawdown, win rate, risk/reward ratios. "
        "State confidence intervals. No opinions."
    ),
    "contrarian": (
        "You are the CONTRARIAN analyst. Find what the consensus is MISSING. "
        "Challenge the dominant narrative. Look for crowded trades reversing, "
        "hidden asymmetries, non-obvious second-order effects."
    ),
    "macro": (
        "You are the MACRO analyst. Focus on Fed policy, interest rates, "
        "geopolitics, dollar dynamics, sector rotation, global capital flows, "
        "yield curve, commodity prices."
    ),
    "sentiment": (
        "You are the SENTIMENT analyst. Focus on options flow, social media buzz, "
        "retail vs institutional divergence, fear/greed indicators, "
        "short interest, insider transactions."
    ),
    "industry": (
        "You are the INDUSTRY SPECIALIST. Focus on sector-specific dynamics, "
        "competitive moat, regulatory risk, supply chain factors, "
        "industry KPIs, peer comparison, market share trends."
    ),
}


@dataclass(frozen=True)
class ScenarioConfig:
    """Immutable configuration for a what-if scenario simulation."""

    hypothesis: str
    symbols: str = ""
    time_horizon: str = "1 week"
    agent_count: int = 5
    synthesis_rounds: int = 1


@dataclass(frozen=True)
class ScenarioResult:
    """Immutable result of a scenario simulation."""

    id: str
    config: ScenarioConfig
    agent_perspectives: dict[str, str]
    bull_scenario: str
    base_scenario: str
    bear_scenario: str
    bull_probability: float
    base_probability: float
    bear_probability: float
    synthesis: str
    created_at: str


class ScenarioSimulator:
    """Runs parallel what-if scenario simulations using MiRo's panel agents."""

    def __init__(self, state_store: Any = None) -> None:
        self._state_store = state_store
        self._llm: Any = None

    def set_llm(self, llm: Any) -> None:
        self._llm = llm

    async def simulate(self, config: ScenarioConfig) -> ScenarioResult:
        """Run a full scenario simulation with parallel agents + synthesis."""
        if not self._llm:
            raise RuntimeError("ScenarioSimulator has no LLM configured")

        scenario_id = f"scenario_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Select agents based on count (up to 7)
        panel_keys = list(_SCENARIO_PANELS.keys())[:config.agent_count]

        # ── Phase 1: Parallel agent perspectives ──────────────────
        perspectives = await self._gather_perspectives(config, panel_keys)

        # ── Phase 2: Synthesis rounds ─────────────────────────────
        synthesis = ""
        for round_num in range(config.synthesis_rounds):
            synthesis = await self._synthesize(config, perspectives, round_num, synthesis)

        # ── Phase 3: Extract potentiality map ─────────────────────
        potentiality = await self._extract_potentiality(config, synthesis, perspectives)

        result = ScenarioResult(
            id=scenario_id,
            config=config,
            agent_perspectives=perspectives,
            bull_scenario=potentiality.get("bull_scenario", ""),
            base_scenario=potentiality.get("base_scenario", ""),
            bear_scenario=potentiality.get("bear_scenario", ""),
            bull_probability=potentiality.get("bull_probability", 0.3),
            base_probability=potentiality.get("base_probability", 0.4),
            bear_probability=potentiality.get("bear_probability", 0.3),
            synthesis=synthesis,
            created_at=now.isoformat(),
        )

        # Store in state.db
        self._persist_result(result)

        return result

    async def _gather_perspectives(
        self, config: ScenarioConfig, panel_keys: list[str],
    ) -> dict[str, str]:
        """Run panel agents in parallel to gather diverse perspectives."""

        async def _run_agent(panel_key: str) -> tuple[str, str]:
            prompt = (
                f"## What-If Scenario Analysis\n\n"
                f"**Hypothesis**: {config.hypothesis}\n"
                f"**Symbols**: {config.symbols or 'general market'}\n"
                f"**Time Horizon**: {config.time_horizon}\n\n"
                f"Analyze this scenario from your specialist perspective. "
                f"Be specific with numbers, price targets, and probabilities. "
                f"Keep your response to 4-6 sentences."
            )
            try:
                result = await asyncio.wait_for(
                    self._llm.complete(
                        system=_SCENARIO_PANELS[panel_key],
                        messages=[{"role": "user", "content": prompt}],
                        model_tier="fast",
                        temperature=0.5,
                    ),
                    timeout=60.0,
                )
                return (panel_key, result or "No response")
            except Exception as exc:
                logger.warning("Scenario agent %s failed: %s", panel_key, exc)
                return (panel_key, f"Agent unavailable: {str(exc)[:100]}")

        results = await asyncio.gather(
            *[_run_agent(k) for k in panel_keys],
            return_exceptions=True,
        )

        perspectives: dict[str, str] = {}
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Scenario agent error: %s", r)
            else:
                key, text = r
                perspectives[key] = text

        return perspectives

    async def _synthesize(
        self,
        config: ScenarioConfig,
        perspectives: dict[str, str],
        round_num: int,
        prior_synthesis: str,
    ) -> str:
        """Synthesize agent perspectives into a unified analysis."""
        perspective_text = "\n\n".join(
            f"**{k.upper()} Agent**: {v}" for k, v in perspectives.items()
        )

        prior_context = ""
        if prior_synthesis:
            prior_context = (
                f"\n\n## Prior Synthesis (Round {round_num})\n{prior_synthesis}\n\n"
                f"Build on this analysis. Identify any new insights or contradictions."
            )

        prompt = (
            f"## Scenario Synthesis — Round {round_num + 1}\n\n"
            f"**Hypothesis**: {config.hypothesis}\n"
            f"**Symbols**: {config.symbols or 'general market'}\n"
            f"**Time Horizon**: {config.time_horizon}\n\n"
            f"## Agent Perspectives\n{perspective_text}\n"
            f"{prior_context}\n\n"
            f"## Instructions\n"
            f"1. Identify where agents AGREE (consensus signals)\n"
            f"2. Identify where agents DISAGREE (key uncertainties)\n"
            f"3. Weigh the evidence for each scenario\n"
            f"4. Produce a VERDICT: most likely outcome with confidence %\n"
            f"5. Identify the single most important variable to watch"
        )

        try:
            result = await asyncio.wait_for(
                self._llm.complete(
                    system=(
                        "You are MiRo's synthesis engine. Merge multiple analyst "
                        "perspectives into a unified verdict. Be specific and actionable."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                    model_tier="default",
                    temperature=0.4,
                ),
                timeout=90.0,
            )
            return result or "Synthesis unavailable"
        except Exception as exc:
            logger.error("Synthesis failed: %s", exc)
            return f"Synthesis failed: {str(exc)[:200]}"

    async def _extract_potentiality(
        self,
        config: ScenarioConfig,
        synthesis: str,
        perspectives: dict[str, str],
    ) -> dict[str, Any]:
        """Extract structured potentiality map from synthesis."""
        prompt = (
            f"Based on this scenario analysis, produce a structured potentiality map.\n\n"
            f"Hypothesis: {config.hypothesis}\n"
            f"Synthesis: {synthesis[:1500]}\n\n"
            f"Return ONLY valid JSON with this exact structure:\n"
            f'{{"bull_scenario": "2-3 sentence bull case",'
            f'"base_scenario": "2-3 sentence base case",'
            f'"bear_scenario": "2-3 sentence bear case",'
            f'"bull_probability": 0.XX,'
            f'"base_probability": 0.XX,'
            f'"bear_probability": 0.XX}}\n\n'
            f"Probabilities MUST sum to 1.0. No markdown, no explanation — JSON only."
        )

        try:
            result = await asyncio.wait_for(
                self._llm.complete(
                    system="You output valid JSON only. No markdown fences, no text.",
                    messages=[{"role": "user", "content": prompt}],
                    model_tier="fast",
                    temperature=0.1,
                ),
                timeout=45.0,
            )
            # Parse JSON from result
            cleaned = (result or "{}").strip()
            # Remove markdown fences if present
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            # Normalize probabilities to sum to 1.0
            total = (
                data.get("bull_probability", 0.3)
                + data.get("base_probability", 0.4)
                + data.get("bear_probability", 0.3)
            )
            if total > 0:
                data["bull_probability"] = round(data.get("bull_probability", 0.3) / total, 2)
                data["base_probability"] = round(data.get("base_probability", 0.4) / total, 2)
                data["bear_probability"] = round(1.0 - data["bull_probability"] - data["base_probability"], 2)

            return data
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Potentiality extraction failed: %s", exc)
            return {
                "bull_scenario": "Extraction failed — see synthesis text",
                "base_scenario": "Extraction failed — see synthesis text",
                "bear_scenario": "Extraction failed — see synthesis text",
                "bull_probability": 0.30,
                "base_probability": 0.40,
                "bear_probability": 0.30,
            }

    def _persist_result(self, result: ScenarioResult) -> None:
        """Store scenario result in StateStore for retrieval."""
        if not self._state_store:
            return
        try:
            data = {
                "id": result.id,
                "hypothesis": result.config.hypothesis,
                "symbols": result.config.symbols,
                "time_horizon": result.config.time_horizon,
                "agent_count": result.config.agent_count,
                "synthesis_rounds": result.config.synthesis_rounds,
                "agent_perspectives": result.agent_perspectives,
                "bull_scenario": result.bull_scenario,
                "base_scenario": result.base_scenario,
                "bear_scenario": result.bear_scenario,
                "bull_probability": result.bull_probability,
                "base_probability": result.base_probability,
                "bear_probability": result.bear_probability,
                "synthesis": result.synthesis,
                "created_at": result.created_at,
            }
            self._state_store.set(f"scenario:{result.id}", json.dumps(data))
            # Maintain index
            index = self._get_index()
            index.insert(0, result.id)
            index = index[:100]  # Keep last 100
            self._state_store.set("scenario:_index", json.dumps(index))
            logger.info("Stored scenario %s", result.id)
        except Exception as exc:
            logger.warning("Failed to persist scenario: %s", exc)

    def _get_index(self) -> list[str]:
        """Get list of scenario IDs from state store."""
        if not self._state_store:
            return []
        try:
            raw = self._state_store.get("scenario:_index")
            return json.loads(raw) if raw else []
        except Exception:
            return []

    def get_scenario(self, scenario_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a stored scenario by ID."""
        if not self._state_store:
            return None
        try:
            raw = self._state_store.get(f"scenario:{scenario_id}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def list_scenarios(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent scenarios (summaries only)."""
        index = self._get_index()[:limit]
        results: list[dict[str, Any]] = []
        for sid in index:
            data = self.get_scenario(sid)
            if data:
                results.append({
                    "id": data.get("id", sid),
                    "hypothesis": data.get("hypothesis", ""),
                    "symbols": data.get("symbols", ""),
                    "bull_probability": data.get("bull_probability", 0),
                    "base_probability": data.get("base_probability", 0),
                    "bear_probability": data.get("bear_probability", 0),
                    "created_at": data.get("created_at", ""),
                })
        return results
