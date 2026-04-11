---
name: Monte Carlo Simulation
description: Monte Carlo methods for portfolio risk estimation and scenario analysis
version: "1.0.0"
author: ROOT
tags: [risk-management, monte-carlo, simulation, risk-estimation, scenarios]
platforms: [all]
---

# Monte Carlo Simulation for Risk

Use random sampling to estimate portfolio risk metrics that are analytically intractable.

## Core Method

### Basic Portfolio Simulation
1. **Fit return distribution**: Estimate mean and covariance of asset returns from historical data
2. **Generate scenarios**: Draw N random return vectors from the fitted distribution (N >= 10,000)
3. **Compute portfolio P&L**: For each scenario, apply returns to current portfolio weights
4. **Extract risk metrics**: VaR, CVaR, max drawdown, probability of loss from the P&L distribution

### Distribution Choices
| Distribution | When to Use | Limitation |
|-------------|------------|------------|
| Normal (Gaussian) | Quick estimate, well-behaved markets | Underestimates tail risk |
| Student's t (df=5) | Better tail modeling, standard choice | Symmetric tails only |
| Skewed t | Asymmetric returns (equities fall faster) | More parameters to fit |
| Historical bootstrap | No assumptions, use actual return history | Limited by history length |
| Copula-based | Complex dependency structures | Computationally expensive |

## Simulation Procedures

### Drawdown Path Simulation
1. Simulate 10,000 equity curves over 252 trading days
2. For each path, compute max drawdown
3. Report: median drawdown, 95th percentile drawdown, worst case
4. Use to set realistic drawdown limits for the strategy

### Strategy Survival Analysis
1. Simulate account equity paths with current strategy statistics (win rate, payoff, frequency)
2. Count paths that hit zero or breach minimum capital threshold
3. Probability of ruin = paths_that_ruin / total_paths
4. If ruin probability > 1%, reduce position sizing

### Retirement / Goal Planning
1. Define goal (e.g., $1M in 10 years from $200K)
2. Simulate 10,000 portfolio paths with expected return and volatility
3. Report probability of reaching goal, median outcome, worst 10% outcome
4. Adjust allocation or savings rate to achieve target probability (>80%)

## Implementation Tips

- Use variance reduction techniques (antithetic variates) to improve convergence
- Seed the random number generator for reproducibility
- Run convergence test: if VaR changes < 1% when doubling N, you have enough samples
- Parallelize simulation across CPU cores for speed
- Store simulation results for what-if analysis without re-running

## Validation

- Compare Monte Carlo VaR to parametric VaR — should be close for normal returns
- Backtest: compare simulated max drawdown distribution to actual historical drawdowns
- Stress test the simulation itself: what happens if volatility doubles? If correlations spike?

## Common Pitfalls

- Using too few simulations (< 1,000) — results are noisy and unreliable
- Fitting distribution to too short a history — misses rare events
- Assuming constant parameters (mean, vol, correlation) — they change over time
- Ignoring serial correlation in returns (momentum / mean-reversion effects)
- Not accounting for transaction costs, slippage, and liquidity constraints
