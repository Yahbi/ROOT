---
name: money-orchestration
category: trading
description: Multi-agent Strategy Council for wealth generation decisions
version: "1.0"
tags: [money, strategy, council, agents, wealth, revenue]
author: ROOT
platforms: [all]
---

# Money Orchestration — Strategy Council

## Purpose
Coordinate all agents (Trading Swarm, MiRo, HERMES, ASTRA) to collectively identify, evaluate, and prioritize money-making opportunities for Yohan.

## Process

### 1. Intelligence Gathering (Parallel)
Each agent searches its knowledge domain:
- **Trading Swarm**: Trading strategies, backtest results, market conditions
- **MiRo**: Scenario simulations, prediction accuracy, opinion models
- **HERMES**: Web research, data sources, automation opportunities
- **ASTRA**: Workflow patterns, coordination efficiency, worker utilization
- **ROOT**: Memory synthesis, historical patterns, user preferences

### 2. Opportunity Synthesis
Transform raw intelligence into scored opportunities:
- Assign `OpportunityType` (trading, SaaS, freelance, arbitrage, data product, AI product)
- Calculate `confidence_score` (0.0-1.0) from memory confidence + evidence count
- Estimate `monthly_revenue`, `capital_required`, `time_to_first_revenue`
- Identify `action_steps` (concrete next moves)

### 3. Ranking & Recommendation
- Sort by confidence score (descending)
- Apply risk-adjusted weighting
- Consider capital requirements vs. available resources
- Factor in time-to-revenue urgency

### 4. Memory & Evolution
- Store top 3 opportunities as goal memories
- Log session as evolution entry
- Track which opportunities are pursued and their outcomes

## Scoring Formula

```
final_score = confidence * 0.4 + (revenue_potential / max_revenue) * 0.3 + (1 - risk_factor) * 0.2 + speed_factor * 0.1
```

Where:
- `confidence`: Agent consensus (0-1)
- `revenue_potential`: Normalized estimated monthly revenue
- `risk_factor`: LOW=0.2, MEDIUM=0.4, HIGH=0.7, VERY_HIGH=0.9
- `speed_factor`: 1.0 - (days_to_revenue / 90), clamped 0-1

## Triggers
- Chat command: "make money", "council", "strategy council", "opportunities"
- API: `POST /api/money/council`
- Scheduled: Can run weekly for fresh recommendations
