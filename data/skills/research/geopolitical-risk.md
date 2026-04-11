---
name: Geopolitical Risk Assessment
description: Country risk scoring, sanctions impact analysis, and trade war scenario modeling for investment decisions
version: "1.0.0"
author: ROOT
tags: [research, geopolitical, risk, sanctions, macro, country-risk]
platforms: [all]
---

# Geopolitical Risk Assessment

Quantify and hedge geopolitical risks that create asymmetric market impacts, from sanctions and trade wars to regime changes and armed conflicts.

## Country Risk Scoring Framework

### Quantitative Components (0-100 scale)
- **Political stability** (20%): Government stability index, regime type, succession risk, protest frequency
- **Economic fundamentals** (20%): Debt/GDP, current account, FX reserves / import months, inflation trajectory
- **Institutional quality** (15%): Rule of law, corruption perception, contract enforcement, judicial independence
- **Security risk** (15%): Conflict intensity, terrorism index, military spending / GDP, border disputes
- **Financial openness** (15%): Capital controls, FX regime, banking system health, sovereign CDS spread
- **Contagion exposure** (15%): Trade dependency concentration, regional conflict spillover, alliance obligations

### Risk Tiers
| Score | Tier | Investment Approach |
|-------|------|-------------------|
| 80-100 | Low Risk | Full allocation, standard hedging |
| 60-79 | Moderate | Reduced allocation, FX hedged |
| 40-59 | Elevated | Tactical only, strict position limits |
| 20-39 | High | Event-driven only, options-based exposure |
| 0-19 | Critical | No direct exposure; monitor for contagion |

## Sanctions Impact Analysis

- **Primary sanctions**: Direct prohibitions on transacting with sanctioned entities; check OFAC SDN list
- **Secondary sanctions**: Penalties for third parties dealing with sanctioned entities; broader impact
- **Sectoral sanctions**: Target specific industries (energy, defense, finance) rather than entire country
- **Impact assessment**: Map sanctioned entity through supply chain; identify affected revenue streams
- **Compliance risk**: Screen portfolio holdings against OFAC, EU, UK sanctions lists; automate daily
- **Market impact**: Sanctions announcement typically moves affected assets 5-20% within 48 hours
- **Evasion vectors**: Monitor ship-to-ship transfers, front companies, crypto flows for sanctions circumvention

## Trade War Scenario Modeling

### Tariff Impact Framework
- **Direct cost**: `tariff_impact = import_value * tariff_rate * (1 - pass_through_rate)`
- **Pass-through**: Consumer goods ~50-70% pass-through; intermediate goods ~30-50%; commodities ~80-100%
- **Supply chain rerouting**: Tariff avoidance via third countries; adds 2-5% cost but circumvents duties
- **Retaliation modeling**: Tit-for-tat escalation; model 3 scenarios (de-escalation, status quo, full escalation)

### Scenario Construction
1. **Base case** (50% probability): Current tariffs maintained; no escalation; markets range-bound
2. **Escalation** (25%): Additional tariff rounds; technology restrictions; supply chain decoupling
3. **Resolution** (25%): Partial rollback; trade deal; risk asset rally
4. **Portfolio impact**: Calculate P&L under each scenario; weight by probability for expected outcome

## Event-Driven Geopolitical Trading

- **Conflict premium**: Oil +$5-15/bbl for Middle East escalation; gold +3-5% for any major conflict
- **Safe haven flows**: USD, JPY, CHF, gold, US Treasuries benefit from risk-off geopolitical events
- **Emerging market contagion**: EM sell-off spreads indiscriminately; cherry-pick unaffected quality EM after panic
- **Election risk**: Position for policy change 3-6 months before election; hedge with currency options
- **Regime change**: Monitor protest intensity, military positioning, elite defections as leading indicators

## Intelligence Sources

| Source | Type | Latency | Reliability |
|--------|------|---------|-------------|
| GDELT Project | Event data (conflicts, protests) | Real-time | Medium (noisy) |
| ACLED | Armed conflict data | Weekly | High |
| Caldara-Iacoviello GPR Index | Text-based geopolitical risk | Monthly | High |
| Political risk consultancies | Expert analysis | As published | High (costly) |
| Satellite imagery | Military/economic activity | Daily | High |
| Social media / OSINT | Ground truth, early signals | Real-time | Low (unverified) |

## Risk Management

- **Geographic diversification**: Max 15% portfolio exposure to any single country; 30% to any region
- **Currency hedging**: Hedge 100% of FX exposure in elevated-risk countries; use options for tail protection
- **Liquidity buffer**: Hold 5-10% extra cash when geopolitical risk index elevated above 80th percentile
- **Scenario sizing**: Size positions so worst-case geopolitical scenario loses < 3% of portfolio
- **Rapid response plan**: Pre-define exit triggers (sanctions, conflict, coup); execute within hours, not days
- **Correlation spike**: During geopolitical crises, correlations go to 1; diversification benefit disappears temporarily
