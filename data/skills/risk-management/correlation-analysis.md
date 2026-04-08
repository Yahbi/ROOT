---
name: Correlation Analysis
description: Cross-asset correlation tracking and management for portfolio diversification
version: "1.0.0"
author: ROOT
tags: [risk-management, correlation, diversification, cross-asset]
platforms: [all]
---

# Correlation Analysis

Track and manage cross-asset correlations to maintain genuine portfolio diversification.

## Correlation Measurement

### Pearson Correlation
- Standard linear correlation between asset returns
- Use daily returns over rolling 60-day and 252-day windows
- Range: -1 (perfect inverse) to +1 (perfect positive)
- Limitation: only captures linear relationships

### Rank Correlation (Spearman)
- Correlation of return rankings, not magnitudes
- More robust to outliers and non-normal distributions
- Better for detecting non-linear relationships
- Use as confirmation when Pearson shows unexpected results

### Rolling vs Static
- **Static**: single number over full history — misleading, hides regime changes
- **Rolling 60-day**: captures recent correlation regime
- **Rolling 252-day**: captures structural relationships
- Compare short vs long rolling — divergence signals regime shift

## Correlation Regime Detection

### Normal Regime (avg pairwise corr < 0.4)
- Diversification is working as expected
- Standard position sizing applies
- Rebalance on schedule

### Elevated Regime (avg pairwise corr 0.4-0.6)
- Diversification benefit is declining
- Reduce gross exposure by 20%
- Increase cash or add uncorrelated assets (managed futures, gold)

### Crisis Regime (avg pairwise corr > 0.6)
- "All correlations go to 1" — diversification is failing
- Reduce gross exposure by 40%
- Only hold assets with demonstrated crisis alpha (treasuries, gold, VIX)

## Cross-Asset Correlation Map

| | Equities | Bonds | Gold | USD | Crypto | Real Estate |
|---|---------|-------|------|-----|--------|-------------|
| **Equities** | 1.0 | -0.3* | 0.0 | -0.2 | 0.5 | 0.6 |
| **Bonds** | | 1.0 | 0.2 | 0.1 | -0.1 | -0.2 |
| **Gold** | | | 1.0 | -0.5 | 0.2 | 0.0 |

*Note: stock-bond correlation flipped positive in 2022 during inflation regime*

## Actionable Signals

1. **Correlation breakdown**: Two normally correlated assets diverge — potential mean-reversion trade
2. **Correlation spike**: Multiple uncorrelated assets suddenly correlate — risk-off event incoming
3. **Decorrelation opportunity**: New asset shows < 0.2 correlation to portfolio — diversification candidate
4. **Structural shift**: 252-day correlation changes sign — regime change, reassess allocation

## Monitoring Implementation

- Compute full correlation matrix daily for all portfolio holdings
- Track rolling 60-day correlation heatmap — visual inspection weekly
- Alert when any pairwise correlation crosses 0.7 (up) or -0.5 (down)
- Monthly report: average portfolio correlation, diversification ratio, marginal contribution to risk
