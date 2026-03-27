"""
Interest Assessment Engine — ROOT's moral compass and decision filter.

Evaluates every opportunity, decision, and recommendation through
Yohan's personal interest framework:
- Financial impact (money is foundational)
- Time investment vs. return
- Risk tolerance alignment
- Long-term vs. short-term gain
- Skill/knowledge growth
- Personal values alignment
- Opportunity cost
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("root.interest")


class Verdict(str, Enum):
    """Assessment outcome."""
    STRONGLY_ALIGNED = "strongly_aligned"
    ALIGNED = "aligned"
    NEUTRAL = "neutral"
    MISALIGNED = "misaligned"
    STRONGLY_MISALIGNED = "strongly_misaligned"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class InterestAssessment:
    """Immutable assessment of whether something serves Yohan's interests."""
    subject: str
    verdict: Verdict
    score: float  # -1.0 (against interests) to +1.0 (strongly in interests)
    financial_impact: float  # estimated $ impact (positive = gain)
    time_cost_hours: float
    risk_level: RiskLevel
    reasoning: str
    benefits: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommendation: str = ""
    knowledge_domains: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Yohan's Interest Profile ──────────────────────────────────

YOHAN_PROFILE = {
    "core_values": [
        "financial_independence",
        "continuous_learning",
        "building_systems",
        "automation",
        "family_security",
        "health",
        "freedom_of_time",
    ],
    "financial_goals": {
        "short_term": "Generate $10K+/month from tech products and services",
        "medium_term": "Build SaaS products that generate recurring revenue",
        "long_term": "Financial independence through multiple income streams",
    },
    "skills": [
        "software_development",
        "ai_engineering",
        "data_pipelines",
        "web_scraping",
        "api_development",
        "lead_generation",
        "construction_industry_knowledge",
    ],
    "assets": [
        "permit_pulse_platform",
        "root_ai_system",
        "gc_app",
        "technical_expertise",
        "construction_data_knowledge",
    ],
    "risk_tolerance": "medium",  # willing to invest time, cautious with money
    "time_availability": "high_if_automated",  # prefers systems that run themselves
    "deal_breakers": [
        "requires_large_upfront_capital",
        "legal_risk",
        "ethical_violations",
        "time_intensive_manual_labor",
        "dependent_on_single_client",
    ],
}


class InterestEngine:
    """Evaluates decisions, opportunities, and actions through Yohan's interest lens."""

    def __init__(self, memory=None, llm=None) -> None:
        self._memory = memory
        self._llm = llm
        self._assessment_history: list[InterestAssessment] = []

    def assess(
        self,
        subject: str,
        context: str = "",
        financial_impact: float = 0.0,
        time_cost_hours: float = 0.0,
        risk_level: str = "medium",
    ) -> InterestAssessment:
        """Quick rule-based assessment of whether something serves Yohan's interests."""
        score = 0.0
        benefits = []
        risks = []
        domains = []

        subject_lower = subject.lower()
        context_lower = (context or "").lower()
        combined = f"{subject_lower} {context_lower}"

        # ── Financial scoring (most important) ──
        if financial_impact > 0:
            score += min(0.4, financial_impact / 10000 * 0.4)
            benefits.append(f"Financial gain: ${financial_impact:,.0f}")
        elif financial_impact < 0:
            if abs(financial_impact) > 5000:
                score -= 0.3
                risks.append(f"Significant cost: ${abs(financial_impact):,.0f}")
            else:
                score -= 0.1
                risks.append(f"Cost: ${abs(financial_impact):,.0f}")

        # ── Revenue/income alignment ──
        revenue_terms = ["revenue", "income", "profit", "money", "saas", "recurring", "subscription", "passive"]
        for term in revenue_terms:
            if term in combined:
                score += 0.15
                benefits.append(f"Revenue potential ({term})")
                domains.append("financial")
                break

        # ── Technology/building alignment ──
        tech_terms = ["api", "software", "platform", "automation", "ai", "data", "scraping", "pipeline"]
        for term in tech_terms:
            if term in combined:
                score += 0.1
                benefits.append(f"Tech/building alignment ({term})")
                domains.append("technology")
                break

        # ── Construction industry (Yohan's domain expertise) ──
        construction_terms = ["permit", "construction", "contractor", "building", "lead", "gc ", "general contractor"]
        for term in construction_terms:
            if term in combined:
                score += 0.1
                benefits.append("Leverages construction industry expertise")
                domains.append("construction")
                break

        # ── Learning/growth ──
        learning_terms = ["learn", "skill", "knowledge", "research", "study", "understand", "master"]
        for term in learning_terms:
            if term in combined:
                score += 0.08
                benefits.append("Growth opportunity")
                domains.append("personal_development")
                break

        # ── Automation preference ──
        if any(t in combined for t in ["automate", "automation", "self-running", "passive", "scheduled"]):
            score += 0.1
            benefits.append("Aligns with automation preference")

        # ── Time cost penalty ──
        if time_cost_hours > 40:
            score -= 0.2
            risks.append(f"High time investment: {time_cost_hours}h")
        elif time_cost_hours > 20:
            score -= 0.1
            risks.append(f"Moderate time investment: {time_cost_hours}h")

        # ── Risk assessment ──
        try:
            rl = RiskLevel(risk_level)
        except ValueError:
            rl = RiskLevel.MEDIUM

        if rl == RiskLevel.VERY_HIGH:
            score -= 0.2
            risks.append("Very high risk")
        elif rl == RiskLevel.HIGH:
            score -= 0.1
            risks.append("High risk")

        # ── Deal breaker check ──
        dealbreakers = {
            "large upfront capital": "requires_large_upfront_capital",
            "legal risk": "legal_risk",
            "manual labor": "time_intensive_manual_labor",
            "single client": "dependent_on_single_client",
        }
        for phrase, db in dealbreakers.items():
            if phrase in combined:
                score -= 0.4
                risks.append(f"DEAL BREAKER: {db}")

        # ── Clamp and classify ──
        score = max(-1.0, min(1.0, score))

        if score >= 0.5:
            verdict = Verdict.STRONGLY_ALIGNED
        elif score >= 0.2:
            verdict = Verdict.ALIGNED
        elif score >= -0.1:
            verdict = Verdict.NEUTRAL
        elif score >= -0.4:
            verdict = Verdict.MISALIGNED
        else:
            verdict = Verdict.STRONGLY_MISALIGNED

        # ── Build recommendation ──
        if verdict in (Verdict.STRONGLY_ALIGNED, Verdict.ALIGNED):
            recommendation = "PROCEED — this aligns with Yohan's interests and goals."
        elif verdict == Verdict.NEUTRAL:
            recommendation = "EVALUATE FURTHER — not enough signal to recommend or reject."
        else:
            recommendation = "AVOID — this does not serve Yohan's interests well."

        assessment = InterestAssessment(
            subject=subject,
            verdict=verdict,
            score=round(score, 3),
            financial_impact=financial_impact,
            time_cost_hours=time_cost_hours,
            risk_level=rl,
            reasoning=f"Score {score:.2f} based on {len(benefits)} benefits, {len(risks)} risks.",
            benefits=benefits,
            risks=risks,
            recommendation=recommendation,
            knowledge_domains=list(set(domains)),
        )

        self._assessment_history.append(assessment)

        # Store assessment in memory if engine available
        if self._memory:
            from backend.models.memory import MemoryEntry, MemoryType
            self._memory.store(MemoryEntry(
                content=f"Interest assessment: '{subject}' → {verdict.value} ({score:.2f}). {recommendation}",
                memory_type=MemoryType.OBSERVATION,
                tags=["interest-assessment", verdict.value] + domains,
                source="interest_engine",
                confidence=0.85,
            ))

        return assessment

    async def assess_with_llm(self, subject: str, context: str = "") -> InterestAssessment:
        """Deep assessment using LLM for nuanced analysis."""
        if not self._llm:
            return self.assess(subject, context)

        prompt = f"""Analyze this opportunity/decision for Yohan Bismuth.

YOHAN'S PROFILE:
- Software developer & AI engineer
- Builds: Permit Pulse (construction lead platform), ROOT (personal AI), GC App
- Goals: Financial independence through tech products, recurring SaaS revenue
- Skills: Python, FastAPI, data pipelines, web scraping, AI/LLM integration
- Values: Automation, continuous learning, family security, freedom of time
- Risk tolerance: Medium (invests time freely, cautious with capital)
- Deal breakers: Large upfront capital, legal risk, manual labor dependency

SUBJECT: {subject}
CONTEXT: {context}

Evaluate and return JSON:
{{
  "score": float (-1.0 to 1.0),
  "financial_impact": float (estimated $ impact),
  "time_cost_hours": float,
  "risk_level": "low|medium|high|very_high",
  "benefits": ["list of benefits"],
  "risks": ["list of risks"],
  "recommendation": "clear recommendation",
  "knowledge_domains": ["relevant domains"]
}}"""

        try:
            result = await self._llm.complete(
                system="You are an objective advisor evaluating if decisions serve Yohan's interests. Return only JSON.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="default",
                temperature=0.3,
                max_tokens=1024,
            )
            import json
            text = result.strip()
            if "```" in text:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                text = text[start:end].strip()
            data = json.loads(text)

            score = float(data.get("score", 0))
            score = max(-1.0, min(1.0, score))

            if score >= 0.5:
                verdict = Verdict.STRONGLY_ALIGNED
            elif score >= 0.2:
                verdict = Verdict.ALIGNED
            elif score >= -0.1:
                verdict = Verdict.NEUTRAL
            elif score >= -0.4:
                verdict = Verdict.MISALIGNED
            else:
                verdict = Verdict.STRONGLY_MISALIGNED

            try:
                rl = RiskLevel(data.get("risk_level", "medium"))
            except ValueError:
                rl = RiskLevel.MEDIUM

            assessment = InterestAssessment(
                subject=subject,
                verdict=verdict,
                score=score,
                financial_impact=float(data.get("financial_impact", 0)),
                time_cost_hours=float(data.get("time_cost_hours", 0)),
                risk_level=rl,
                reasoning=data.get("recommendation", ""),
                benefits=data.get("benefits", []),
                risks=data.get("risks", []),
                recommendation=data.get("recommendation", ""),
                knowledge_domains=data.get("knowledge_domains", []),
            )
            self._assessment_history.append(assessment)
            return assessment
        except Exception as e:
            logger.error("LLM interest assessment failed: %s", e)
            return self.assess(subject, context)

    def get_history(self, limit: int = 20) -> list[InterestAssessment]:
        return list(reversed(self._assessment_history[-limit:]))

    def stats(self) -> dict[str, Any]:
        total = len(self._assessment_history)
        if not total:
            return {"total_assessments": 0, "avg_score": 0, "aligned_pct": 0}
        aligned = sum(
            1 for a in self._assessment_history
            if a.verdict in (Verdict.STRONGLY_ALIGNED, Verdict.ALIGNED)
        )
        avg_score = sum(a.score for a in self._assessment_history) / total
        return {
            "total_assessments": total,
            "avg_score": round(avg_score, 3),
            "aligned_pct": round(aligned / total * 100, 1),
            "strongly_aligned": sum(1 for a in self._assessment_history if a.verdict == Verdict.STRONGLY_ALIGNED),
            "aligned": sum(1 for a in self._assessment_history if a.verdict == Verdict.ALIGNED),
            "neutral": sum(1 for a in self._assessment_history if a.verdict == Verdict.NEUTRAL),
            "misaligned": sum(1 for a in self._assessment_history if a.verdict == Verdict.MISALIGNED),
        }
