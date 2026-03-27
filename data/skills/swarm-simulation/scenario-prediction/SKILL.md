---
name: scenario-prediction
description: Run multi-agent swarm simulations to predict outcomes
version: 1.0.0
author: ROOT
tags: [simulation, prediction, swarm, miro]
platforms: [darwin, linux, win32]
---

# Scenario Prediction via Swarm Simulation

From MiRo swarm intelligence engine.

## When to Use
- Yohan wants to predict outcomes of a decision
- Market analysis or trend forecasting needed
- "What if" scenarios for business or personal planning
- Testing strategies before real-world deployment

## MiRo Workflow

1. **Seed Material** — Upload relevant context (news, data, docs)
2. **Ontology Generation** — LLM extracts entity types (Person, Org, Event)
3. **Graph Building** — Zep Cloud constructs knowledge graph
4. **Profile Generation** — Create agent personas from entities
5. **Config Tuning** — LLM sets simulation parameters
6. **Dual-Platform Sim** — Agents interact on simulated Twitter + Reddit
7. **Report Generation** — ReportAgent synthesizes predictions
8. **Interactive Dialog** — Chat with simulated entities

## Key Data Structures
- SimulationState: tracks status, entity/profile counts
- AgentAction: per-agent behavior with timestamp
- RoundSummary: aggregated actions per round
- Recent actions buffer: 50-item queue

## Integration with ROOT
- Delegate prediction tasks to MiRo connector
- Store predictions in memory with confidence scores
- Compare predictions to outcomes for calibration
- Feed calibration data back into reflection loop
