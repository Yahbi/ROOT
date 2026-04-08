---
name: Algorithmic Execution
description: Minimize market impact using TWAP, VWAP, implementation shortfall, and iceberg order algorithms
version: "1.0.0"
author: ROOT
tags: [trading, execution, algorithms, TWAP, VWAP, market-impact]
platforms: [all]
---

# Algorithmic Execution

Optimize trade execution to minimize market impact and slippage when working large orders across fragmented venues.

## TWAP (Time-Weighted Average Price)

- **Logic**: Divide total order into equal slices executed at uniform time intervals
- **Slice size**: `quantity_per_slice = total_quantity / num_intervals`
- **Interval**: Typically 1-5 minutes; shorter for liquid names, longer for illiquid
- **Advantage**: Simple, predictable, minimal information leakage; good benchmark for small orders
- **Disadvantage**: Ignores volume patterns; executes same size during low-vol lunch as during high-vol open
- **Enhancement**: Add randomization (+/- 20% per slice) to reduce pattern detection by predatory algos

## VWAP (Volume-Weighted Average Price)

- **Logic**: Execute proportionally to historical intraday volume curve
- **Volume profile**: Use 20-day average volume-by-minute to predict intraday distribution
- **Participation rate**: `slice_size = predicted_volume_this_minute * participation_rate` (typically 5-20%)
- **Benchmark**: VWAP = `SUM(P_i * V_i) / SUM(V_i)` over execution window
- **Advantage**: Matches institutional benchmark; minimizes impact during low-volume periods
- **Risk**: If actual volume deviates from prediction, execution drifts from target; use adaptive VWAP

## Implementation Shortfall (IS)

- **Definition**: `IS = (execution_price - decision_price) * quantity`; total cost of trading
- **Components**: Market impact + timing cost + opportunity cost of unexecuted shares
- **Almgren-Chriss model**: Minimize `E[cost] + lambda * Var[cost]` where lambda = risk aversion
- **Optimal trajectory**: Front-load execution (aggressive) when risk aversion high; spread out when low
- **Urgency parameter**: High urgency = execute quickly (accept impact); low urgency = trade patiently
- **Adaptive IS**: Adjust execution speed based on real-time price movement and fill rates

## Iceberg Orders

- **Concept**: Display only a fraction of total order; replenish visible portion as it fills
- **Display ratio**: Typically 5-20% of total order; lower for more stealth
- **Replenishment logic**: Immediate refill exposes the iceberg; add 1-5 second random delay
- **Price adjustment**: Re-enter at same price or better; do not chase away from target
- **Detection defense**: Vary display size randomly (+/- 30%); occasionally skip replenishment
- **Venue selection**: Dark pools for maximum concealment; lit venues for price discovery

## Smart Order Routing (SOR)

- **Venue analysis**: Route to venue with best price, lowest fees, highest probability of fill
- **Maker/taker optimization**: Post passive orders on maker-maker venues (earn rebates); take on taker-friendly venues
- **Dark pool strategy**: Ping dark pools first for block fills (zero market impact); fall back to lit venues
- **Anti-gaming**: Randomize routing patterns; avoid predictable venue sequences
- **Latency budget**: Route to fastest venues for urgent orders; prioritize rebates for patient orders

## Market Impact Models

- **Square root law**: `impact = sigma * sqrt(Q / V)` where Q = order size, V = daily volume, sigma = volatility
- **Temporary impact**: Price displacement during execution; mean-reverts after completion
- **Permanent impact**: Information content of trade permanently shifts equilibrium price
- **Sizing rule**: Orders > 1% of daily volume require algorithmic execution; > 10% require multi-day
- **Cost estimate**: Total cost = `0.5 * spread + temporary_impact + permanent_impact + fees`

## Risk Management

- **Benchmark tracking**: Monitor real-time execution vs VWAP/TWAP benchmark; alert if deviation > 5bps
- **Toxicity detection**: If fills are consistently adverse (buying at highs, selling at lows), pause and reassess
- **Stale order protection**: Cancel unfilled orders after max time-in-force; do not let stale limits get swept
- **Circuit breaker**: Halt execution if price moves > 2% against during execution window
- **Post-trade analysis**: Compare execution cost vs pre-trade estimate; calibrate impact models monthly
