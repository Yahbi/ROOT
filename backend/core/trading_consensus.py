"""
Trading Consensus — structured bull/bear debate for investment decisions.

Inspired by TradingAgents' multi-agent debate architecture:
1. Parallel analyst dispatch (technical, fundamental, sentiment, news)
2. Bull/bear adversarial debate (2-3 rounds)
3. Judge synthesis into final signal
4. Risk assessment from 3 perspectives (aggressive, conservative, neutral)
5. Experience memory recording for future reference
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.trading_consensus")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data models ──────────────────────────────────────────────


@dataclass(frozen=True)
class AnalystReport:
    """Immutable report from a single analyst role."""
    role: str           # "technical", "fundamental", "sentiment", "news"
    analysis: str
    signal: str         # "bullish", "bearish", "neutral"
    confidence: float   # 0-1


@dataclass(frozen=True)
class DebateResult:
    """Immutable result of a bull/bear adversarial debate."""
    bull_case: str
    bear_case: str
    rounds: int
    judge_decision: str   # "buy", "sell", "hold"
    judge_reasoning: str
    confidence: float


@dataclass(frozen=True)
class RiskResult:
    """Immutable consensus from 3 risk perspectives."""
    aggressive_view: str
    conservative_view: str
    neutral_view: str
    consensus_risk: str     # "low", "medium", "high"
    max_position_pct: float


@dataclass(frozen=True)
class ConsensusResult:
    """Immutable final consensus for an investment decision."""
    symbol: str
    signal: str            # "strong_buy", "buy", "hold", "sell", "strong_sell"
    confidence: float
    analyst_reports: tuple[AnalystReport, ...]
    debate: DebateResult
    risk: RiskResult
    reasoning: str
    timestamp: str


# ── Analyst prompts ──────────────────────────────────────────

_ANALYST_SYSTEMS: dict[str, str] = {
    "technical": (
        "You are an expert technical analyst. Analyze the given ticker using "
        "price action, support/resistance levels, moving averages, RSI, MACD, "
        "volume profile, and chart patterns. Provide a clear signal (bullish, "
        "bearish, or neutral) with a confidence score between 0 and 1."
    ),
    "fundamental": (
        "You are an expert fundamental analyst. Evaluate the given ticker using "
        "earnings quality, revenue growth, profit margins, balance sheet strength, "
        "cash flow, valuation multiples (P/E, P/S, EV/EBITDA), and competitive "
        "positioning. Provide a clear signal (bullish, bearish, or neutral) with "
        "a confidence score between 0 and 1."
    ),
    "sentiment": (
        "You are an expert sentiment analyst. Evaluate the given ticker by "
        "analyzing social media buzz, retail investor sentiment, institutional "
        "positioning, options flow (put/call ratios), short interest, and insider "
        "transactions. Provide a clear signal (bullish, bearish, or neutral) with "
        "a confidence score between 0 and 1."
    ),
    "news": (
        "You are an expert news and macro analyst. Evaluate the given ticker by "
        "analyzing recent news catalysts, sector trends, macroeconomic backdrop, "
        "regulatory developments, and geopolitical factors that may impact the "
        "stock. Provide a clear signal (bullish, bearish, or neutral) with a "
        "confidence score between 0 and 1."
    ),
}

_ANALYST_USER_TEMPLATE = (
    "Analyze {symbol} for a potential trade.\n\n"
    "Context:\n{context}\n\n"
    "Respond in JSON with keys: analysis (string), signal (bullish/bearish/neutral), "
    "confidence (float 0-1). Nothing else."
)


# ── Main class ───────────────────────────────────────────────


class TradingConsensus:
    """Structured bull/bear debate and consensus system for investment decisions.

    Orchestrates parallel analyst dispatch, adversarial debate, judicial
    synthesis, and multi-perspective risk assessment into a single
    ConsensusResult.
    """

    def __init__(
        self,
        llm=None,
        collab=None,
        experience_memory=None,
        memory=None,
    ) -> None:
        self._llm = llm
        self._collab = collab
        self._experience_memory = experience_memory
        self._memory = memory

    # ── Public API ───────────────────────────────────────────

    async def analyze_ticker(
        self,
        symbol: str,
        context: str = "",
    ) -> ConsensusResult:
        """Full consensus pipeline: analysts -> debate -> judge -> risk.

        1. Dispatch parallel analysis to 4 analyst roles
        2. Run bull/bear debate (2-3 rounds)
        3. Judge synthesises debate into final signal
        4. Score confidence based on agreement level
        5. Record in experience memory
        """
        symbol = symbol.upper().strip()
        logger.info("Starting consensus analysis for %s", symbol)

        # Step 1 — parallel analyst reports
        analyst_reports = await self._dispatch_analysts(symbol, context)
        logger.info(
            "Analyst reports for %s: %s",
            symbol,
            {r.role: r.signal for r in analyst_reports},
        )

        # Step 2+3 — bull/bear debate with judge synthesis
        debate = await self.bull_bear_debate(
            symbol,
            {r.role: r for r in analyst_reports},
        )
        logger.info(
            "Debate for %s: decision=%s confidence=%.2f",
            symbol,
            debate.judge_decision,
            debate.confidence,
        )

        # Step 4 — compute agreement-weighted confidence
        signal = self._decision_to_signal(debate.judge_decision, debate.confidence)
        overall_confidence = self._compute_confidence(analyst_reports, debate)

        # Step 5 — risk assessment
        risk = await self.risk_assessment(symbol, signal, overall_confidence)

        reasoning = (
            f"Consensus for {symbol}: {signal} (confidence {overall_confidence:.0%}). "
            f"Debate judge decided '{debate.judge_decision}' — {debate.judge_reasoning} "
            f"Risk level: {risk.consensus_risk}, max position {risk.max_position_pct:.1%}."
        )

        result = ConsensusResult(
            symbol=symbol,
            signal=signal,
            confidence=overall_confidence,
            analyst_reports=tuple(analyst_reports),
            debate=debate,
            risk=risk,
            reasoning=reasoning,
            timestamp=_now_iso(),
        )

        # Record in experience memory
        await self._record_experience(result)

        logger.info("Consensus complete for %s: %s", symbol, signal)
        return result

    async def bull_bear_debate(
        self,
        symbol: str,
        analyst_reports: dict[str, AnalystReport],
        rounds: int = 2,
    ) -> DebateResult:
        """Adversarial debate between bull and bear, resolved by a judge.

        Round 1: Bull presents using analyst reports, bear counter-argues.
        Round 2+: Each side responds to the other's latest arguments.
        Final: Judge evaluates both sides and decides.
        """
        if not self._llm:
            return self._fallback_debate(analyst_reports)

        reports_summary = "\n".join(
            f"- {role}: {r.signal} (confidence {r.confidence:.0%}) — {r.analysis[:300]}"
            for role, r in analyst_reports.items()
        )

        bull_history: list[str] = []
        bear_history: list[str] = []

        # ── Debate rounds ────────────────────────────────────
        for round_num in range(1, rounds + 1):
            if round_num == 1:
                bull_prompt = (
                    f"You are the BULL advocate for {symbol}. Using these analyst reports, "
                    f"make the strongest possible case for BUYING this stock.\n\n"
                    f"Analyst Reports:\n{reports_summary}\n\n"
                    f"Present your bull case clearly and persuasively."
                )
                bear_prompt = (
                    f"You are the BEAR advocate for {symbol}. Using these analyst reports, "
                    f"make the strongest possible case AGAINST buying this stock.\n\n"
                    f"Analyst Reports:\n{reports_summary}\n\n"
                    f"Present your bear case clearly and persuasively."
                )
            else:
                bull_prompt = (
                    f"You are the BULL advocate for {symbol}. The bear argued:\n\n"
                    f"{bear_history[-1]}\n\n"
                    f"Respond to their arguments and strengthen your bull case."
                )
                bear_prompt = (
                    f"You are the BEAR advocate for {symbol}. The bull argued:\n\n"
                    f"{bull_history[-1]}\n\n"
                    f"Respond to their arguments and strengthen your bear case."
                )

            # Run bull and bear in parallel each round
            bull_task = self._llm.complete(
                messages=[{"role": "user", "content": bull_prompt}],
                system="You are a passionate bull investor. Argue for buying.",
                model_tier="fast",
                temperature=0.8,
            )
            bear_task = self._llm.complete(
                messages=[{"role": "user", "content": bear_prompt}],
                system="You are a cautious bear investor. Argue against buying.",
                model_tier="fast",
                temperature=0.8,
            )

            bull_response, bear_response = await asyncio.gather(
                bull_task, bear_task,
            )

            bull_history.append(bull_response)
            bear_history.append(bear_response)

            logger.debug(
                "Debate round %d/%d for %s complete",
                round_num,
                rounds,
                symbol,
            )

        # ── Judge synthesis ──────────────────────────────────
        judge_prompt = (
            f"You are an impartial investment judge evaluating {symbol}.\n\n"
            f"BULL's final argument:\n{bull_history[-1]}\n\n"
            f"BEAR's final argument:\n{bear_history[-1]}\n\n"
            f"Analyst Reports:\n{reports_summary}\n\n"
            f"Weigh both sides carefully. Respond in JSON with keys: "
            f"decision (buy/sell/hold), reasoning (string), confidence (float 0-1). "
            f"Nothing else."
        )

        judge_raw = await self._llm.complete(
            messages=[{"role": "user", "content": judge_prompt}],
            system="You are a fair, rational investment judge. Decide based on evidence.",
            model_tier="default",
            temperature=0.3,
        )

        judge_data = self._parse_json(judge_raw, {
            "decision": "hold",
            "reasoning": "Unable to parse judge response",
            "confidence": 0.5,
        })

        return DebateResult(
            bull_case=bull_history[-1],
            bear_case=bear_history[-1],
            rounds=rounds,
            judge_decision=judge_data.get("decision", "hold"),
            judge_reasoning=judge_data.get("reasoning", ""),
            confidence=float(judge_data.get("confidence", 0.5)),
        )

    async def risk_assessment(
        self,
        symbol: str,
        signal: str,
        confidence: float,
    ) -> RiskResult:
        """Run 3 risk perspectives in parallel: aggressive, conservative, neutral.

        Returns consensus risk level and recommended max position size.
        """
        if not self._llm:
            return self._fallback_risk()

        perspectives = {
            "aggressive": (
                f"You are an aggressive risk manager. Given a {signal} signal on {symbol} "
                f"with {confidence:.0%} confidence, assess risk and recommend max position "
                f"size as a portfolio percentage. You favor larger positions on high-conviction "
                f"trades. Respond in JSON: view (string), risk (low/medium/high), "
                f"max_position_pct (float 0-1). Nothing else."
            ),
            "conservative": (
                f"You are a conservative risk manager. Given a {signal} signal on {symbol} "
                f"with {confidence:.0%} confidence, assess risk and recommend max position "
                f"size as a portfolio percentage. You prioritize capital preservation above all. "
                f"Respond in JSON: view (string), risk (low/medium/high), "
                f"max_position_pct (float 0-1). Nothing else."
            ),
            "neutral": (
                f"You are a balanced risk manager. Given a {signal} signal on {symbol} "
                f"with {confidence:.0%} confidence, assess risk and recommend max position "
                f"size as a portfolio percentage. You balance growth and safety. "
                f"Respond in JSON: view (string), risk (low/medium/high), "
                f"max_position_pct (float 0-1). Nothing else."
            ),
        }

        tasks = {
            name: self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                system=f"You are a {name} risk manager.",
                model_tier="fast",
                temperature=0.4,
            )
            for name, prompt in perspectives.items()
        }

        results = await asyncio.gather(*tasks.values())
        parsed: dict[str, dict] = {}
        for name, raw in zip(tasks.keys(), results):
            parsed[name] = self._parse_json(raw, {
                "view": f"{name} view unavailable",
                "risk": "medium",
                "max_position_pct": 0.02,
            })

        # Consensus: majority vote on risk level
        risk_votes = [parsed[n].get("risk", "medium") for n in ("aggressive", "conservative", "neutral")]
        consensus_risk = max(set(risk_votes), key=risk_votes.count)

        # Position size: use the median recommendation
        position_pcts = sorted(
            float(parsed[n].get("max_position_pct", 0.02))
            for n in ("aggressive", "conservative", "neutral")
        )
        median_position = position_pcts[1]  # middle of 3

        return RiskResult(
            aggressive_view=parsed["aggressive"].get("view", ""),
            conservative_view=parsed["conservative"].get("view", ""),
            neutral_view=parsed["neutral"].get("view", ""),
            consensus_risk=consensus_risk,
            max_position_pct=min(median_position, 0.05),  # hard cap at 5%
        )

    # ── Internal helpers ─────────────────────────────────────

    async def _dispatch_analysts(
        self,
        symbol: str,
        context: str,
    ) -> list[AnalystReport]:
        """Run 4 analyst roles in parallel and return their reports."""
        if not self._llm:
            return self._fallback_analysts(symbol)

        roles = ("technical", "fundamental", "sentiment", "news")

        async def _run_analyst(role: str) -> AnalystReport:
            user_msg = _ANALYST_USER_TEMPLATE.format(
                symbol=symbol,
                context=context or "No additional context provided.",
            )
            raw = await self._llm.complete(
                messages=[{"role": "user", "content": user_msg}],
                system=_ANALYST_SYSTEMS[role],
                model_tier="default",
                temperature=0.5,
            )
            data = self._parse_json(raw, {
                "analysis": f"{role} analysis unavailable",
                "signal": "neutral",
                "confidence": 0.5,
            })
            signal = data.get("signal", "neutral").lower()
            if signal not in ("bullish", "bearish", "neutral"):
                signal = "neutral"
            return AnalystReport(
                role=role,
                analysis=data.get("analysis", ""),
                signal=signal,
                confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
            )

        results = await asyncio.gather(
            *(_run_analyst(role) for role in roles),
            return_exceptions=True,
        )

        reports: list[AnalystReport] = []
        for role, result in zip(roles, results):
            if isinstance(result, Exception):
                logger.warning("Analyst %s failed: %s", role, result)
                reports.append(AnalystReport(
                    role=role,
                    analysis=f"Analysis failed: {result}",
                    signal="neutral",
                    confidence=0.0,
                ))
            else:
                reports.append(result)

        return reports

    def _decision_to_signal(self, decision: str, confidence: float) -> str:
        """Map judge decision + confidence into a 5-tier signal."""
        decision = decision.lower().strip()
        if decision == "buy":
            return "strong_buy" if confidence >= 0.8 else "buy"
        elif decision == "sell":
            return "strong_sell" if confidence >= 0.8 else "sell"
        return "hold"

    def _compute_confidence(
        self,
        reports: list[AnalystReport],
        debate: DebateResult,
    ) -> float:
        """Weighted confidence: 40% analyst agreement + 60% debate judge."""
        if not reports:
            return debate.confidence

        # Analyst agreement: what fraction agree with the judge's direction?
        judge_dir = debate.judge_decision.lower()
        agree_map = {"buy": "bullish", "sell": "bearish", "hold": "neutral"}
        target_signal = agree_map.get(judge_dir, "neutral")

        agreeing = sum(1 for r in reports if r.signal == target_signal)
        agreement_ratio = agreeing / len(reports)

        # Weighted average of analyst confidence for agreeing analysts
        agreeing_conf = [r.confidence for r in reports if r.signal == target_signal]
        avg_analyst_conf = (sum(agreeing_conf) / len(agreeing_conf)) if agreeing_conf else 0.5

        analyst_score = agreement_ratio * avg_analyst_conf
        return 0.4 * analyst_score + 0.6 * debate.confidence

    async def _record_experience(self, result: ConsensusResult) -> None:
        """Record the consensus result in experience memory for future learning."""
        if not self._experience_memory:
            return
        try:
            self._experience_memory.record_experience(
                experience_type="strategy",
                domain="trading",
                title=f"Consensus: {result.symbol} = {result.signal}",
                description=result.reasoning,
                context={
                    "symbol": result.symbol,
                    "signal": result.signal,
                    "confidence": result.confidence,
                    "debate_decision": result.debate.judge_decision,
                    "risk_level": result.risk.consensus_risk,
                    "analyst_signals": {r.role: r.signal for r in result.analyst_reports},
                },
                confidence=result.confidence,
                tags=["trading", "consensus", result.symbol.lower()],
            )
        except Exception as exc:
            logger.warning("Failed to record consensus experience: %s", exc)

    @staticmethod
    def _parse_json(raw: str, fallback: dict[str, Any]) -> dict[str, Any]:
        """Extract JSON from LLM response, returning fallback on failure."""
        text = raw.strip()
        # Try to find JSON block in markdown fences
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()
        # Try to find JSON object
        if not text.startswith("{"):
            brace_start = text.find("{")
            if brace_start != -1:
                text = text[brace_start:]
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            logger.debug("Failed to parse JSON from LLM response: %s", raw[:200])
            return fallback

    # ── Fallbacks (no LLM available) ─────────────────────────

    @staticmethod
    def _fallback_analysts(symbol: str) -> list[AnalystReport]:
        """Return neutral placeholder reports when LLM is unavailable."""
        return [
            AnalystReport(
                role=role,
                analysis=f"LLM unavailable — {role} analysis not performed for {symbol}",
                signal="neutral",
                confidence=0.0,
            )
            for role in ("technical", "fundamental", "sentiment", "news")
        ]

    @staticmethod
    def _fallback_debate(analyst_reports: dict) -> DebateResult:
        """Return neutral placeholder debate when LLM is unavailable."""
        return DebateResult(
            bull_case="LLM unavailable — no bull case generated",
            bear_case="LLM unavailable — no bear case generated",
            rounds=0,
            judge_decision="hold",
            judge_reasoning="No LLM available for debate",
            confidence=0.0,
        )

    @staticmethod
    def _fallback_risk() -> RiskResult:
        """Return conservative placeholder risk when LLM is unavailable."""
        return RiskResult(
            aggressive_view="LLM unavailable",
            conservative_view="LLM unavailable",
            neutral_view="LLM unavailable",
            consensus_risk="high",
            max_position_pct=0.01,
        )
