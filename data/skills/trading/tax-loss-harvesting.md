---
name: Tax-Loss Harvesting
description: Systematically realize losses to offset gains while maintaining market exposure
version: "1.0.0"
author: ROOT
tags: [trading, tax, optimization, portfolio, harvesting]
platforms: [all]
---

# Tax-Loss Harvesting

Generate tax alpha by strategically realizing losses to offset capital gains while maintaining desired market exposure through substitute positions.

## Core Mechanics

- **Tax alpha**: Defer taxes by realizing losses now, offsetting gains; time value of deferred taxes = free capital
- **Short-term losses first**: Offset short-term gains (taxed at ordinary income, up to 37%) before long-term (20%)
- **Annual limit**: Excess losses offset up to $3,000 of ordinary income; remainder carries forward indefinitely
- **Estimated value**: 0.5-1.5% annualized after-tax alpha for taxable accounts; higher in volatile markets

## Wash Sale Rules (Critical)

- **30-day rule**: Cannot repurchase "substantially identical" security within 30 days before or after sale
- **Substantially identical**: Same stock, same class of shares, options on same stock, ETF tracking same narrow index
- **NOT substantially identical**: Different index ETFs (SPY vs VTI), sector ETFs vs broad market, individual stock vs sector ETF
- **Cross-account**: Wash sale applies across ALL accounts (taxable, IRA, spouse accounts)
- **Replacement pairs**: AAPL -> MSFT (same sector, not identical), SPY -> VTI, IWM -> SCHA, QQQ -> VGT
- **Penalty**: Disallowed loss added to cost basis of replacement; not lost permanently, but deferral eliminated

## Lot Selection Strategy

- **Specific identification**: Designate which lots to sell (vs FIFO default); crucial for optimization
- **Highest cost basis first**: Realize the largest loss per share
- **Short-term losses preferred**: Worth more in tax savings (higher rate offset)
- **Long-term gains preferred**: Lower tax rate when realizing gains for rebalancing
- **Tax lot optimization**: For each position, rank lots by: `tax_benefit = loss * marginal_rate - transaction_cost`

## Systematic Harvesting Protocol

1. **Daily scan**: Check all positions for unrealized losses exceeding threshold (e.g., > $1,000 or > 5%)
2. **Evaluate**: `net_benefit = loss * tax_rate - 2 * transaction_cost - tracking_error_cost`
3. **Execute**: Sell losing lots, immediately buy pre-approved substitute security
4. **Calendar**: After 31 days, optionally swap back to original security
5. **Year-end sprint**: Aggressive harvesting in November-December; be aware of December mutual fund distributions
6. **Track basis**: Maintain precise records of adjusted cost basis for replacement securities

## Tax Alpha Optimization

- **Volatility harvesting**: More volatile portfolios generate more harvesting opportunities
- **Direct indexing**: Hold individual stocks (not ETFs) to maximize loss opportunities across 500+ positions
- **Asset location**: Hold tax-inefficient assets (bonds, REITs) in tax-deferred; equities in taxable for harvesting
- **Gain deferral math**: `Alpha = loss * tax_rate * discount_rate / (1 + discount_rate)` per year of deferral
- **Charitable giving**: Donate appreciated lots instead of selling; donate losers only after harvesting

## Risk Management

- **Tracking error**: Substitute securities introduce tracking error; keep correlation > 0.95 with original
- **Rebalancing interaction**: Coordinate harvesting with rebalancing to avoid cross-purposes
- **State taxes**: Consider state capital gains rates (0-13.3%); increases harvesting value in high-tax states
- **AMT awareness**: Some harvested losses may trigger AMT complications; consult tax rules for large harvests
- **Breakeven analysis**: Do not harvest if expected holding period < 1 year (short-term gain on replacement)
