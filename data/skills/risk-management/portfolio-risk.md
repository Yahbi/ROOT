---
name: Portfolio Risk Assessment
description: VaR, CVaR, correlation tracking, and stress testing for portfolio risk management
version: "1.0.0"
author: ROOT
tags: [risk-management, VaR, CVaR, stress-testing, correlation]
platforms: [all]
---

# Portfolio Risk Assessment

Quantify and monitor portfolio-level risk using statistical methods and scenario analysis.

## Value at Risk (VaR)

### Parametric VaR (Variance-Covariance)
- Assumes returns are normally distributed
- VaR(95%) = portfolio_value * z_score(1.65) * portfolio_sigma * sqrt(holding_period)
- Fast to compute, but underestimates tail risk

### Historical VaR
- Sort historical portfolio returns, take the 5th percentile
- No distributional assumptions — captures fat tails
- Requires sufficient history (minimum 252 trading days)

### Monte Carlo VaR
- Simulate 10,000+ portfolio return paths from fitted distribution
- Take the 5th percentile of simulated P&L distribution
- Most flexible — can model non-linear instruments and complex correlations

## Conditional VaR (CVaR / Expected Shortfall)

- Average loss in the worst 5% of scenarios (more informative than VaR)
- CVaR captures tail severity — VaR only captures tail boundary
- Preferred by regulators and sophisticated risk managers
- CVaR is always >= VaR for the same confidence level

## Correlation Tracking

### Rolling Correlation Matrix
- Compute 60-day rolling pairwise correlations across all holdings
- Alert when correlations spike above 0.7 (diversification breaking down)
- Correlations increase during crises — exactly when diversification is most needed

### Regime Detection
- Track correlation regime: normal (avg corr < 0.4) vs crisis (avg corr > 0.6)
- In crisis regime: reduce gross exposure by 30%, increase cash allocation

## Stress Testing

### Historical Scenarios
- Replay portfolio through: 2008 GFC, 2020 COVID crash, 2022 rate shock
- Compute max drawdown and recovery time under each scenario

### Hypothetical Scenarios
- Rates +200bps: impact on bond holdings and rate-sensitive equities
- Equity market -30%: portfolio drawdown with current beta
- Volatility spike (VIX > 40): impact on options positions
- USD +10%: impact on international holdings

## Risk Monitoring Dashboard

| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| Daily VaR (95%) | < 2% | 2-4% | > 4% |
| Portfolio beta | 0.5-1.0 | 1.0-1.5 | > 1.5 |
| Max sector weight | < 25% | 25-35% | > 35% |
| Avg pairwise corr | < 0.3 | 0.3-0.5 | > 0.5 |
| Drawdown from peak | < 5% | 5-10% | > 10% |
