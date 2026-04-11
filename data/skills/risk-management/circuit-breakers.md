---
name: Circuit Breakers
description: Automated trading halts and volatility-based protective mechanisms
version: "1.0.0"
author: ROOT
tags: [risk-management, circuit-breakers, volatility, automated-halts]
platforms: [all]
---

# Trading Circuit Breakers

Automated mechanisms that halt or reduce trading activity when predefined thresholds are breached.

## Account-Level Circuit Breakers

### Daily Loss Limit
- **Trigger**: Daily P&L falls below -3% of account equity
- **Action**: Close all positions, disable new orders for remainder of day
- **Reset**: Automatically at market open next trading day

### Weekly Loss Limit
- **Trigger**: Weekly P&L falls below -5% of account equity
- **Action**: Flatten all positions, reduce next week's size by 50%
- **Reset**: Monday open with reduced sizing

### Consecutive Loss Limit
- **Trigger**: 5 consecutive losing trades
- **Action**: Pause trading for 24 hours, review strategy alignment
- **Reset**: After review and confirmation that losses are within expected variance

## Volatility-Based Halts

### VIX-Based Rules
| VIX Level | Action |
|-----------|--------|
| < 15 | Normal trading, full position sizes |
| 15-25 | Reduce position sizes by 25% |
| 25-35 | Reduce by 50%, widen stops to 2x ATR |
| 35-50 | Defensive only — close longs, hold hedges |
| > 50 | No new positions — cash or short vol premium |

### Intraday Volatility
- If any position moves > 3x ATR in a single session, reassess immediately
- If portfolio moves > 2% intraday, halt new entries for 2 hours
- After gap opens > 2%, wait 30 minutes before any action (let price discover)

## Strategy-Level Circuit Breakers

### Drawdown from Strategy Peak
- If a single strategy draws down > 10% from its equity peak, reduce allocation by 50%
- If drawdown exceeds 20%, disable strategy and run diagnostics

### Win Rate Degradation
- Track rolling 50-trade win rate per strategy
- If win rate drops below (expected - 2 standard deviations), flag for review
- If below (expected - 3 SD), auto-disable and investigate regime change

## Implementation

1. Wire circuit breakers into the order management system (pre-trade check)
2. Every order must pass all active circuit breaker checks before submission
3. Log all circuit breaker triggers with timestamp, reason, and positions affected
4. Send notification (Telegram/Discord) on any trigger
5. Monthly review: adjust thresholds based on changing market conditions
6. Never allow manual override without explicit approval from governance

## Common Mistakes

- Setting limits too tight (triggered by normal variance, not real problems)
- Setting limits too loose (triggered only after catastrophic damage)
- Allowing manual overrides without accountability
- Not testing circuit breakers in simulation before live deployment
