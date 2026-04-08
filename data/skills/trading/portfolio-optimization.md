---
name: Portfolio Optimization
description: Construct optimal portfolios using modern portfolio theory, factor models, and risk parity
version: "1.0.0"
author: ROOT
tags: [trading, portfolio, optimization, MPT, risk-parity, factor-investing]
platforms: [all]
difficulty: advanced
---

# Portfolio Optimization

Build portfolios that maximize risk-adjusted returns through systematic asset allocation,
factor exposure management, and robust covariance estimation.

## Modern Portfolio Theory (MPT)

### Efficient Frontier Construction
```python
import numpy as np
from scipy.optimize import minimize

# Maximize Sharpe ratio:
def neg_sharpe(weights, returns, cov_matrix, rf=0.05):
    port_return = np.dot(weights, returns.mean()) * 252
    port_vol = np.sqrt(weights @ cov_matrix @ weights * 252)
    return -(port_return - rf) / port_vol

constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
bounds = [(0.02, 0.25)] * n_assets  # 2-25% per asset
result = minimize(neg_sharpe, equal_weights, constraints=constraints, bounds=bounds)
```

### Covariance Estimation (Critical — Sample Covariance is Noisy)
| Method | When to Use | Benefit |
|--------|------------|---------|
| Sample covariance | Large samples (> 5 years) | Simple |
| Ledoit-Wolf shrinkage | Standard approach | Reduces estimation error |
| Factor model covariance | When factor exposures known | Economically grounded |
| Exponentially weighted | Regime-sensitive | Emphasizes recent data |

## Risk Parity

Equal risk contribution from each asset — avoids concentration in low-vol assets.

```python
# Risk parity weights: each asset contributes equal portfolio variance
def risk_parity_weights(cov_matrix):
    # Iterative optimization to equalize risk contributions
    n = len(cov_matrix)
    weights = np.ones(n) / n
    for _ in range(1000):
        port_vol = np.sqrt(weights @ cov_matrix @ weights)
        marginal_risk = cov_matrix @ weights / port_vol
        risk_contribution = weights * marginal_risk
        weights = weights / risk_contribution  # inverse risk weighting
        weights /= weights.sum()
    return weights
```

Standard risk parity allocations (approximate):
- Equities: 25-30% (high vol → lower weight)
- Bonds: 40-50% (low vol → higher weight)
- Commodities: 15-20%
- REITs: 10-15%

## Factor-Based Portfolio Construction

### Core Factors (Fama-French + Extensions)
| Factor | Measurement | Historical Premium |
|--------|------------|------------------|
| Market (Beta) | Market excess return | 5-7% annually |
| Size (SMB) | Small minus large cap | 2-3% |
| Value (HML) | Book-to-market ratio | 3-5% |
| Profitability (RMW) | Gross profit / assets | 2-4% |
| Momentum | 12-1 month return | 5-8% |
| Quality | ROE, low leverage, stable earnings | 3-5% |

### Factor Portfolio Construction
1. Rank universe by factor score
2. Long top quintile, short bottom quintile (for long-short)
3. Or tilt long-only portfolio toward high-factor-score stocks
4. Rebalance quarterly — avoid excessive turnover

## Practical Constraints

```
Real-world portfolio constraints:
  - Long-only (no shorting for most accounts)
  - Minimum position: 2% (avoid fractional shares)
  - Maximum single position: 15-20%
  - Maximum sector: 30%
  - Transaction costs: minimize turnover < 50% annual
  - Liquidity: min $1M average daily volume
```

## Rebalancing Strategy

| Method | Trigger | Cost | Discipline |
|--------|---------|------|-----------|
| Calendar (monthly) | Monthly | Medium | High |
| Threshold (5% drift) | When target exceeded | Low | Medium |
| Factor-based | Significant factor change | Varies | High |
| Volatility-triggered | Vol regime change | Medium | Adaptive |

**Best practice**: 5% threshold + maximum 2 rebalances per year to control costs.

## Portfolio Analytics

### Key Metrics to Monitor
```python
# Performance metrics
sharpe_ratio = (annual_return - risk_free) / annual_vol
sortino_ratio = (annual_return - risk_free) / downside_deviation
calmar_ratio = annual_return / max_drawdown
information_ratio = active_return / tracking_error

# Risk metrics
value_at_risk = portfolio_value * norm.ppf(0.05) * daily_vol
conditional_var = portfolio_value * norm.pdf(norm.ppf(0.05)) / 0.05 * daily_vol
beta = covariance(portfolio, market) / variance(market)
```

### Drawdown Analysis
- Track peak-to-trough drawdown continuously
- Alert at -10%, reduce at -15%, stop at -20%
- Calculate recovery time: months to return to prior peak
- Compare max drawdown to market benchmark

## Stress Testing

Run portfolio through historical scenarios:
1. 2008 Financial Crisis (-50% equities, +20% bonds, -30% credit)
2. 2020 COVID Crash (-34% equities in 33 days)
3. 1994 Bond Crash (rates +250bps, bonds -15%)
4. 2022 Inflation Shock (bonds -20%, equities -20% simultaneously)

Target: Portfolio should not exceed -25% in any severe stress scenario.

## Implementation Workflow

1. Define investment universe and constraints
2. Collect 5+ years of return data
3. Calculate expected returns (use historical mean or factor model)
4. Estimate covariance matrix (Ledoit-Wolf recommended)
5. Run optimization (Sharpe maximization or risk parity)
6. Apply practical constraints and round to tradeable positions
7. Backtest with realistic costs
8. Set monitoring alerts and rebalance triggers
