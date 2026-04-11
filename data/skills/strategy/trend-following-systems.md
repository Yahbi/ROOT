---
name: Trend Following Systems
description: Systematic trend capture using Turtle rules, Donchian channels, ATR stops, and pyramiding
version: "1.0.0"
author: ROOT
tags: [strategy, trend-following, momentum, CTA, systematic]
platforms: [all]
---

# Trend Following Systems

Capture extended price movements across all asset classes using systematic, rules-based trend detection and position management.

## Turtle Trading Rules (Classic)

- **Entry (System 1)**: Buy on 20-day Donchian breakout (new 20-day high); short on 20-day low
- **Entry (System 2)**: Buy on 55-day breakout; used when System 1 signal was skipped
- **Exit**: 10-day low for longs (System 1), 20-day low for System 2; always honor the exit
- **Position sizing**: `unit = 1% of equity / (ATR_20 * dollar_per_point)`; risk 1% per unit
- **Pyramiding**: Add 1 unit at each 0.5 ATR increment above entry; max 4 units per market
- **Stop loss**: 2 ATR from entry price; tightens as pyramid grows (last unit's stop = tightest)

## Donchian Channel System

- **Upper channel**: Highest high over N periods (20, 55, or 100 days)
- **Lower channel**: Lowest low over N periods
- **Middle line**: `(Upper + Lower) / 2`; used as trailing stop in some variants
- **Breakout entry**: Close above upper channel = long; close below lower channel = short
- **Filter**: Only take breakouts in direction of 200-day MA slope; avoids counter-trend entries
- **Timeframe selection**: 20-day for short-term; 55-day is robust default; 100-day for slow macro trends

## ATR-Based Position Management

- **ATR (Average True Range)**: `ATR = EMA(max(H-L, |H-C_prev|, |L-C_prev|), 20)`
- **Initial stop**: Entry price +/- 2-3 ATR; wider stops survive noise, tighter stops reduce tail risk
- **Trailing stop**: Highest close minus 3 ATR for longs; advance only (never widen)
- **Chandelier exit**: Highest high of last 22 days minus 3 ATR; popular CTA trailing stop
- **Profit target**: Optional; many trend followers use no target, only trailing stops
- **Volatility normalization**: Size all positions so that 1 ATR move = same dollar P&L across all markets

## Multi-Market Portfolio

- **Diversification**: Trade 30-50 uncorrelated markets (equities, bonds, FX, commodities, crypto)
- **Correlation filter**: Max 3 correlated positions in same sector (e.g., crude + heating oil + gasoline)
- **Risk allocation**: Equal risk per market; `risk_per_market = total_risk / num_markets`
- **Market selection**: Minimum liquidity threshold (ADV > $50M notional); sufficient volatility (ATR > 0.5%)
- **Sector caps**: Max 25% of portfolio risk in any single sector (energy, metals, rates, etc.)

## Pyramiding Strategies

- **Fixed ATR increments**: Add at 0.5 ATR, 1.0 ATR, 1.5 ATR above entry; natural profit-scaling
- **Breakout of breakout**: Add on higher timeframe breakout confirmation (20-day entry, add on 55-day)
- **Pullback add**: Add when trend resumes after pullback to 10-day MA while 50-day MA slope intact
- **Max pyramid units**: 4 per market, 10 per correlated group, 24 portfolio-wide (Turtle rules)
- **Risk on pyramid**: Each add risks 0.5% of equity; total risk per market capped at 2%

## Performance Characteristics

- **Win rate**: Typically 35-45%; profits come from few large winners (heavy right tail)
- **Profit factor**: 1.5-2.5x; expectancy = `(avg_win * win_rate) - (avg_loss * loss_rate)`
- **Drawdowns**: Expect 20-30% max drawdown; extended flat periods of 6-18 months are normal
- **Best environments**: High macro volatility, trending commodity/FX markets, crisis periods
- **Worst environments**: Range-bound, mean-reverting markets with frequent false breakouts

## Risk Management

- **Portfolio heat**: Total open risk across all positions < 20% of equity at any time
- **Correlation adjustment**: If realized correlation between positions > 0.6, treat as single unit for sizing
- **Drawdown throttle**: Reduce position sizes by 25% for each 10% drawdown; resume at new equity highs
- **Regime filter**: Optional — reduce trend exposure when VIX term structure in contango (low vol regime)
- **Rebalance**: Monthly assessment of market roster; remove illiquid markets, add newly trending ones
