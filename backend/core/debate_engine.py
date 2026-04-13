"""
Debate Engine — Bull/Bear structured investment debates.

Implements the TradingAgents-style debate architecture:
1. Analyst team produces reports (parallel)
2. Bull researcher builds bullish case from reports
3. Bear researcher builds bearish case from reports
4. Multiple debate rounds with rebuttals
5. Research Manager synthesizes verdict
6. Risk Manager evaluates from 3 perspectives (aggressive/conservative/neutral)
7. Portfolio Manager makes final decision

Uses ROOT's existing AgentCollaboration + MessageBus for orchestration.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.debate_engine")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class DebatePosition:
    """One side of a debate."""
    side: str              # "bull" | "bear"
    arguments: list[str]
    key_evidence: list[str]
    confidence: float      # 0-100
    rebuttal_to: Optional[str] = None  # What the opponent said


@dataclass(frozen=True)
class DebateRound:
    """A single round of bull/bear exchange."""
    round_number: int
    bull_position: DebatePosition
    bear_position: DebatePosition
    duration_seconds: float


@dataclass(frozen=True)
class RiskPerspective:
    """Risk assessment from one perspective."""
    perspective: str       # "aggressive" | "conservative" | "neutral"
    verdict: str           # "approve" | "reject" | "reduce_size"
    max_position_pct: float
    key_risks: list[str]
    confidence: float


@dataclass(frozen=True)
class DebateVerdict:
    """Final output of a complete debate."""
    id: str
    symbol: str
    analyst_reports: dict[str, str]  # analyst_id -> report summary
    debate_rounds: list[DebateRound]
    research_manager_verdict: str    # "bullish" | "bearish" | "neutral"
    research_manager_reasoning: str
    risk_perspectives: list[RiskPerspective]
    final_decision: str              # "buy" | "sell" | "hold" | "short" | "cover"
    final_confidence: float          # 0-100
    position_size_pct: float
    investment_thesis: str
    executive_summary: str
    duration_seconds: float
    created_at: str = field(default_factory=_now_iso)


# ── Debate Engine ────────────────────────────────────────────

class DebateEngine:
    """Runs structured Bull/Bear investment debates."""

    def __init__(
        self,
        llm,
        investment_runner=None,
        market_data=None,
        experience_memory=None,
        prediction_ledger=None,
        bus=None,
    ) -> None:
        self._llm = llm
        self._investment_runner = investment_runner
        self._market_data = market_data
        self._experience = experience_memory
        self._prediction_ledger = prediction_ledger
        self._bus = bus
        self._debates: list[DebateVerdict] = []

    async def run_debate(
        self,
        symbol: str,
        max_rounds: int = 2,
        analyst_agents: Optional[list[str]] = None,
        risk_rounds: int = 1,
    ) -> DebateVerdict:
        """Run a full investment debate on a symbol.

        Flow:
        1. Analyst team (parallel) → reports
        2. Bull/Bear debate (N rounds)
        3. Research Manager → verdict
        4. Risk team (3 perspectives) → approval
        5. Portfolio Manager → final decision
        """
        start_time = time.monotonic()
        debate_id = f"debate-{uuid.uuid4().hex[:8]}"

        if not self._llm:
            raise RuntimeError("LLM required for debate engine")

        # ── 1. Analyst Reports (parallel) ────────────────────
        analyst_ids = analyst_agents or [
            "valuation_analyst", "fundamentals_analyst",
            "sentiment_analyst", "technical_analyst",
        ]
        analyst_reports = {}
        if self._investment_runner:
            signals = await self._investment_runner.analyze_multi(analyst_ids, symbol)
            for sig in signals:
                analyst_reports[sig.agent_id] = (
                    f"Signal: {sig.signal} (confidence: {sig.confidence}%)\n"
                    f"Thesis: {sig.thesis}\n"
                    f"Reasoning: {sig.reasoning}"
                )

        if not analyst_reports:
            # Fallback: generate basic data context
            analyst_reports["data"] = self._build_data_summary(symbol)

        reports_text = "\n\n".join(
            f"[{aid.upper()}]\n{report}" for aid, report in analyst_reports.items()
        )

        # ── 2. Bull/Bear Debate ──────────────────────────────
        debate_rounds = []
        bull_history = []
        bear_history = []

        for round_num in range(1, max_rounds + 1):
            round_start = time.monotonic()

            # Bull argues
            bull_pos = await self._generate_position(
                symbol, "bull", reports_text, bear_history, round_num,
            )
            bull_history.append(bull_pos)

            # Bear argues (with access to bull's latest)
            bear_pos = await self._generate_position(
                symbol, "bear", reports_text, bull_history, round_num,
            )
            bear_history.append(bear_pos)

            debate_rounds.append(DebateRound(
                round_number=round_num,
                bull_position=bull_pos,
                bear_position=bear_pos,
                duration_seconds=round(time.monotonic() - round_start, 2),
            ))

        # ── 3. Research Manager Synthesis ─────────────────────
        rm_verdict, rm_reasoning = await self._research_manager_synthesis(
            symbol, reports_text, debate_rounds,
        )

        # ── 4. Risk Assessment (3 perspectives) ──────────────
        risk_perspectives = await self._risk_assessment(
            symbol, rm_verdict, rm_reasoning, reports_text, risk_rounds,
        )

        # ── 5. Portfolio Manager Final Decision ───────────────
        decision, confidence, size_pct, thesis, summary = await self._portfolio_manager_decision(
            symbol, rm_verdict, rm_reasoning, risk_perspectives, reports_text, debate_rounds,
        )

        elapsed = round(time.monotonic() - start_time, 2)

        verdict = DebateVerdict(
            id=debate_id,
            symbol=symbol.upper(),
            analyst_reports=analyst_reports,
            debate_rounds=debate_rounds,
            research_manager_verdict=rm_verdict,
            research_manager_reasoning=rm_reasoning,
            risk_perspectives=risk_perspectives,
            final_decision=decision,
            final_confidence=confidence,
            position_size_pct=size_pct,
            investment_thesis=thesis,
            executive_summary=summary,
            duration_seconds=elapsed,
        )

        self._debates.append(verdict)

        # Record prediction if we have a ledger
        if self._prediction_ledger and decision in ("buy", "short"):
            direction = "long" if decision == "buy" else "short"
            try:
                self._prediction_ledger.record_prediction(
                    source="debate_engine",
                    symbol=symbol.upper(),
                    direction=direction,
                    confidence=confidence / 100.0,
                    reasoning=summary[:500],
                    deadline_hours=168,  # 1 week
                )
            except Exception as e:
                logger.warning("Failed to record debate prediction: %s", e)

        # Publish to bus
        if self._bus:
            try:
                msg = self._bus.create_message(
                    topic="system.debate",
                    sender="debate_engine",
                    payload={
                        "debate_id": debate_id,
                        "symbol": symbol,
                        "decision": decision,
                        "confidence": confidence,
                        "thesis": thesis[:200],
                    },
                )
                await self._bus.publish(msg)
            except Exception:
                pass

        logger.info(
            "Debate %s on %s: %s (confidence=%.0f%%, size=%.1f%%) in %.1fs",
            debate_id, symbol, decision, confidence, size_pct, elapsed,
        )

        return verdict

    async def _generate_position(
        self,
        symbol: str,
        side: str,
        reports_text: str,
        opponent_history: list[DebatePosition],
        round_num: int,
    ) -> DebatePosition:
        """Generate bull or bear position."""
        opponent_label = "bear" if side == "bull" else "bull"

        system = (
            f"You are the {side.upper()} researcher in an investment debate about {symbol}.\n"
            f"{'Emphasize growth potential, competitive advantages, and positive indicators.' if side == 'bull' else 'Emphasize risks, weaknesses, and negative indicators.'}\n"
            f"Critically analyze the {opponent_label}'s arguments and show why your position is stronger.\n"
            f"Be specific with numbers and evidence. No vague generalities."
        )

        opponent_text = ""
        if opponent_history:
            last = opponent_history[-1]
            opponent_text = (
                f"\n\n{opponent_label.upper()}'S LATEST ARGUMENTS:\n"
                + "\n".join(f"- {a}" for a in last.arguments)
                + f"\nEvidence: {', '.join(last.key_evidence[:3])}"
            )

        # Inject past experience if available
        experience_text = ""
        if self._experience:
            try:
                experiences = self._experience.query(
                    category="trading", query=f"{symbol} {side}", limit=2,
                )
                if experiences:
                    experience_text = "\n\nPAST LESSONS:\n" + "\n".join(
                        f"- {e.get('lesson', '')}" for e in experiences[:2]
                    )
            except Exception:
                pass

        user_msg = (
            f"Round {round_num}: Present your {side.upper()} case for {symbol}.\n\n"
            f"ANALYST REPORTS:\n{reports_text}"
            f"{opponent_text}"
            f"{experience_text}\n\n"
            f"Respond as JSON:\n"
            f'{{"arguments": ["arg1", "arg2", ...], "key_evidence": ["ev1", "ev2", ...], '
            f'"confidence": 0-100}}'
        )

        try:
            response = await self._llm.complete(
                messages=[{"role": "user", "content": user_msg}],
                system=system,
                model_tier="default",
                max_tokens=1500,
                temperature=0.4,
            )
            return self._parse_position(side, response, opponent_text)
        except Exception as e:
            logger.error("Debate position generation failed (%s, %s): %s", symbol, side, e)
            return DebatePosition(
                side=side,
                arguments=[f"Unable to generate {side} arguments"],
                key_evidence=[],
                confidence=50.0,
            )

    def _parse_position(self, side: str, response: str, rebuttal_to: str) -> DebatePosition:
        """Parse LLM response into DebatePosition."""
        import json
        try:
            text = response.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                data = {}

            return DebatePosition(
                side=side,
                arguments=data.get("arguments", [response[:200]]),
                key_evidence=data.get("key_evidence", []),
                confidence=max(0, min(100, float(data.get("confidence", 50)))),
                rebuttal_to=rebuttal_to[:200] if rebuttal_to else None,
            )
        except (json.JSONDecodeError, ValueError):
            return DebatePosition(
                side=side,
                arguments=[response[:300]],
                key_evidence=[],
                confidence=50.0,
                rebuttal_to=rebuttal_to[:200] if rebuttal_to else None,
            )

    async def _research_manager_synthesis(
        self,
        symbol: str,
        reports_text: str,
        debate_rounds: list[DebateRound],
    ) -> tuple[str, str]:
        """Research Manager reviews debate and issues verdict."""
        debate_summary = ""
        for dr in debate_rounds:
            debate_summary += (
                f"\nROUND {dr.round_number}:\n"
                f"BULL: {'; '.join(dr.bull_position.arguments[:3])}\n"
                f"BEAR: {'; '.join(dr.bear_position.arguments[:3])}\n"
            )

        system = (
            f"You are the Research Manager synthesizing the investment debate on {symbol}.\n"
            "Review the bull and bear arguments, weigh the evidence, and commit to a verdict.\n"
            "Be decisive — no fence-sitting. Your verdict must be actionable."
        )

        user_msg = (
            f"ANALYST REPORTS:\n{reports_text}\n\n"
            f"DEBATE:\n{debate_summary}\n\n"
            f"Respond as JSON:\n"
            f'{{"verdict": "bullish|bearish|neutral", "reasoning": "your detailed reasoning"}}'
        )

        try:
            response = await self._llm.complete(
                messages=[{"role": "user", "content": user_msg}],
                system=system,
                model_tier="default",
                max_tokens=1500,
                temperature=0.2,
            )

            import json
            text = response.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                verdict = data.get("verdict", "neutral").lower()
                if verdict not in ("bullish", "bearish", "neutral"):
                    verdict = "neutral"
                return verdict, data.get("reasoning", response)
        except Exception as e:
            logger.error("Research manager synthesis failed: %s", e)

        return "neutral", "Unable to synthesize debate"

    async def _risk_assessment(
        self,
        symbol: str,
        verdict: str,
        reasoning: str,
        reports_text: str,
        risk_rounds: int,
    ) -> list[RiskPerspective]:
        """Three risk perspectives evaluate the verdict."""
        perspectives = ["aggressive", "conservative", "neutral"]
        results = []

        for perspective in perspectives:
            system = (
                f"You are the {perspective.upper()} risk assessor for {symbol}.\n"
                f"The research verdict is {verdict.upper()}.\n\n"
                f"{'You favor taking calculated risks for higher returns.' if perspective == 'aggressive' else ''}"
                f"{'You prioritize capital preservation above all else.' if perspective == 'conservative' else ''}"
                f"{'You balance risk and reward objectively.' if perspective == 'neutral' else ''}"
            )

            user_msg = (
                f"RESEARCH VERDICT: {verdict}\n"
                f"REASONING: {reasoning[:500]}\n\n"
                f"Respond as JSON:\n"
                f'{{"verdict": "approve|reject|reduce_size", '
                f'"max_position_pct": 0-10, "key_risks": ["risk1", ...], "confidence": 0-100}}'
            )

            try:
                response = await self._llm.complete(
                    messages=[{"role": "user", "content": user_msg}],
                    system=system,
                    model_tier="fast",
                    max_tokens=800,
                    temperature=0.3,
                )

                import json
                text = response.strip()
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(text[start:end])
                    results.append(RiskPerspective(
                        perspective=perspective,
                        verdict=data.get("verdict", "reject"),
                        max_position_pct=min(10, max(0, float(data.get("max_position_pct", 2)))),
                        key_risks=data.get("key_risks", []),
                        confidence=max(0, min(100, float(data.get("confidence", 50)))),
                    ))
                    continue
            except Exception as e:
                logger.warning("Risk assessment failed for %s: %s", perspective, e)

            results.append(RiskPerspective(
                perspective=perspective,
                verdict="reject",
                max_position_pct=1.0,
                key_risks=["Assessment failed"],
                confidence=0,
            ))

        return results

    async def _portfolio_manager_decision(
        self,
        symbol: str,
        verdict: str,
        reasoning: str,
        risk_perspectives: list[RiskPerspective],
        reports_text: str,
        debate_rounds: list[DebateRound],
    ) -> tuple[str, float, float, str, str]:
        """Portfolio Manager makes final actionable decision."""
        risk_summary = "\n".join(
            f"{rp.perspective}: {rp.verdict} (max {rp.max_posi_pct}%, confidence {rp.confidence}%)"
            if hasattr(rp, 'max_posi_pct') else
            f"{rp.perspective}: {rp.verdict} (max {rp.max_position_pct}%, confidence {rp.confidence}%)"
            for rp in risk_perspectives
        )

        # Calculate allowed position from risk team consensus
        approved = [rp for rp in risk_perspectives if rp.verdict in ("approve", "reduce_size")]
        if approved:
            avg_size = sum(rp.max_position_pct for rp in approved) / len(approved)
        else:
            avg_size = 0.0

        system = (
            f"You are the Portfolio Manager making the FINAL investment decision on {symbol}.\n"
            f"Research verdict: {verdict.upper()}\n"
            f"Risk team average position: {avg_size:.1f}%\n\n"
            "Choose one: Buy, Hold, Sell, Short, Cover.\n"
            "Provide executive summary with entry tactics, position sizing, and risk thresholds."
        )

        user_msg = (
            f"RESEARCH VERDICT: {verdict}\n"
            f"REASONING: {reasoning[:500]}\n\n"
            f"RISK ASSESSMENTS:\n{risk_summary}\n\n"
            f"Respond as JSON:\n"
            f'{{"decision": "buy|sell|hold|short|cover", "confidence": 0-100, '
            f'"position_size_pct": 0-5, '
            f'"investment_thesis": "detailed thesis paragraph", '
            f'"executive_summary": "entry/exit/risk summary"}}'
        )

        try:
            response = await self._llm.complete(
                messages=[{"role": "user", "content": user_msg}],
                system=system,
                model_tier="default",
                max_tokens=1500,
                temperature=0.2,
            )

            import json
            text = response.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                decision = data.get("decision", "hold").lower()
                if decision not in ("buy", "sell", "hold", "short", "cover"):
                    decision = "hold"
                confidence = max(0, min(100, float(data.get("confidence", 50))))
                size = min(5.0, max(0, float(data.get("position_size_pct", avg_size))))
                thesis = data.get("investment_thesis", "")
                summary = data.get("executive_summary", "")
                return decision, confidence, size, thesis, summary
        except Exception as e:
            logger.error("Portfolio manager decision failed: %s", e)

        # Fallback
        fallback_decision = "buy" if verdict == "bullish" else "sell" if verdict == "bearish" else "hold"
        return fallback_decision, 50.0, min(avg_size, 2.0), reasoning[:300], "Debate completed with fallback decision"

    def _build_data_summary(self, symbol: str) -> str:
        """Build basic data summary when no investment runner is available."""
        if not self._market_data:
            return f"No market data available for {symbol}"

        parts = []
        quote = self._market_data.get_quote(symbol)
        if quote:
            parts.append(f"Price: ${quote.price} ({quote.change_pct:+.2f}%)")

        fm = self._market_data.get_financials(symbol)
        if fm:
            metrics = []
            if fm.pe_ratio:
                metrics.append(f"P/E: {fm.pe_ratio:.1f}")
            if fm.profit_margin:
                metrics.append(f"Margin: {fm.profit_margin:.1%}")
            if fm.revenue_growth:
                metrics.append(f"Rev Growth: {fm.revenue_growth:.1%}")
            if fm.roe:
                metrics.append(f"ROE: {fm.roe:.1%}")
            parts.append(", ".join(metrics))

        return "\n".join(parts) if parts else f"Limited data for {symbol}"

    def get_debate(self, debate_id: str) -> Optional[DebateVerdict]:
        """Retrieve a debate by ID."""
        for d in self._debates:
            if d.id == debate_id:
                return d
        return None

    def get_debates(self, symbol: Optional[str] = None, limit: int = 10) -> list[DebateVerdict]:
        """List recent debates."""
        results = self._debates
        if symbol:
            results = [d for d in results if d.symbol == symbol.upper()]
        return results[-limit:]

    def stats(self) -> dict:
        """Engine statistics."""
        if not self._debates:
            return {"total_debates": 0}

        decisions = [d.final_decision for d in self._debates]
        return {
            "total_debates": len(self._debates),
            "avg_confidence": round(sum(d.final_confidence for d in self._debates) / len(self._debates), 1),
            "decisions": {d: decisions.count(d) for d in set(decisions)},
            "avg_duration_seconds": round(sum(d.duration_seconds for d in self._debates) / len(self._debates), 1),
        }
