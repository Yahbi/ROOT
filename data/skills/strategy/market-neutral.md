---
name: Market Neutral Strategy
description: Long/short equity construction with beta hedging and multi-factor neutralization
version: "1.0.0"
author: ROOT
tags: [strategy, market-neutral, long-short, hedging, beta, factor]
platforms: [all]
---

# Market Neutral Strategy

Construct portfolios that generate alpha independent of market direction by neutralizing systematic risk exposures through careful hedging.

## Long/Short Equity Construction

- **Core idea**: Long undervalued stocks, short overvalued stocks; net exposure near zero
- **Gross exposure**: `|long_notional| + |short_notional|`; typically 150-200% for levered L/S funds
- **Net exposure**: `long_notional - short_notional`; target 0% to +/-10% for market-neutral
- **Alpha source**: Stock selection skill; `return = alpha_long + alpha_short + beta * R_market`
- **Book balance**: Match long and short book sizes; dollar-neutral is minimum requirement

## Beta Hedging

- **Portfolio beta**: `beta_portfolio = SUM(w_i * beta_i)` across all positions
- **Target**: beta_portfolio = 0.0 +/- 0.05
- **Hedge instrument**: S&P 500 futures (ES) or SPY; `hedge_notional = beta_portfolio * portfolio_NAV`
- **Dynamic adjustment**: Recalculate beta daily using 60-day rolling regression; betas drift with regimes
- **Beta estimation**: Use Dimson (1979) adjustment for illiquid stocks (lead/lag betas)
- **Residual beta**: After hedging, residual beta should be < 0.05; test with attribution analysis

## Multi-Factor Neutralization

Beyond beta, neutralize these systematic exposures:

- **Sector neutral**: Equal long and short notional within each GICS sector; zero sector bets
- **Size neutral**: Match market-cap distribution between long and short books
- **Value neutral**: Equal value factor loading on both sides; `SUM(w_i * B/P_i)_long = SUM(w_i * B/P_i)_short`
- **Momentum neutral**: Balance momentum exposures to avoid hidden momentum beta
- **Implementation**: Use constrained optimization: `min tracking_error subject to factor_exposures = 0`
- **Factor risk model**: Barra, Axioma, or custom PCA-based; decompose returns into factor + specific

## Alpha Signal Integration

- **Composite score**: Combine multiple signals — fundamental (earnings revisions), technical (RSI), alternative (sentiment)
- **Signal weighting**: `alpha_i = w_1 * signal_1 + w_2 * signal_2 + ...`; weights from IC-based optimization
- **Information Coefficient (IC)**: `corr(predicted_return, actual_return)`; target IC > 0.05 per signal
- **Breadth**: `IR = IC * sqrt(breadth)` (fundamental law); trade more names with weaker signal, fewer with stronger
- **Signal decay**: Measure IC over holding periods; faster-decaying signals require higher turnover
- **Crowding penalty**: Reduce signal weight for consensus positions (high short interest, popular longs)

## Portfolio Optimization

- **Objective**: Maximize `expected_return - lambda * risk - turnover_cost`
- **Risk model**: Factor covariance + specific risk; `Var(R_p) = w' * (B*F*B' + D) * w`
- **Constraints**: Max position size 3%, sector neutral, factor neutral, turnover < 30% per month
- **Transaction costs**: Include spread, market impact, commission; `impact = k * sigma * sqrt(shares/ADV)`
- **Rebalance frequency**: Daily or weekly; balance alpha decay vs transaction costs
- **Tax-aware**: In taxable accounts, penalize short-term gain realization in optimizer

## Performance Attribution

- **Factor attribution**: Decompose returns into factor contributions + stock-specific alpha
- **Hit rate**: Percentage of longs that outperform and shorts that underperform; target > 53% each
- **Long alpha vs short alpha**: Track separately; short alpha is harder and often dominates P&L variance
- **Information ratio target**: > 1.0 (annualized alpha / annualized tracking error)
- **Drawdown profile**: Market-neutral should have < 10% max drawdown; if higher, factor leakage suspected

## Risk Management

- **Net exposure limit**: |net_exposure| < 10%; breach triggers immediate rebalancing
- **Single stock limit**: Max 3% of NAV long, 2% of NAV short (shorts have asymmetric risk)
- **Pair correlation**: If long/short pairs are correlated > 0.8, count combined as single position for limits
- **Short squeeze monitoring**: Watch short interest > 20% of float, cost-to-borrow spikes, social media activity
- **Stress testing**: Run portfolio through 2008, 2020 March, sector rotation scenarios monthly
- **Leverage limit**: Gross exposure < 250%; reduce if realized vol exceeds 15% annualized
