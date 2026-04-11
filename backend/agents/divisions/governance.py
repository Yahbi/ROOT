"""Governance & Safety — 15 oversight, compliance, and safety agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


GOVERNANCE_SAFETY: list[AgentProfile] = [
    AgentProfile(
        id="alignment_monitor", name="Alignment Monitor",
        role="Alignment", tier=1, connector_type="internal",
        description="Ensures system actions align with Yohan's values, goals, and directives",
        capabilities=[
            _cap("compliance", "Verify actions comply with stated values and goals"),
            _cap("anomaly_detection", "Detect behavioral drift from alignment targets"),
            _cap("decision_making", "Evaluate decisions against alignment criteria"),
            _cap("risk_assessment", "Assess alignment risk of proposed actions"),
        ],
    ),
    AgentProfile(
        id="ethics_monitor", name="Ethics Monitor",
        role="Ethics", tier=1, connector_type="internal",
        description="Evaluates ethical implications of system decisions and outputs",
        capabilities=[
            _cap("compliance", "Enforce ethical guidelines and policies"),
            _cap("risk_assessment", "Assess ethical risk of proposed actions"),
            _cap("anomaly_detection", "Flag ethically questionable outputs"),
            _cap("decision_making", "Provide ethical guidance on edge cases"),
        ],
    ),
    AgentProfile(
        id="security_auditor", name="Security Auditor",
        role="Security Audit", tier=1, connector_type="internal",
        description="Audits system security, identifies vulnerabilities, and enforces hardening",
        capabilities=[
            _cap("security_audit", "Run security audits on code and infrastructure"),
            _cap("anomaly_detection", "Detect unauthorized access and suspicious activity"),
            _cap("system_integrity", "Verify system configurations against baselines"),
            _cap("compliance", "Ensure adherence to security policies and standards"),
            _cap("health_monitoring", "Monitor security posture and incident metrics"),
        ],
    ),
    AgentProfile(
        id="hallucination_detector", name="Hallucination Detector",
        role="Truth Verification", tier=1, connector_type="internal",
        description="Detects and flags potential hallucinations in AI-generated outputs",
        capabilities=[
            _cap("anomaly_detection", "Identify outputs inconsistent with known facts"),
            _cap("compliance", "Enforce factual accuracy standards"),
            _cap("risk_assessment", "Score hallucination risk of generated content"),
            _cap("decision_making", "Determine whether outputs need human review"),
        ],
    ),
    AgentProfile(
        id="cost_controller", name="Cost Controller",
        role="Cost Control", tier=1, connector_type="internal",
        description="Monitors and controls operational costs across all systems",
        capabilities=[
            _cap("cost_optimization", "Identify and enforce cost reduction measures"),
            _cap("anomaly_detection", "Alert on unexpected cost spikes"),
            _cap("risk_assessment", "Assess financial impact of proposed actions"),
            _cap("health_monitoring", "Track spend against budgets in real time"),
        ],
    ),
    AgentProfile(
        id="financial_risk", name="Financial Risk Monitor",
        role="Financial Risk", tier=1, connector_type="internal",
        description="Monitors financial risk exposure and triggers protective alerts",
        capabilities=[
            _cap("risk_assessment", "Quantify financial risk across portfolios"),
            _cap("risk_modeling", "Model worst-case and expected loss scenarios"),
            _cap("anomaly_detection", "Detect abnormal trading and spending patterns"),
            _cap("health_monitoring", "Track risk metrics and exposure limits"),
        ],
    ),
    AgentProfile(
        id="compliance_agent", name="Compliance Agent",
        role="Compliance", tier=1, connector_type="internal",
        description="Ensures compliance with regulations, licenses, and internal policies",
        capabilities=[
            _cap("compliance", "Audit operations against regulatory requirements"),
            _cap("security_audit", "Review data handling and privacy practices"),
            _cap("risk_assessment", "Assess compliance risk of new initiatives"),
            _cap("decision_making", "Advise on regulatory implications of actions"),
        ],
    ),
    AgentProfile(
        id="integrity_monitor", name="System Integrity Monitor",
        role="System Integrity", tier=1, connector_type="internal",
        description="Monitors system integrity and detects unauthorized modifications",
        capabilities=[
            _cap("system_integrity", "Verify checksums and configuration baselines"),
            _cap("anomaly_detection", "Detect unauthorized file and config changes"),
            _cap("health_monitoring", "Continuously monitor system state for drift"),
            _cap("security_audit", "Audit system changes against approval records"),
        ],
    ),
    AgentProfile(
        id="decision_auditor", name="Decision Audit Agent",
        role="Decision Audit", tier=1, connector_type="internal",
        description="Audits major decisions for quality, bias, and sound reasoning",
        capabilities=[
            _cap("decision_making", "Evaluate decision quality and reasoning chains"),
            _cap("risk_assessment", "Assess risk of past and proposed decisions"),
            _cap("anomaly_detection", "Flag decisions deviating from established patterns"),
            _cap("compliance", "Verify decisions follow governance protocols"),
        ],
    ),
    AgentProfile(
        id="failure_recovery", name="Failure Recovery Agent",
        role="Recovery", tier=1, connector_type="internal",
        description="Handles system failures and executes automated recovery procedures",
        capabilities=[
            _cap("health_monitoring", "Detect failures and degraded components"),
            _cap("system_integrity", "Restore systems to known-good state"),
            _cap("anomaly_detection", "Identify root cause of failures"),
            _cap("risk_assessment", "Assess blast radius and recovery priority"),
            _cap("decision_making", "Decide between auto-recovery and escalation"),
        ],
    ),
    AgentProfile(
        id="bias_detector", name="Bias Detector",
        role="Bias Detection", tier=1, connector_type="internal",
        description="Detects statistical and cognitive biases in AI outputs, decisions, and data pipelines",
        capabilities=[
            _cap("anomaly_detection", "Detect demographic, selection, and confirmation biases"),
            _cap("statistical_analysis", "Apply fairness metrics across protected groups"),
            _cap("compliance", "Enforce bias thresholds mandated by policy or regulation"),
            _cap("risk_assessment", "Assess downstream harm potential of detected biases"),
            _cap("evaluation", "Evaluate model outputs for disparate impact and fairness"),
        ],
        metadata={"priority": 1},
    ),
    AgentProfile(
        id="privacy_auditor", name="Privacy Auditor",
        role="Privacy Audit", tier=1, connector_type="internal",
        description="Audits data handling practices for privacy compliance with GDPR, CCPA, and internal policies",
        capabilities=[
            _cap("security_audit", "Audit data collection, storage, and processing for PII exposure"),
            _cap("compliance", "Verify adherence to GDPR, CCPA, and relevant privacy regulations"),
            _cap("anomaly_detection", "Detect unauthorized PII access and retention violations"),
            _cap("risk_assessment", "Assess privacy risk of new features and data flows"),
            _cap("decision_making", "Advise on privacy-by-design implementation requirements"),
        ],
        metadata={"priority": 1},
    ),
    AgentProfile(
        id="compliance_checker", name="Compliance Checker",
        role="Compliance Verification", tier=1, connector_type="internal",
        description="Continuously verifies system and operational compliance against regulatory and policy requirements",
        capabilities=[
            _cap("compliance", "Run automated compliance checks against defined control frameworks"),
            _cap("security_audit", "Review configurations for SOC2, ISO 27001, and HIPAA controls"),
            _cap("anomaly_detection", "Flag compliance drift and policy violations"),
            _cap("risk_assessment", "Prioritize compliance gaps by regulatory exposure"),
            _cap("decision_making", "Recommend remediation actions and escalation paths"),
        ],
        metadata={"priority": 1},
    ),
    AgentProfile(
        id="sla_monitor", name="SLA Monitor",
        role="SLA Monitoring", tier=1, connector_type="internal",
        description="Monitors SLA compliance across all services and escalates at-risk commitments before breach",
        capabilities=[
            _cap("health_monitoring", "Track SLA metrics in real time across all service tiers"),
            _cap("monitoring", "Measure availability, latency, and error rate against SLA targets"),
            _cap("system_reliability", "Enforce error budgets and trigger burn-rate alerts"),
            _cap("risk_assessment", "Forecast SLA breach risk based on current burn rates"),
            _cap("decision_making", "Trigger escalation when SLA breach is imminent"),
        ],
        metadata={"priority": 1},
    ),
    AgentProfile(
        id="incident_reporter", name="Incident Reporter",
        role="Incident Reporting", tier=1, connector_type="internal",
        description="Documents incidents, coordinates post-mortems, and tracks corrective action closure",
        capabilities=[
            _cap("health_monitoring", "Detect and classify incident severity during events"),
            _cap("decision_making", "Coordinate incident response team assignment and escalation"),
            _cap("compliance", "Ensure incident documentation meets regulatory and contractual requirements"),
            _cap("risk_assessment", "Assess incident impact on SLAs, data, and reputation"),
            _cap("knowledge_expansion", "Convert post-mortem findings into reusable runbooks and lessons"),
        ],
        metadata={"priority": 1},
    ),
]
