---
name: Mean Reversion Trading
description: Profit from temporary price deviations that revert to a statistical mean
version: "1.0.0"
author: ROOT
tags: [trading, mean-reversion, statistical, quantitative, short-term]
platforms: [all]
difficulty: intermediate
---

# Mean Reversion Trading

Exploit the tendency of prices to revert to equilibrium after short-term dislocations.
Works best in range-bound markets, high-liquidity assets, and on intraday to weekly timeframes.

## Core Signals

### Z-Score Mean Reversion
```python
lookback = 20  # days
z_score = (current_price - rolling_mean(lookback)) / rolling_std(lookback)

# Entry thresholds:
# z < -2.0 → BUY (oversold)
# z > +2.0 → SELL SHORT (overbought)
# Exit: z returns to 0
```

### Bollinger Band Reversion
1. Calculate 20-day SMA and 2 standard deviation bands
2. Enter LONG when price closes below lower band
3. Enter SHORT when price closes above upper band
4. Exit at middle band (20-day SMA)
5. Stop loss: 3rd standard deviation breach (trend breakout confirmed)

### RSI Oscillator
- RSI < 20: Aggressive long entry
- RSI < 30: Standard long entry
- RSI > 70: Short entry
- RSI > 80: Aggressive short entry
- Exit: RSI crosses 50 (midpoint)

## Market Conditions Filter

Mean reversion FAILS during trending markets. Use filters to avoid trend periods:

| Filter | Method | Threshold |
|--------|--------|-----------|
| Trend filter | 200-day SMA slope | Flat ± 0.1% per week |
| Volatility filter | ATR < historical 75th percentile | Skip during vol spikes |
| Regime filter | ADX < 25 | High ADX = trending market |
| Hurst exponent | H < 0.5 | Mean-reverting; H > 0.5 = trending |

## Best Assets for Mean Reversion

- **ETFs**: SPY, GLD, TLT (deeply liquid, rarely trend violently)
- **Rate-bound assets**: Utility stocks, REITs (yield-anchored valuation)
- **Pairs spread**: Mean reversion of spread between cointegrated pairs
- **Intraday**: Index futures during lunch hours (11am-2pm ET) — low trend, high reversion

## Position Sizing by Signal Strength

```
Z-score -1.5 to -2.0 → 25% of max position
Z-score -2.0 to -2.5 → 50% of max position
Z-score -2.5 to -3.0 → 75% of max position
Z-score < -3.0      → 100% of max position
```
Scale into positions as price moves against you; scale out as it recovers.

## Risk Controls

- **Hard stop**: Close position if z-score exceeds -4.0 (regime change or crisis)
- **Time stop**: Close after 10 days if position has not reverted — momentum may be winning
- **Correlation risk**: Avoid multiple mean-reversion positions in same sector simultaneously
- **Earnings**: Flat before earnings — fundamental shock can prevent reversion
- **Maximum drawdown per strategy**: 10% triggers position size reduction by 50%

## Execution Tips

1. Use limit orders, not market orders — capture the spread as market maker
2. Scale in at each z-score threshold rather than all-at-once entry
3. Set target exits (take profit at z = 0) as limit orders in advance
4. Avoid holding over weekends — gap risk can widen deviation further

## Common Mistakes

- **Fighting a trend**: Mean reversion in a trending stock bleeds capital steadily
- **Oversizing**: Deviations can persist and widen before reverting — keep positions small
- **Ignoring fundamentals**: Some "cheap" stocks are cheap for good reasons (value traps)
- **No time stop**: Tying up capital in slow-reverting positions has opportunity cost

## Performance Characteristics

- Win rate: 60-70% (more frequent small wins)
- Average winner: smaller than average loser
- Sharpe: 0.8-1.5 in optimal conditions
- Max drawdown: can be severe during trending regimes
- Best months: Low-volatility, sideways market environments
- Worst months: Strong directional trends, crisis events
