---
name: Pairs Correlation Strategy
description: Dynamic correlation tracking with regime-aware pair selection and z-score entry thresholds
version: "1.0.0"
author: ROOT
tags: [strategy, pairs, correlation, mean-reversion, quantitative]
platforms: [all]
---

# Pairs Correlation Strategy

Trade relative value between correlated instruments using dynamic correlation tracking and regime-adaptive entry signals.

## Dynamic Correlation Tracking

- **Rolling correlation**: `rho_t = corr(R_x, R_y)` over rolling window (60-120 days)
- **Exponential weighted**: `EWMA_corr` with halflife = 30 days; more responsive to recent correlation shifts
- **DCC-GARCH**: Dynamic Conditional Correlation model; captures time-varying correlations with volatility clustering
- **Correlation breakdown signal**: When 20-day corr drops > 0.3 below 120-day corr, relationship is stressed
- **Regime filter**: Only trade pairs with current correlation > 0.7 and 252-day average > 0.75

## Pair Selection Methodology

1. **Universe screening**: Liquid stocks (ADV > $10M) within same sector or economic linkage
2. **Correlation matrix**: Compute pairwise correlations for top 500 names; filter > 0.8
3. **Cointegration test**: Pairs with high correlation must also pass ADF test (p < 0.05) on spread
4. **Fundamental linkage**: Prefer pairs with real economic connection (competitors, supply chain, dual-listed)
5. **Stability check**: Correlation must remain > 0.7 in at least 80% of rolling 60-day windows over 2 years
6. **Rank by**: Sharpe ratio of historical spread mean-reversion strategy; top 30 pairs make the portfolio

## Z-Score Entry and Exit Framework

- **Spread**: `S_t = log(P_x) - beta * log(P_y)` where beta = rolling OLS hedge ratio
- **Z-score**: `z_t = (S_t - MA(S, n)) / StdDev(S, n)` with n = 2x estimated half-life
- **Entry long spread**: z < -2.0 (spread cheap); **entry short spread**: z > 2.0 (spread rich)
- **Exit**: |z| < 0.5 (mean reversion achieved) or time stop at 3x half-life days
- **Stop loss**: |z| > 3.5 or correlation drops below 0.5 (relationship breakdown)
- **Pyramiding**: Add 50% at z = -2.5 (long) or z = 2.5 (short); max 2 entries per direction

## Regime-Aware Adjustments

- **Low volatility regime**: Tighten entry to |z| > 1.5; spreads mean-revert faster
- **High volatility regime**: Widen entry to |z| > 2.5; more noise requires larger dislocations
- **Correlation breakdown**: If pair correlation < 0.5, close position regardless of z-score
- **Trending regime**: Reduce pair trading allocation; mean-reversion underperforms in strong trends
- **Crisis regime**: Correlations spike to 1.0; pairs converge mechanically; reduce exposure to avoid gap risk

## Portfolio Construction

- **Position sizing**: Equal risk per pair; `size = target_risk / (spread_vol * sqrt(holding_period))`
- **Diversification**: Hold 20-40 pairs; max 3 pairs from same sub-sector
- **Dollar neutral**: Each pair is dollar-neutral; portfolio aggregate is market-neutral
- **Correlation of pairs**: Monitor pair P&L correlations; if > 5 pairs share a common factor, reduce
- **Turnover management**: Average holding period 5-20 days; target annual turnover < 20x

## Risk Management

- **Max loss per pair**: 0.5% of portfolio NAV; auto-close if breached
- **Hedge ratio updating**: Recalculate beta weekly using rolling regression; stale betas create directional drift
- **Execution risk**: Enter both legs simultaneously; use market orders or aggressive limits to avoid legging risk
- **Event risk**: Close or hedge pairs before earnings of either leg; idiosyncratic events destroy pair dynamics
- **Drawdown limit**: Halt new pair entries if portfolio drawdown > 5%; resume after recovery above 3%
