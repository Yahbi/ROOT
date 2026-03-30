---
name: Event-Driven Trading
description: Trade around earnings, FDA decisions, IPOs, and other catalysts
version: "1.0.0"
author: ROOT
tags: [strategy, event-driven, catalysts, earnings, biotech]
platforms: [all]
---

# Event-Driven Trading Strategy

Exploit predictable price dislocations around corporate and regulatory events.

## Event Types and Playbooks

### Earnings Announcements
- **Pre-earnings drift**: stocks with positive estimate revisions drift up before report
- **Post-earnings drift**: surprises take 60 days to fully price in (PEAD)
- **Volatility play**: sell straddles if implied vol > 1.5x historical realized vol
- **Entry**: 3-5 days before (drift) or 1-2 days after (PEAD)

### FDA Decisions (Biotech)
- **PDUFA dates**: FDA action dates are public and predictable
- **Binary outcome**: approval = +30-100%, rejection = -40-70%
- **Strategy**: risk-defined options (buy call spread or put spread, not stock)
- **Size**: max 0.5% of portfolio per FDA play (binary risk)

### IPO Trading
- **Lock-up expiry**: 90-180 days after IPO, insider selling pressure
- **Strategy**: SHORT into lock-up expiry if stock is >50% above IPO price
- **IPO base breakout**: after 3+ months of basing, buy breakout above IPO range
- **Avoid**: first 2 weeks of trading (too volatile, too thin)

### M&A and Spin-offs
- **Merger arbitrage**: buy target at discount to deal price, earn the spread
- **Spin-off alpha**: parent company shareholders dump spin-off (forced selling)
- **Entry**: buy spin-off 2-4 weeks after separation (selling exhaustion)

### Index Rebalancing
- **Additions**: stocks added to S&P 500 see 3-5% forced buying
- **Deletions**: removed stocks see 3-5% forced selling
- **Strategy**: buy additions on announcement, hold through effective date

## Event Calendar Management

1. Track upcoming events in database: date, type, affected tickers, expected impact
2. Set alerts for T-5, T-1, T+0, T+1 relative to event
3. Size all event trades based on event type risk profile
4. Never stack more than 3 event trades in same week

## Risk Controls

- **Max loss per event**: 1% of portfolio
- **Correlation check**: avoid multiple biotech FDA plays simultaneously
- **Always use defined-risk instruments** for binary events (options spreads)
- **Track hit rate by event type**: drop any category below 45% success rate
- **Post-event review**: log outcome and refine entry/exit rules quarterly
