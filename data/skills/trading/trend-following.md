---
name: Trend Following (CTA Style)
description: Systematic trend-following across diversified futures and asset classes using moving averages and breakouts
version: "1.0.0"
author: ROOT
tags: [trading, trend-following, CTA, futures, systematic, diversified]
platforms: [all]
difficulty: intermediate
---

# Trend Following (CTA Style)

Capture large directional moves across diversified asset classes. This is the core strategy
of Commodity Trading Advisors (CTAs). Works best during macro trending environments.

## Core Principle

"Cut losses short, let winners run."
Trend followers are wrong 60-70% of the time but right moves are 3-5x larger than wrong moves.
Expected value is positive because of this asymmetry.

## Signal Methods

### Dual Moving Average Crossover
```python
fast_ma = price.rolling(50).mean()
slow_ma = price.rolling(200).mean()

signal = 1  if fast_ma > slow_ma else -1  # long or short
```

### Exponential Moving Average (Faster Response)
```python
fast_ema = price.ewm(span=20).mean()
slow_ema = price.ewm(span=60).mean()
signal = np.sign(fast_ema - slow_ema)
```

### Donchian Channel Breakout
- Long: Price breaks above N-day high (N=20 or 55)
- Short: Price breaks below N-day low
- Exit: Price crosses opposite N/2 day extreme

### MACD Signal
- MACD line = 12-day EMA - 26-day EMA
- Signal line = 9-day EMA of MACD
- Long when MACD crosses above signal; short when below

## Asset Universe (Diversified Futures)

| Asset Class | Markets |
|------------|---------|
| Equities | S&P 500, Nasdaq, Euro Stoxx, Nikkei, DAX futures |
| Fixed Income | US 10yr, 30yr, Bund, Gilt futures |
| Commodities | Crude oil, Gold, Copper, Corn, Soybeans |
| Currencies | EUR/USD, GBP/USD, USD/JPY, AUD/USD |
| Crypto | BTC, ETH perpetual futures |

Diversification is essential — no single market dominates returns.

## Position Sizing (Volatility-Based)

```python
# Risk parity approach — each asset risks equal dollar amount
target_risk = account_value * 0.01  # 1% risk per position
position_size = target_risk / (ATR_20 * dollar_per_point)

# ATR = 20-day Average True Range
# dollar_per_point = contract multiplier
```

## Entry and Exit Rules

```
ENTRY:
  - Signal confirms direction (MA crossover or breakout)
  - ADX > 20 (confirming trend strength)
  - No entry within 5 days of prior signal in same direction

EXIT:
  - Opposite signal generated
  - Time-based: trend hasn't progressed after 30 days → exit
  - Trailing stop: price breaks below N-day low (for longs)
```

## Stop Loss Strategy

- **Initial stop**: 2 ATR from entry price
- **Trailing stop**: Move stop to 2 ATR below highest close (ratchet up)
- **Maximum loss**: 2% of account per trade
- **Portfolio stop**: If portfolio draws down 20%, reduce all positions by 50%

## Diversification Rules

- No more than 25% portfolio risk in one asset class
- No more than 10% risk in correlated assets (e.g., crude oil + gasoline)
- Minimum 10 uncorrelated markets to smooth equity curve
- Correlation check monthly — adjust weights if correlations rise

## Performance Expectations

- Win rate: 35-45% (most trades are small losses)
- Average winner / average loser: 3:1 to 5:1 ratio
- Annual Sharpe: 0.5-1.0 (lower than equity, but crisis-proof)
- Crisis alpha: Trend following profits during market crashes (long bonds, short equities)
- Worst environment: Choppy, oscillating markets with no clear direction

## Benchmark: Classic Trend Signals Performance

| Period | Environment | Trend Following Returns |
|--------|------------|------------------------|
| 2000-2002 | Dot-com crash | +100%+ (short equities, long bonds) |
| 2007-2009 | Financial crisis | +40-80% (long bonds, short equities) |
| 2022 | Inflation spike | +25-40% (long commodities, short bonds) |
| 2012-2020 | Post-crisis stability | Flat to modestly negative |

## Implementation Checklist

- [ ] Build signal calculator for all asset universe
- [ ] Implement volatility-based position sizing
- [ ] Set up automated daily signal refresh
- [ ] Configure stop-loss monitoring
- [ ] Test on 20+ years of data with realistic transaction costs
- [ ] Track metrics: MAR ratio, Calmar ratio, max drawdown
