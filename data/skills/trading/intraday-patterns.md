---
name: Intraday Patterns
description: Exploit recurring time-of-day price patterns including opening range, VWAP, and power hour dynamics
version: "1.0.0"
author: ROOT
tags: [trading, intraday, daytrading, VWAP, patterns]
platforms: [all]
---

# Intraday Patterns

Trade recurring time-based market behaviors driven by institutional order flow, market structure, and participant psychology.

## Opening Range Breakout (ORB)

- **Define range**: First 15 or 30 minutes of trading session (9:30-10:00 ET for US equities)
- **Entry**: Break above OR high = long; break below OR low = short
- **Confirmation**: Volume on breakout bar > 1.5x average opening bar volume
- **Target**: 1x opening range width from breakout point; extend to 2x if momentum strong
- **Stop**: Opposite side of opening range; if range > 1% of price, use 0.5x range
- **Filter**: Only trade ORB when prior day closed within 0.5% of a key level (support/resistance)
- **Win rate**: ~55-60% with proper filtering; profit factor 1.3-1.8x

## VWAP Reversion

- **VWAP formula**: `VWAP = SUM(Price_i * Volume_i) / SUM(Volume_i)` cumulative from session open
- **Mean reversion**: Price tends to revisit VWAP; deviation > 2 standard deviations triggers fade
- **VWAP bands**: 1st band = 1 StdDev, 2nd = 2 StdDev; 2nd band touch = high-probability reversion
- **Long setup**: Price touches lower 2nd band with decelerating selling delta; target VWAP
- **Short setup**: Price touches upper 2nd band with decelerating buying delta; target VWAP
- **Institutional use**: Large orders benchmark to VWAP; expect defense and reversion near it
- **Avoid**: Trend days where price stays on one side of VWAP all session (10-15% of days)

## Power Hour (3:00-4:00 PM ET)

- **Behavior**: Institutional MOC (market-on-close) orders create directional momentum
- **MOC imbalance**: Published at 3:50 PM; large imbalance (> $1B) predicts final 10-minute direction
- **Strategy**: Fade early power hour mean-reversion if price extended; trend-follow after 3:50 on imbalance
- **Volume pattern**: Last 30 minutes = 15-20% of daily volume; breakouts here have follow-through
- **Avoid fading**: If power hour move aligns with day's trend direction, do not counter-trend trade

## Gap Fill Trading

- **Gap types**: Common (fill same day, 70% probability), breakaway (no fill, trend start), exhaustion (fill = reversal)
- **Fill probability**: Gaps < 1% fill same day ~70% of time; gaps > 2% fill same day only ~30%
- **Long on gap down**: Buy if gap fills 50% within first hour and holds; target full fill
- **Short on gap up**: Sell if gap fills 50% within first hour and holds; target full fill
- **Avoid**: Earnings gaps, news-driven gaps > 3%, gaps that expand in first 15 minutes

## Time-of-Day Volume Pattern (U-Shape)

| Time Window | Volume % | Character |
|------------|----------|-----------|
| 9:30-10:00 | 15-20% | High volatility, emotional, news-driven |
| 10:00-11:30 | 20-25% | Trend establishment, institutional positioning |
| 11:30-2:00 | 15-20% | Low volume, choppy, avoid trading |
| 2:00-3:00 | 15-20% | Repositioning, pre-close preparation |
| 3:00-4:00 | 20-25% | MOC flows, trend resolution, high conviction moves |

## Risk Management

- **Session risk limit**: Max 1% account loss per day; stop trading after 3 consecutive losers
- **Avoid midday**: 11:30-2:00 ET produces most false signals; if no setup by 11:30, wait for 2 PM
- **Size by volatility**: Reduce position size by 50% in first 15 minutes (widest spreads, highest slippage)
- **News filter**: No intraday pattern trades within 30 minutes of FOMC, CPI, NFP releases
- **Instrument selection**: Trade only stocks with > $5M average daily volume and spreads < 0.05%
