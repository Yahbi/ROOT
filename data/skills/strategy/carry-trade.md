---
name: Carry Trade
description: Profit from interest rate differentials, funding rates, and roll yield across asset classes
version: "1.0.0"
author: ROOT
tags: [strategy, carry, interest-rates, FX, funding, yield]
platforms: [all]
---

# Carry Trade

Extract return from holding higher-yielding assets funded by lower-yielding instruments, exploiting the forward rate bias and funding rate differentials.

## FX Carry Trade

- **Classic setup**: Borrow in low-rate currency (JPY, CHF), invest in high-rate currency (AUD, BRL, MXN)
- **Expected return**: `carry = (r_invest - r_fund) - E[FX_depreciation]`
- **Forward rate bias**: Forward rates overestimate depreciation; carry earns excess returns on average
- **Annualized carry**: Interest rate differential * notional; typical 3-8% for EM carry trades
- **G10 carry portfolio**: Long AUD, NZD, NOK; short JPY, CHF, EUR; equal-risk-weighted
- **EM carry portfolio**: Long BRL, MXN, ZAR, INR; short USD; higher carry but larger drawdowns

## Crypto Funding Rate Carry

- **Perpetual funding**: Long pays short when funding > 0 (bullish market); funding rate = basis proxy
- **Trade setup**: Long spot + short perpetual futures; collect positive funding every 8 hours
- **Annualized yield**: `funding_rate * 3 * 365` (3 payments/day); often 10-30% APR in bull markets
- **Execution**: Must hold spot as collateral; basis risk minimal if using same underlying
- **Risks**: Funding can flip negative (bear market); liquidation risk on short perp if margin insufficient
- **Exchanges**: Binance, Bybit, dYdX; compare rates across venues for best carry

## Fixed Income Carry

- **Roll yield**: Bond prices converge to par; long bond earns `(forward_yield - spot_yield) * duration`
- **Curve carry**: Buy longer-duration bonds funded by short-term borrowing (positive yield curve)
- **Carry formula**: `carry = yield - funding_cost + roll_down + pull_to_par`
- **Steepener/flattener**: Trade the yield curve shape; steepener = long short-end, short long-end
- **Break-even yield change**: `carry / duration`; the yield rise that would wipe out carry profit

## Commodity Carry

- **Contango carry**: Short front-month, long back-month; profit from convergence (negative roll yield for long-only)
- **Backwardation carry**: Long front-month earns positive roll yield as futures converge to spot
- **Roll yield formula**: `(near_price - far_price) / far_price * (365 / days_between)` annualized
- **Structural backwardation**: Energy, agriculture during supply shocks; structural contango: VIX futures, gold

## Carry Portfolio Construction

- **Multi-asset carry**: Combine FX, rates, commodity carry for diversification; low cross-asset correlation
- **Risk parity weighting**: Allocate inversely proportional to historical volatility per carry source
- **Target volatility**: Scale portfolio to 8-10% annualized vol; lever/delever dynamically
- **Signal blending**: Pure carry + momentum filter (only hold carry trades where trend is supportive)
- **Rebalance**: Monthly for FX and rates; weekly for crypto funding; at roll dates for commodities

## Unwinding Risks

- **Carry crash**: Rapid unwind when risk sentiment shifts; JPY carry trades reversed 15% in days (2024)
- **VaR shock**: Correlated unwind across carry trades amplifies losses beyond individual pair risk
- **Crowding indicator**: When speculative positioning reaches extremes (CFTC COT data), carry is vulnerable
- **Liquidity withdrawal**: EM carry trades seize during global risk-off; exit becomes impossible at reasonable prices
- **Central bank surprise**: Unexpected rate cut in high-yield country instantly destroys carry thesis

## Risk Management

- **Position sizing**: Max 3% portfolio risk per carry trade; 15% aggregate carry exposure
- **Stop loss**: Exit if carry trade drawdown exceeds 2x annual carry income
- **Momentum filter**: Only hold carry where 3-month price trend aligns; cuts drawdowns by 30-40%
- **Correlation monitoring**: If carry trade correlations spike > 0.7, reduce portfolio by 50%
- **Hedge tail risk**: Allocate 5% to put options on high-carry positions as crash insurance
