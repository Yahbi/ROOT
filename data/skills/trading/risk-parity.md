---
name: Risk Parity
description: Portfolio construction using equal risk contribution across assets
version: "1.0.0"
author: ROOT
tags: [trading, portfolio, risk-management, allocation]
platforms: [all]
---

# Risk Parity Portfolio Construction

Build portfolios where each asset contributes equally to total portfolio risk.

## Core Concept

Traditional 60/40 portfolios concentrate ~90% of risk in equities. Risk parity
equalizes risk contribution so no single asset class dominates drawdowns.

## Implementation Steps

1. **Select asset classes** — minimum 4: equities, bonds, commodities, gold
2. **Calculate volatility** — use 60-day rolling standard deviation of daily returns
3. **Compute inverse-vol weights**: weight_i = (1/vol_i) / sum(1/vol_j for all j)
4. **Apply leverage** (optional) — target 10% annual portfolio vol via scaling factor
5. **Rebalance monthly** — recalculate weights on the first trading day

## Example Allocation (unlevered)

| Asset | ETF | Typical Vol | Approx Weight |
|-------|-----|-------------|---------------|
| US Equities | SPY | 16% | 15% |
| Long-Term Bonds | TLT | 15% | 16% |
| Commodities | DJP | 12% | 20% |
| Gold | GLD | 14% | 17% |
| Int'l Equities | EFA | 17% | 14% |
| TIPS | TIP | 5% | 18% |

## Correlation Matrix Check

- Verify pairwise correlations quarterly
- If equity-bond correlation exceeds +0.3, reduce both and increase gold/commodities
- Negative correlation assets are the most valuable diversifiers

## Leverage and Targeting

- **Unlevered risk parity**: ~5-7% annual vol, ~4-6% annual return
- **Levered to 10% vol**: multiply weights by (target_vol / portfolio_vol)
- Use futures or margin, not options, for leverage
- Never exceed 2x effective leverage

## Risk Controls

- Max 35% weight in any single asset after leverage
- If portfolio drawdown exceeds 10%, reduce leverage by 50%
- Monitor funding costs — leverage is not free
- Rebalance if any asset's weight drifts >5% from target
- Backtest rolling 3-year Sharpe; target >0.7 after costs
