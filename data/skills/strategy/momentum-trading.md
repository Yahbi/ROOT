---
name: Momentum Trading
description: Systematic momentum factor strategies for equities and ETFs
version: "1.0.0"
author: ROOT
tags: [strategy, momentum, factor, systematic]
platforms: [all]
---

# Momentum Trading Strategy

Exploit the tendency of recent winners to continue outperforming and losers to underperform.

## Momentum Factors

### Price Momentum (12-1)
- Rank universe by 12-month return excluding the most recent month
- Skip last month to avoid short-term reversal effect
- Buy top decile, sell/avoid bottom decile
- Rebalance monthly — momentum decays over 3-12 months

### Earnings Momentum
- Rank by standardized unexpected earnings (SUE): (actual EPS - estimate) / std
- Top SUE decile outperforms for 60-90 days post-announcement
- Combine with price momentum for stronger signal

### Relative Strength (Sector)
- Compare each sector ETF to SPY over 3 and 6 month windows
- Overweight sectors with RS > 1.0 and rising
- Underweight sectors with RS < 1.0 and falling

## Entry Rules

1. **Universe**: S&P 500 constituents (or liquid ETFs for simplicity)
2. **Rank**: compute 12-1 month return for each stock
3. **Filter**: require average daily volume > $10M (liquidity filter)
4. **Select**: top 20 stocks by momentum score
5. **Size**: equal-weight (5% each) or inverse-volatility weight
6. **Enter**: at market open on first trading day of the month

## Exit Rules

- **Monthly rebalance**: sell any stock that drops out of top 30 rank
- **Stop-loss**: exit if position drops 15% from entry (momentum crash protection)
- **Regime filter**: if SPY is below 200-day MA, go to 50% cash
- **Volatility filter**: if VIX > 30, reduce position sizes by 50%

## Momentum Crash Protection

Momentum strategies suffer severe drawdowns during sharp reversals (2009, 2020).

1. **Volatility scaling**: reduce exposure when trailing 20-day vol > 2x median
2. **Diversify momentum horizons**: blend 1-month, 3-month, and 12-month signals
3. **Combine with value**: momentum + value = reduced crash risk
4. **Dynamic hedging**: buy SPY puts when momentum dispersion is extreme

## Expected Performance

- **Annual return**: 8-15% above market (gross, before costs)
- **Sharpe ratio**: 0.6-0.9 (standalone), 1.0+ when combined with value
- **Max drawdown**: -30% to -50% in momentum crashes (mitigated by filters)
- **Turnover**: 80-120% annual (moderate transaction costs)
- **Best in**: trending markets with clear sector leadership
