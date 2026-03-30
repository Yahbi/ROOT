---
name: Options Strategies
description: Core options strategies for income, hedging, and directional trades
version: "1.0.0"
author: ROOT
tags: [trading, options, derivatives, hedging, income]
platforms: [all]
---

# Options Strategies

Executable options strategies for different market conditions and objectives.

## Income Strategies

### Covered Call
- **Setup**: Own 100 shares + sell 1 OTM call (30-45 DTE, 0.30 delta)
- **When**: Neutral to slightly bullish, want to generate income
- **Max profit**: Premium collected + (strike - entry) if assigned
- **Risk**: Stock drops — premium provides small buffer only
- **Management**: Roll up and out if stock rallies past strike

### Cash-Secured Put
- **Setup**: Sell 1 OTM put + hold cash equal to 100x strike price
- **When**: Bullish, willing to buy stock at strike price
- **Target**: Sell at 0.25-0.30 delta, 30-45 DTE
- **Management**: Roll down if stock drops; let expire if OTM at expiry

## Directional Strategies

### Bull Call Spread (Debit)
- **Setup**: Buy ATM call + sell OTM call (same expiry)
- **When**: Moderately bullish, want defined risk
- **Max profit**: Width of strikes minus premium paid
- **Target**: 60-90 DTE, exit at 50% max profit

### Bear Put Spread (Debit)
- **Setup**: Buy ATM put + sell OTM put (same expiry)
- **When**: Moderately bearish, want defined risk
- **Max profit**: Width of strikes minus premium paid

## Volatility Strategies

### Long Straddle
- **Setup**: Buy ATM call + ATM put (same strike, same expiry)
- **When**: Expect large move but direction uncertain (pre-earnings)
- **Breakeven**: Strike +/- total premium paid
- **Risk**: Time decay — need move within 1-2 weeks

### Iron Condor
- **Setup**: Sell OTM put spread + sell OTM call spread
- **When**: Low volatility expected, range-bound market
- **Target**: Collect 1/3 of wing width in premium, 30-45 DTE
- **Management**: Close at 50% profit; adjust if tested

## Risk Rules

- Never risk more than 2% of portfolio on a single options trade
- Always use defined-risk strategies (spreads) over naked positions
- Close positions at 21 DTE to avoid gamma risk acceleration
- Size based on max loss, not notional exposure
