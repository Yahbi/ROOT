---
name: Dispersion Trading
description: Trade index vs single-stock volatility through correlation and variance swap strategies
version: "1.0.0"
author: ROOT
tags: [strategy, dispersion, volatility, correlation, options, variance]
platforms: [all]
---

# Dispersion Trading

Exploit the persistent overpricing of index volatility relative to constituent volatility by trading the correlation risk premium.

## Core Concept

- **Observation**: Index implied vol is systematically higher than realized vol from constituents
- **Reason**: Index options embed a correlation risk premium — hedgers overpay for portfolio protection
- **Trade**: Short index volatility + long single-stock volatility = short correlation
- **P&L driver**: `P&L ~ (implied_correlation - realized_correlation) * vega_notional`
- **Historical edge**: Implied correlation exceeds realized by 5-15 points on average (persistent premium)

## Index vs Single-Stock Volatility Relationship

- **Index vol formula**: `sigma_index^2 = SUM(w_i^2 * sigma_i^2) + SUM(w_i * w_j * rho_ij * sigma_i * sigma_j)`
- **Implied correlation**: `rho_implied = (sigma_index^2 - SUM(w_i^2 * sigma_i^2)) / SUM(w_i * w_j * sigma_i * sigma_j)`
- **Dispersion P&L**: Positive when realized correlation < implied correlation (most of the time)
- **Correlation spike risk**: During crashes, correlations go to ~1.0; dispersion trade loses significantly
- **Typical P&L profile**: Many small wins, occasional large loss (short convexity in correlation)

## Implementation Methods

### Variance Swap Dispersion
- **Short index variance swap**: Pay fixed, receive realized index variance
- **Long constituent variance swaps**: Receive fixed, pay realized single-stock variance
- **Weighting**: Match vega notional so that net position is pure correlation bet
- **Advantage**: Clean exposure to correlation; no delta hedging required

### Options-Based Dispersion
- **Short index straddle/strangle**: Sell ATM or 25-delta options on SPX
- **Long constituent straddles**: Buy ATM options on top 20-30 index constituents
- **Delta hedge**: All positions delta-hedged to isolate pure volatility exposure
- **Practical**: More liquid than variance swaps; easier to adjust

## Trade Sizing and Weighting

- **Vega matching**: Index short vega = sum of constituent long vega (weighted by index weight)
- **Constituent selection**: Top 20-30 stocks by index weight (covers 50-70% of index)
- **Weight formula**: `vega_stock_i = w_i * vega_index / SUM(w_j for selected)` where w_i = index weight
- **Tenor**: 1-3 months optimal; correlation premium highest in short-dated options
- **Roll**: Close at 2 weeks to expiry; re-establish new position monthly

## Correlation Risk Premium Measurement

- **CBOE Implied Correlation Index (ICJ/JCJ)**: Tracks SPX implied correlation; entry when > 70th percentile
- **Correlation spread**: `implied_corr - realized_corr_60day`; trade when spread > 10 points
- **Term structure**: Short-dated implied correlation usually > long-dated; front-month premium richest
- **Seasonal pattern**: Correlation tends to rise into year-end and Q1 earnings; plan timing accordingly

## Risk Management

- **Max loss scenario**: Correlation spike to 0.95+ (market crash); size position so max loss < 5% of portfolio
- **Tail hedge**: Buy far OTM SPX puts (5-10% OTM) to cap crash losses; costs 1-2% of premium annually
- **Vega imbalance monitoring**: If net vega exceeds +/-5% of target, rebalance immediately
- **Earnings risk**: Single-stock vol spikes around earnings; stagger constituents to avoid cluster
- **Correlation regime**: Do not initiate new positions when VIX > 30 (correlations already elevated)
- **Drawdown stop**: Close full position if P&L exceeds -3% of portfolio; re-enter after correlation normalizes
