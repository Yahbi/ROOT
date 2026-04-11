---
name: Event-Driven Trading
description: Capture alpha from corporate events — earnings, M&A, spin-offs, restructurings
version: "1.0.0"
author: ROOT
tags: [trading, event-driven, earnings, M&A, catalyst, special-situations]
platforms: [all]
difficulty: advanced
---

# Event-Driven Trading

Trade corporate events where market prices don't fully reflect the post-event value.
Alpha comes from: faster analysis, better probability estimation, or superior structure.

## Event Categories

| Event | Edge | Typical Timeframe |
|-------|------|------------------|
| Earnings surprises | Drift after beat/miss | 1-5 days |
| M&A announcements | Deal spread arb | Weeks to months |
| Spin-offs | Neglect premium on child | 6-18 months |
| Index inclusions | Forced buying creates demand | 1-30 days |
| Activist campaigns | Value unlock catalyst | 6-24 months |
| Insider buying | Management conviction signal | 1-6 months |
| Short squeeze setups | Gamma/short covering | Days to weeks |

## Earnings Momentum (Post-Earnings Drift)

### Setup
1. Screen for earnings surprise > 10% above consensus EPS
2. Revenue beat required (not just EPS from cost-cutting)
3. Guidance raised for next quarter
4. Analyst upgrades within 24 hours

### Execution
```
Entry: Open of day after earnings announcement
Exit: 5-20 days post-earnings (drift period)
Position size: 1-3% of portfolio
Stop: -5% from entry (no drift = thesis wrong)
```

### Short Side (Earnings Miss)
- Revenue miss more predictive than EPS miss
- Lowered guidance = more powerful bearish signal
- Avoid shorting cheap stocks — high short-interest bounce risk

## Merger Arbitrage

### Deal Spread Calculation
```
Deal spread = (offer price - current price) / current price * (365 / days_to_close)
Example: Offer $50, current $48, 90 days to close
Annualized spread = ($50 - $48) / $48 * (365 / 90) = 16.9% annualized
```

### Risk Assessment Framework
| Factor | Low Risk | High Risk |
|--------|----------|-----------|
| Deal type | All-cash | Stock-for-stock |
| Regulatory approval | Minimal overlap | DOJ/FTC scrutiny |
| Financing | Committed bank debt | Contingent financing |
| Target sentiment | Board recommends | Hostile bid |
| Deal premium | > 30% | < 15% |

### Merger Arb Position Sizing
- Maximum 3% per deal (single deal break can cost 15-25%)
- Diversify across minimum 10 deals
- Never over-leverage — forced selling during deal break is devastating
- Hedge with index shorts when overall M&A spreads are tight

## Spin-Off Strategy

Spin-offs systematically outperform for 12-18 months post-separation because:
- Index funds sell the smaller child company (forced seller = mispricing)
- Management incentivized with new equity grants in child
- Child company runs leaner without parent bureaucracy

### Playbook
1. Identify upcoming spin-offs from SEC Form 10-12B filings
2. Hold parent stock through spin record date to receive child shares
3. Sell parent shares immediately after spin (often weakens)
4. Hold child for 6-18 months (historical outperformance window)
5. Track insider ownership — CEO taking large stake = bullish signal

## Index Inclusion Trade

When a stock is added to an index (S&P 500, Russell 2000):
- Passive funds must buy it before the effective date
- Announcement to addition date: typically 7-10 business days
- Price pressure is predictable and front-runnable

```
Strategy:
  - Buy stock immediately after S&P 500 addition announcement
  - Sell on effective inclusion date (peak of forced buying)
  - Expected edge: 2-5% over 5-10 day window
  - Risk: Stock already priced in by fast money
```

## Insider Buying Signal

SEC Form 4 filed within 2 days of transaction:
- **Bullish signals**: CEO/CFO buying in open market at current prices; multiple insiders buying simultaneously
- **Bearish signals**: Insider selling (ambiguous — could be diversification)
- **Strongest signal**: Insider buying after stock down 20%+ (conviction buy)
- **Weak signal**: Small purchases by junior employees, option exercises (mandatory)

## Risk Management Framework

```
Per-event position: 1-3% of portfolio
Maximum event exposure: 20% of portfolio
Loss stop: -7% on any single event position
Earnings: Never hold through earnings without options hedge
Catalyst date tracking: Know exit timeline before entry
```

## Screening Tools

1. Earnings: EPS/revenue surprise screeners (e.g., Estimize, Bloomberg consensus)
2. M&A: Deal tracker (Bloomberg MA, FactSet)
3. Spin-offs: SEC Edgar Form 10-12B filings
4. Insider buying: SEC EDGAR Form 4, InsiderInsights.com
5. Index changes: MSCI/S&P 500 constituent change announcements
