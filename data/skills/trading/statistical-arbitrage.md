---
name: Statistical Arbitrage
description: Exploit mean-reverting price relationships between cointegrated assets using quantitative methods
version: "1.0.0"
author: ROOT
tags: [trading, stat-arb, cointegration, quantitative, pairs]
platforms: [all]
---

# Statistical Arbitrage

Identify and trade mean-reverting spreads between cointegrated securities using rigorous statistical methods.

## Cointegration Testing

### Engle-Granger Two-Step Method
1. Regress price series Y on X: `Y_t = alpha + beta * X_t + epsilon_t`
2. Test residuals for stationarity using ADF test (p < 0.05 required)
3. The hedge ratio is the regression coefficient beta
4. Limitation: only tests pairwise, assumes one cointegrating vector

### Johansen Test (Preferred for Baskets)
- Tests multiple cointegrating relationships simultaneously
- Use **trace statistic** or **max eigenvalue** to determine number of vectors
- Rank 0 = no cointegration, Rank 1+ = cointegrated system
- Rolling 252-day windows to detect regime changes in cointegration strength

## Spread Construction and Z-Score

- **Spread**: `S_t = Y_t - beta * X_t`
- **Z-score**: `z_t = (S_t - mean(S)) / std(S)` over lookback window (typically 60-120 days)
- **Entry**: |z| > 2.0 (short spread when z > 2, long when z < -2)
- **Exit**: |z| < 0.5 (mean reversion target) or |z| > 3.5 (stop loss)
- **Half-life**: `HL = -ln(2) / ln(phi)` where phi is AR(1) coefficient of the spread
- Optimal lookback window ~ 2-3x the half-life; reject pairs with HL > 60 days

## Signal Refinement

- **Hurst exponent** < 0.5 confirms mean-reversion; target H < 0.4 for strongest signals
- **Variance ratio test**: ratio of k-period variance to 1-period variance should be < 1
- **Kalman filter**: dynamic hedge ratio estimation adapts to changing beta in real time
- **Ornstein-Uhlenbeck process**: `dS = theta * (mu - S) * dt + sigma * dW` models mean reversion speed

## Portfolio Construction

- Run cointegration tests across universe of 500+ liquid equities
- Rank pairs by: half-life (shorter better), Hurst exponent (lower better), spread stability
- Hold 20-50 pairs simultaneously for diversification
- Dollar-neutral: equal notional on long and short legs
- Sector-neutral variant: pair only within sectors to reduce factor exposure

## Risk Management

- Max 2% portfolio risk per pair; 15% gross exposure per sector
- Cointegration can break: re-test weekly, exit immediately if ADF p-value rises above 0.10
- Stop loss at 3.5 sigma or if spread exceeds 2x historical max
- Monitor correlation of pair P&L across the book to avoid hidden concentration
- Transaction costs matter: minimum expected profit per round-trip must exceed 3x costs
