---
name: Position Sizing
description: Optimal position sizing using Kelly criterion, fractional Kelly, and ATR-based methods
version: "1.0.0"
author: ROOT
tags: [risk-management, position-sizing, kelly, ATR, money-management]
platforms: [all]
---

# Position Sizing

Determine how much capital to allocate per trade to maximize long-term growth while controlling drawdowns.

## Kelly Criterion

### Full Kelly Formula
```
f* = (bp - q) / b
where:
  f* = fraction of capital to wager
  b  = odds received (win/loss ratio)
  p  = probability of winning
  q  = 1 - p (probability of losing)
```

### Practical Application
- Full Kelly is mathematically optimal but produces extreme volatility
- **Use fractional Kelly (25-50% of full Kelly)** for real trading
- Half-Kelly reduces growth rate by 25% but cuts variance by 50%
- Requires accurate win rate and payoff ratio estimates — garbage in, garbage out

### Estimating Inputs
- Win rate: minimum 100 trades of backtest data, walk-forward validated
- Payoff ratio: average winner / average loser from same backtest
- Recalculate monthly as market conditions shift

## ATR-Based Position Sizing

### Method
1. Calculate 14-period ATR (Average True Range) for the instrument
2. Define risk per trade as percentage of account (typically 0.5-2%)
3. Set stop-loss distance as multiple of ATR (usually 1.5-3x ATR)
4. Position size = (Account * Risk%) / (ATR * ATR_multiple)

### Advantages
- Automatically adjusts for volatility — smaller positions in volatile markets
- Consistent dollar risk across different instruments
- Works for any asset class (equities, futures, forex, crypto)

## Fixed Fractional Method

- Risk a fixed percentage of current equity per trade (1-2% standard)
- Position size grows as account grows, shrinks as account shrinks
- Simple, robust, and self-correcting after drawdowns

## Position Sizing Rules

| Account Size | Max Risk/Trade | Max Correlated Risk | Max Total Exposure |
|-------------|---------------|--------------------|--------------------|
| < $25K | 1.0% | 3% | 30% |
| $25K-$100K | 1.5% | 5% | 50% |
| $100K-$500K | 2.0% | 8% | 60% |
| > $500K | 1.0% | 5% | 40% |

## Common Mistakes

- Sizing based on conviction rather than math (emotional sizing)
- Not reducing size after consecutive losses (ignoring drawdown)
- Ignoring correlation — 5 positions in tech stocks is really 1 large position
- Using full Kelly without understanding the variance implications
- Not accounting for slippage and commissions in size calculations
