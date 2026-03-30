---
name: Mean Reversion (Enhanced)
description: Advanced mean reversion strategies with regime detection and adaptive parameters
version: "1.0.0"
author: ROOT
tags: [strategy, mean-reversion, statistical, adaptive]
platforms: [all]
---

# Enhanced Mean Reversion Strategy

Trade the tendency of prices to revert to statistical averages, with regime awareness.

## Core Signals

### Bollinger Band Reversion
- Compute 20-day SMA and 2-standard-deviation bands
- BUY when price closes below lower band and RSI(14) < 30
- SELL when price closes above upper band and RSI(14) > 70
- Exit at middle band (20-day SMA)

### Z-Score Reversion
- z = (price - SMA_50) / rolling_std_50
- Entry: z < -2.0 (buy) or z > +2.0 (sell)
- Exit: z returns to +/- 0.5
- Stop: z exceeds +/- 3.5 (regime break)

### RSI Divergence
- Price makes lower low but RSI makes higher low = bullish divergence
- Price makes higher high but RSI makes lower high = bearish divergence
- Combine with mean-reversion levels for higher probability entries

## Regime Detection (Critical Enhancement)

Mean reversion fails in trending markets. Detect regime first:

| Indicator | Mean-Reverting Regime | Trending Regime |
|-----------|----------------------|-----------------|
| ADX(14) | < 20 | > 30 |
| Hurst exponent | < 0.5 | > 0.5 |
| Bollinger bandwidth | Narrowing | Expanding |
| VIX term structure | Contango (normal) | Backwardation (stress) |

**Rule**: only trade mean-reversion when ADX < 25 AND Hurst < 0.5.

## Adaptive Parameters

- **Lookback period**: use 20-day in high-vol, 50-day in low-vol environments
- **Entry threshold**: z-score 2.0 in normal vol, 2.5 in high vol
- **Position size**: inversely proportional to recent realized volatility
- **Hold period**: cap at 10 days — if not reverted, close and reassess

## Risk Management

- Max 5 concurrent mean-reversion positions
- Per-position risk: 1% of equity
- Daily loss limit: 3% — halt all mean-reversion trades
- Never fight the trend: if 50-day SMA slopes strongly, skip the trade
- Avoid mean-reversion 3 days before and after earnings

## Expected Characteristics

- **Win rate**: 60-70% (high hit rate, moderate payoff)
- **Avg hold period**: 3-7 trading days
- **Sharpe ratio**: 0.8-1.2 (works best in range-bound markets)
- **Worst regime**: strong trending markets (momentum crash = MR windfall)
