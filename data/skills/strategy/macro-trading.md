---
name: Macro Trading
description: Global macro strategy framework for cross-asset directional trading
version: "1.0.0"
author: ROOT
tags: [strategy, macro, global, cross-asset, rates]
platforms: [all]
---

# Global Macro Trading Framework

Top-down analysis of economic regimes to position across asset classes.

## Macro Regime Classification

### Growth + Inflation Matrix

| Regime | Growth | Inflation | Best Assets | Worst Assets |
|--------|--------|-----------|-------------|--------------|
| Goldilocks | Rising | Low/stable | Equities, credit | Gold, commodities |
| Reflation | Rising | Rising | Commodities, TIPS, value stocks | Long bonds, growth stocks |
| Stagflation | Falling | Rising | Gold, energy, cash | Equities, bonds |
| Deflation | Falling | Falling | Long bonds, USD, quality stocks | Commodities, credit |

## Key Indicators to Monitor

### Growth Signals
- ISM Manufacturing PMI (leading by 3-6 months)
- Initial jobless claims (weekly, high frequency)
- Copper/gold ratio (industrial demand proxy)
- OECD Leading Economic Indicators
- Shipping rates (Baltic Dry Index)

### Inflation Signals
- 5-year breakeven inflation rate (TIPS vs nominal)
- CPI and PCE (lagging but market-moving)
- Commodity indices (CRB, Bloomberg Commodity)
- Wage growth (Employment Cost Index)
- Money supply growth (M2)

### Liquidity and Policy
- Fed funds rate and forward guidance (dot plot)
- Central bank balance sheet changes (QE/QT pace)
- Financial conditions indices (Chicago Fed, Goldman Sachs)
- Credit spreads (IG and HY vs Treasuries)
- Dollar index (DXY) — tightening or loosening global liquidity

## Trade Implementation

| View | Long | Short/Underweight |
|------|------|-------------------|
| Global growth accelerating | SPY, EEM, copper (COPX) | TLT, gold (GLD) |
| US recession incoming | TLT, gold, utilities (XLU) | SPY, HYG, industrials |
| Inflation surprise up | TIPS, commodities, energy | Long-duration bonds, growth |
| Dollar weakening | EEM, gold, bitcoin | UUP, US importers |
| Yield curve steepening | Financials (XLF), value | Utilities, long bonds |

## Position Sizing for Macro

- Core macro view: 15-25% of portfolio in theme
- Satellite trades: 3-5% per position
- Use futures/ETFs for broad exposure, not individual stocks
- Leverage via futures only, max 1.5x notional
- Set macro stop: exit entire theme if thesis indicators reverse

## Review Cycle

1. **Weekly**: update indicator dashboard, assess any regime shift signals
2. **Monthly**: rebalance macro allocations, review P&L attribution by theme
3. **Quarterly**: full regime reassessment, compare forecast to actuals
4. **After major events**: Fed meetings, employment reports, CPI — immediate review
