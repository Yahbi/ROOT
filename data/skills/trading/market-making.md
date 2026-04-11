---
name: Market Making
description: Capture bid-ask spreads while managing inventory risk using quantitative models
version: "1.0.0"
author: ROOT
tags: [trading, market-making, liquidity, spread, inventory]
platforms: [all]
---

# Market Making

Profit from providing liquidity by continuously quoting bid and ask prices while managing inventory exposure.

## Core Mechanics

- **Profit source**: Bid-ask spread capture (buy at bid, sell at ask)
- **Revenue per round-trip**: `spread - 2 * fees - slippage`
- **Inventory risk**: Holding unhedged positions exposes you to directional moves
- **Adverse selection**: Informed traders pick off stale quotes; the primary cost of market making

## Avellaneda-Stoikov Model

The optimal quoting framework for inventory-aware market makers:

- **Reservation price**: `r(s, q, t) = s - q * gamma * sigma^2 * (T - t)`
  - s = mid price, q = inventory, gamma = risk aversion, sigma = volatility, T = horizon
- **Optimal spread**: `delta = gamma * sigma^2 * (T - t) + (2/gamma) * ln(1 + gamma/k)`
  - k = order arrival intensity parameter
- **Key insight**: Skew quotes away from inventory — if long, lower ask to offload; if short, raise bid
- Inventory penalty increases with time-to-horizon and volatility

## Quote Placement Strategy

- **Symmetric quotes**: Place bid and ask equidistant from mid (neutral inventory)
- **Skewed quotes**: Shift toward reducing inventory (asymmetric distances from mid)
- **Layered quotes**: Multiple levels at increasing distance for partial fills at better prices
- **Spread floor**: Never quote tighter than `2 * fee + minimum_profit_threshold`
- **Queue priority**: Place orders early in the book; time priority matters on FIFO venues

## Inventory Management

- **Hard limits**: Max inventory = `portfolio_value * max_exposure_pct` (typically 5-15%)
- **Soft limits**: Begin aggressive offloading at 50% of hard limit
- **Hedging**: Delta-hedge accumulated inventory with correlated instruments or futures
- **Mean reversion assumption**: Inventory naturally cycles; set half-life target < 5 minutes for HFT
- **EOD flatten**: Reduce positions before market close to avoid overnight gap risk

## Adverse Selection Defense

- **Toxicity metrics**: Track VPIN (Volume-Synchronized Probability of Informed Trading)
- **Cancel-to-fill ratio**: High ratio suggests you are being adversely selected
- **Widen spreads** when: volatility spikes, news events, order flow imbalance > 70%
- **Pull quotes** when: VPIN > 0.7, large sweep detected, spread inverts
- **Fade detection**: Monitor for large hidden orders that signal informed flow

## Risk Controls

- Max loss per day: 2x average daily revenue; auto-halt if breached
- Position limits: per-symbol and aggregate; hard-coded circuit breakers
- Latency monitoring: stale quotes in fast markets are toxic; kill switch at >10ms delay
- P&L attribution: separate spread capture, inventory P&L, and hedging costs daily
