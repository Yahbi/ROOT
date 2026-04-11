---
name: Momentum Trading
description: Systematically buy recent outperformers and short recent underperformers across asset classes
version: "1.0.0"
author: ROOT
tags: [trading, momentum, systematic, cross-sectional, quantitative]
platforms: [all]
difficulty: intermediate
---

# Momentum Trading

Momentum is one of the most robust anomalies in finance: assets that have outperformed recently
tend to continue outperforming for 3-12 months. Exploit it systematically.

## Types of Momentum

| Type | Lookback | Holding | Best For |
|------|----------|---------|---------|
| Cross-sectional | 12-1 month | 1 month | Equities, ETFs |
| Time-series (TSMOM) | 12 months | 1 month | Futures, commodities |
| Short-term | 1-4 weeks | 1 week | High-frequency |
| Industry momentum | 12-1 month | 3 months | Sector rotation |

## Signal Construction (Cross-Sectional)

1. **Universe**: S&P 500 or liquid ETF universe (exclude penny stocks, illiquid names)
2. **Lookback window**: 12-month return, skip the most recent month (avoids reversal effect)
   - Momentum score = (Price[t-1] / Price[t-252]) - 1
3. **Ranking**: Rank all assets by momentum score (1 = lowest, N = highest)
4. **Portfolio**: Long top decile (rank 90-100%), short bottom decile (rank 0-10%)
5. **Rebalance**: Monthly on the first trading day

## Time-Series Momentum (Futures)

```python
# For each asset in universe:
momentum_signal = 1 if 12_month_return > 0 else -1
position_size = momentum_signal * (target_vol / asset_volatility)
# Scale by inverse volatility for risk parity across assets
```

## Risk Management

### Momentum Crashes
- Momentum suffers sharp reversals after market crashes (losers bounce sharply)
- **Recession filter**: reduce or hedge momentum exposure during bear markets
  - Signal: S&P 500 below 200-day SMA → reduce momentum longs by 50%
  - Signal: VIX > 35 → cut short book exposure (losers are extra volatile)

### Diversification
- Maintain exposure across multiple sectors (avoid single-sector concentration)
- Blend with value or quality factors to smooth drawdowns
- Maximum 5% per single position in long book

### Transaction Costs
- Momentum has high turnover — minimize costs or returns evaporate
- Use patient execution: VWAP or TWAP for entries/exits
- Avoid rebalancing during low-liquidity periods (holidays, options expiry)

## Portfolio Construction

```
Long book:  Top 20 stocks by momentum score
Short book: Bottom 20 stocks by momentum score
Leverage:   1.0x long / 0.5x short (bias to long side)
Rebalance:  Monthly; only trade if rank change > 10 positions
Max drawdown stop: -15% from peak → reduce exposure 50%
```

## Enhancements

1. **Volatility adjustment**: Weight positions by 1/vol to risk-normalize returns
2. **Earnings skip**: Avoid entering new momentum longs within 5 days of earnings
3. **Residual momentum**: Use alpha momentum (stock returns minus industry returns)
4. **52-week high signal**: Stocks near 52-week high have stronger forward momentum
5. **Analyst revision momentum**: Recent upward EPS revisions amplify price momentum

## Backtest Results (Historical Reference)

- Raw cross-sectional momentum (Jegadeesh-Titman 1993): +12% alpha annualized
- Time-series momentum (Moskowitz-Ooi-Pedersen 2012): +15% Sharpe improvement
- Industry momentum (Grinblatt-Moskowitz 1999): Robust across 34 markets
- Momentum crashes: worst periods are Jan 2001 (-42%), Mar-Jun 2009 (-73%)

## Implementation Checklist

- [ ] Define universe and data source (yfinance, Quandl, Bloomberg)
- [ ] Code signal calculation with proper lookback window
- [ ] Backtest with realistic transaction costs (5-20bps per trade)
- [ ] Apply crash protection filter
- [ ] Set position limits and max drawdown stops
- [ ] Schedule monthly rebalance automation
- [ ] Monitor signal decay — momentum weakens if crowded
