---
name: Portfolio Optimization
description: Modern portfolio theory, efficient frontier, and optimal allocation
version: "1.0.0"
author: ROOT
tags: [financial, portfolio, optimization, MPT, allocation]
platforms: [all]
---

# Portfolio Optimization

Construct optimal portfolios using Modern Portfolio Theory and practical enhancements.

## Efficient Frontier Construction

### 1. Gather Inputs
- **Expected returns**: use 3-5 year forward estimates (not just historical)
- **Covariance matrix**: 252-day rolling daily returns, shrink toward diagonal
- **Constraints**: min/max weights per asset, sector limits, no short selling

### 2. Mean-Variance Optimization
```
Maximize: Sharpe Ratio = (E[Rp] - Rf) / sigma_p
Subject to: sum(weights) = 1, weights >= 0

E[Rp] = sum(wi * ri)
sigma_p = sqrt(w' * Cov * w)
```

### 3. Generate Frontier
- Sweep target returns from min to max feasible
- For each target, minimize variance subject to constraints
- Plot risk (x-axis) vs return (y-axis) — the curve is the efficient frontier
- Tangency portfolio (max Sharpe) is the optimal risky portfolio

## Practical Enhancements

### Black-Litterman Model
- Start with market equilibrium weights (market-cap weighted)
- Overlay personal views with confidence levels
- Produces more stable, intuitive allocations than raw MVO

### Hierarchical Risk Parity
- Cluster assets by correlation structure
- Allocate within clusters, then across clusters
- More robust to estimation error than mean-variance

### Resampled Efficiency
- Monte Carlo simulate 1000 return/covariance scenarios
- Optimize each scenario, average the resulting weights
- Reduces sensitivity to input estimation errors

## Implementation Checklist

1. Select 5-15 asset classes (too many = overfitting, too few = underdiversified)
2. Estimate returns via CAPM, analyst consensus, or factor models
3. Use Ledoit-Wolf shrinkage on covariance matrix
4. Optimize with max position constraint of 25%
5. Rebalance quarterly or when any weight drifts >5% from target
6. Compare realized Sharpe vs target — recalibrate inputs annually

## Common Mistakes

- Using historical returns as expected returns (past != future)
- Ignoring transaction costs and taxes in optimization
- Over-concentrating in assets with highest historical returns
- Not stress-testing against 2008, 2020, and 2022 scenarios
- Optimizing too frequently (monthly rebalance causes excessive turnover)
