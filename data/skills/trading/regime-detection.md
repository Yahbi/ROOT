---
name: Regime Detection
description: Identify market regimes using Hidden Markov Models and volatility clustering for adaptive strategy selection
version: "1.0.0"
author: ROOT
tags: [trading, regime, HMM, volatility, quantitative]
platforms: [all]
---

# Regime Detection

Classify market states into discrete regimes (trending, mean-reverting, crisis) to dynamically switch strategies and risk parameters.

## Hidden Markov Models (HMM)

- **States**: Typically 2-3 regimes — low-vol trending, high-vol mean-reverting, crisis
- **Observable**: Daily returns, realized volatility, or spread changes
- **Transition matrix**: `P(S_t = j | S_{t-1} = i)` captures regime persistence and switching probabilities
- **Emission distributions**: Gaussian per state with distinct mu and sigma; fit via Expectation-Maximization (EM)
- **Viterbi algorithm**: Decode most likely regime sequence given observed data
- **Forward-backward**: Compute `P(regime = k | all data)` for real-time filtering

## Volatility Clustering Detection

- **GARCH(1,1)**: `sigma_t^2 = omega + alpha * r_{t-1}^2 + beta * sigma_{t-1}^2`; persistence = alpha + beta
- **Regime threshold**: Low-vol when GARCH sigma < 20th percentile of rolling 252-day distribution; high-vol when > 80th
- **Realized vol ratio**: `RV_5day / RV_60day` > 1.5 signals volatility expansion (regime shift)
- **VIX term structure**: Contango = calm regime; backwardation = crisis regime
- **Markov-switching GARCH**: Combines HMM with GARCH — each regime has its own volatility dynamics

## Trend vs Mean-Reversion Classification

- **Hurst exponent**: H > 0.55 = trending, H < 0.45 = mean-reverting, 0.45-0.55 = random walk
- **Variance ratio test**: `VR(k) = Var(k-period returns) / (k * Var(1-period returns))`; VR > 1 = trend, VR < 1 = mean-reversion
- **ADX filter**: ADX > 25 with rising DI+/DI- separation confirms trend regime
- **Rolling autocorrelation**: Positive serial correlation = momentum regime; negative = mean-reversion

## Strategy Switching Rules

| Regime | Strategy | Position Sizing | Stop Width |
|--------|----------|----------------|------------|
| Low-vol trend | Momentum / trend-following | Full size | Tight (1.5 ATR) |
| High-vol trend | Momentum with reduced size | 50% size | Wide (3 ATR) |
| Low-vol mean-revert | Stat-arb / mean-reversion | Full size | Tight (2 sigma) |
| High-vol mean-revert | Mean-reversion with caution | 30% size | Wide (3.5 sigma) |
| Crisis | Defensive / tail hedges only | 20% size or flat | N/A |

## Implementation

1. Fit 3-state HMM on rolling 500-day windows of daily returns
2. Use filtered probabilities (not smoothed) for real-time regime classification
3. Require regime probability > 0.7 before switching; avoid whipsawing on marginal signals
4. Retrain model monthly; monitor BIC to validate state count
5. Combine HMM output with Hurst exponent and VIX term structure for confirmation
6. Lag strategy switches by 1 day to avoid overreacting to single-day regime flickers

## Risk Management

- Reduce gross exposure by 50% during regime transitions (probability of any state < 0.6)
- Crisis regime triggers: flatten directional bets, activate tail hedges, halt new entries
- Track regime duration: mean-reverting regimes after 30+ days of trend often signal exhaustion
- Backtest each strategy exclusively within its target regime to validate conditional alpha
