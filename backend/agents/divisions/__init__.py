"""
Agent Civilization Divisions — 210 specialized agents across 10 divisions.

Each division file defines agents with 4-6 actionable capabilities
that map to real tools via the prompt_builder's CAPABILITY_TOOLS dict.
"""

from backend.agents.divisions.strategy import STRATEGY_COUNCIL
from backend.agents.divisions.research import RESEARCH_DIVISION
from backend.agents.divisions.engineering import ENGINEERING_DIVISION
from backend.agents.divisions.data import DATA_DIVISION
from backend.agents.divisions.learning import LEARNING_DIVISION
from backend.agents.divisions.economic import ECONOMIC_ENGINE
from backend.agents.divisions.content import CONTENT_ENGINE
from backend.agents.divisions.automation import AUTOMATION_ENGINE
from backend.agents.divisions.infrastructure import INFRASTRUCTURE_OPS
from backend.agents.divisions.governance import GOVERNANCE_SAFETY

ALL_DIVISIONS: dict[str, list] = {
    "Strategy Council": STRATEGY_COUNCIL,
    "Research Division": RESEARCH_DIVISION,
    "Engineering Division": ENGINEERING_DIVISION,
    "Data & Memory Division": DATA_DIVISION,
    "Learning & Improvement": LEARNING_DIVISION,
    "Economic Engine": ECONOMIC_ENGINE,
    "Content Network": CONTENT_ENGINE,
    "Automation Business": AUTOMATION_ENGINE,
    "Infrastructure Operations": INFRASTRUCTURE_OPS,
    "Governance & Safety": GOVERNANCE_SAFETY,
}

__all__ = [
    "STRATEGY_COUNCIL", "RESEARCH_DIVISION", "ENGINEERING_DIVISION",
    "DATA_DIVISION", "LEARNING_DIVISION", "ECONOMIC_ENGINE",
    "CONTENT_ENGINE", "AUTOMATION_ENGINE", "INFRASTRUCTURE_OPS",
    "GOVERNANCE_SAFETY", "ALL_DIVISIONS",
]
