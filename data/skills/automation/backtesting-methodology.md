---
name: Backtesting Methodology
description: Rigorous backtesting practices to avoid overfitting and ensure validity
version: "1.0.0"
author: ROOT
tags: [automation, backtesting, validation, quantitative]
platforms: [all]
---

# Backtesting Methodology

Backtest strategies rigorously to distinguish real alpha from curve-fitting.

## Framework

### 1. Data Preparation
- Use adjusted close prices (splits, dividends accounted for)
- Include delisted stocks to avoid survivorship bias
- Minimum 5 years of data (or 2 full market cycles)
- Separate: 60% in-sample (development), 20% validation, 20% out-of-sample (final test)

### 2. Execution Realism
- **Slippage**: add 0.05% per trade minimum (0.10% for small caps)
- **Commission**: model actual broker fees ($0 for most, but include SEC/FINRA fees)
- **Fill assumptions**: limit orders fill only if price crosses; market orders fill at next bar
- **Capacity**: if strategy trades >1% of daily volume, it will move the market
- **Short availability**: not all stocks are borrowable — check borrow rates

### 3. Walk-Forward Analysis
- Train model on window of N days, test on next M days
- Slide window forward by M days and repeat
- Aggregate all out-of-sample windows for true performance estimate
- This prevents look-ahead bias from parameter selection

### 4. Statistical Validation
- **Sharpe ratio**: >1.0 out-of-sample is strong; >1.5 is excellent
- **t-statistic of returns**: require >2.0 (95% confidence returns are non-zero)
- **Max drawdown**: compare to buy-and-hold; strategy drawdown should be smaller
- **Profit factor**: gross profit / gross loss; require >1.5
- **Win rate vs payoff**: 40% win rate is fine if avg win > 2x avg loss

## Overfitting Red Flags

| Red Flag | What It Means |
|----------|--------------|
| Sharpe > 3.0 in backtest | Almost certainly overfit |
| Strategy has >5 tunable parameters | Degrees of freedom too high |
| Performance drops 50%+ out-of-sample | Parameters are fit to noise |
| Only works on one asset | Not generalizable |
| Turnover > 200% monthly | Likely trading on noise |

## Anti-Overfitting Techniques

1. **Fewer parameters**: 2-3 max for any single strategy
2. **Cross-asset validation**: if it works on SPY, test on EFA and EEM
3. **Combinatorial purged cross-validation**: accounts for temporal dependence
4. **Deflated Sharpe Ratio**: adjusts for multiple testing (number of strategies tried)
5. **Monte Carlo permutation**: shuffle signal-return mapping; real signal should beat 95% of random

## Reporting Template

Every backtest report must include:
- Strategy description (plain English, no code)
- Date range and universe
- Number of parameters and how they were selected
- In-sample AND out-of-sample results
- Transaction cost assumptions
- Max drawdown with dates
- Comparison to buy-and-hold benchmark
