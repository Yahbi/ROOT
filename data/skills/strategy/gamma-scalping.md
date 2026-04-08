---
name: Gamma Scalping
description: Delta-neutral options trading to harvest gamma exposure and trade the volatility surface
version: "1.0.0"
author: ROOT
tags: [strategy, options, gamma, delta-neutral, volatility]
platforms: [all]
---

# Gamma Scalping

Profit from realized volatility exceeding implied volatility by maintaining delta-neutral options positions and systematically rebalancing.

## Core Concept

- **Position**: Long options (calls or puts) + hedge with underlying to be delta-neutral
- **Gamma profit**: `P&L_gamma = 0.5 * Gamma * (Delta_S)^2` per rebalance; always positive for long gamma
- **Theta cost**: `P&L_theta = -Theta * Delta_t` per day; the cost of carrying the gamma position
- **Net P&L**: Profitable when `realized_vol > implied_vol` at time of entry
- **Edge**: You are long realized vol, short implied vol; earn the vol spread if RV > IV

## Delta-Neutral Construction

- **ATM straddle**: Buy ATM call + ATM put; highest gamma per dollar of premium
- **Delta hedge**: Sell `net_delta * 100` shares of underlying to flatten portfolio delta
- **Initial delta**: ATM straddle has near-zero delta; minor hedge usually needed
- **Greeks snapshot**: Record gamma, theta, vega at entry for P&L attribution

## Rebalancing Protocol

- **Threshold-based**: Rebalance when |portfolio_delta| exceeds threshold (e.g., 0.10 per contract)
- **Time-based**: Rebalance every N hours (e.g., every 2 hours or end of day)
- **Optimal frequency**: `f* = sigma / (2 * transaction_cost)` — balance gamma capture vs friction
- **Rebalance mechanics**: If delta = +0.15, sell 15 shares per contract; if delta = -0.15, buy 15 shares
- **Band adjustment**: Widen bands in low-vol (less gamma to capture); tighten in high-vol (more opportunity)

## Volatility Surface Trading

- **Skew trades**: Buy cheap wing options, sell expensive ATM; profit when skew normalizes
- **Term structure**: Buy short-dated (high gamma), sell long-dated (high vega) when vol term structure steep
- **Calendar spread gamma scalp**: Long front-month ATM (high gamma) vs short back-month ATM (high vega)
- **Vol surface arbitrage**: Identify mispricings between strikes/expirations using SABR or SVI models
- **Smile dynamics**: Sticky-strike vs sticky-delta; choose model based on regime for accurate hedging

## P&L Attribution

- **Gamma P&L**: `0.5 * Gamma * (realized_move)^2`; increases quadratically with move size
- **Theta P&L**: `-Theta * days_held`; linear time decay; largest for ATM short-dated options
- **Vega P&L**: `Vega * change_in_IV`; risk/reward from IV level shifts
- **Breakeven**: Daily gamma P&L must exceed theta; requires `daily_move > sqrt(2 * Theta / Gamma)`
- **Tracking**: Log each rebalance — delta before, shares traded, fill price, running gamma P&L

## Ideal Conditions

- **IV percentile < 30**: Options are cheap; more likely that realized vol will exceed implied
- **Upcoming catalyst**: Earnings, FOMC, macro events where realized vol may spike
- **Mean-reverting IV**: After extended low-vol period, gamma scalps benefit from vol expansion
- **High gamma names**: Biotech, meme stocks, event-driven situations; avoid low-vol utilities

## Risk Management

- **Max theta burn**: Limit daily theta to 0.1% of portfolio; exit if theta exceeds realized gamma P&L for 5+ days
- **Vega exposure**: Long gamma = long vega; if IV drops, position loses on vega even if gamma scalps are profitable
- **Expiration risk**: Gamma explodes near expiry for ATM options (pin risk); close 5+ days before expiry
- **Liquidity**: Only trade options with bid-ask spread < 5% of mid-price; wide spreads kill gamma scalping edge
- **Position limits**: Max 3% of portfolio in any single name's gamma exposure
