---
name: Seasonal Patterns
description: Exploit recurring calendar-based market anomalies including January effect, sell in May, and earnings seasonality
version: "1.0.0"
author: ROOT
tags: [strategy, seasonal, calendar, anomalies, timing]
platforms: [all]
---

# Seasonal Patterns

Trade statistically significant calendar-based return patterns driven by institutional flows, tax behavior, and behavioral biases.

## January Effect

- **Pattern**: Small-cap stocks outperform large-caps in January, especially first 5 trading days
- **Cause**: Tax-loss selling in December depresses small-caps; January buying creates rebound
- **Magnitude**: Historically +2-5% small-cap excess return in January (diminished post-publication)
- **Implementation**: Buy IWM (Russell 2000) in late December, sell end of January
- **Filter**: Stronger after years with large December small-cap declines; weak after flat December
- **Modern alpha**: Effect has shifted earlier; "January effect" now often starts in mid-December

## Sell in May (Halloween Effect)

- **Pattern**: November-April returns significantly exceed May-October returns across global markets
- **Statistics**: Nov-Apr average +7.1% vs May-Oct +1.6% (S&P 500, 1950-2023)
- **Implementation**: Overweight equities Nov 1 - Apr 30; rotate to bonds/cash May 1 - Oct 31
- **Enhancement**: Use 200-day MA as confirmation; only go defensive in May if price < 200-day MA
- **Sharpe improvement**: Strategy improves Sharpe ratio from 0.5 to 0.8 with similar CAGR and lower drawdowns
- **Robust across markets**: Validated in 37 of 39 countries studied; strongest in European markets

## Santa Claus Rally

- **Window**: Last 5 trading days of December + first 2 trading days of January
- **Average return**: +1.3% (S&P 500); positive in 75% of years since 1950
- **Barometer**: If Santa rally fails, it signals potential weakness for Q1 (Yale Hirsch indicator)
- **Cause**: Low volume, tax positioning complete, window dressing by fund managers, retail optimism
- **Trade**: Go long SPY on December 24th close; exit January 3rd close
- **Caution**: Edge is small; only trade as confirmation of bullish seasonal thesis, not standalone

## Earnings Seasonality

- **Pre-earnings drift**: Stocks tend to drift up 1-2% in 10 days before earnings announcements
- **Post-earnings announcement drift (PEAD)**: Earnings surprises continue in the same direction for 60 days
- **Earnings season timing**: Most companies report in Jan/Apr/Jul/Oct (first 3 weeks)
- **VIX pattern**: VIX rises into earnings season, falls after majority have reported
- **Strategy**: Buy calls 10 days before earnings for drift; buy straddles for vol expansion; trade PEAD after
- **Sector rotation**: Technology reports late in season; financials report early; stagger exposure

## Monthly and Weekly Patterns

- **Turn-of-month effect**: Last day and first 3 days of each month outperform; driven by pension/401k flows
- **Monthly return**: ~65% of monthly S&P 500 returns accrue in the turn-of-month window
- **Monday effect**: Mondays historically weakest day; Friday strongest (diminished in recent decades)
- **Options expiration**: Monthly OpEx (3rd Friday) tends to pin near max pain; increased gamma volatility
- **Quarter-end rebalancing**: Large flows in final days of quarter as funds rebalance; predictable direction

## Commodity Seasonality

- **Natural gas**: Rally Aug-Nov (winter heating demand); decline Mar-May (shoulder season)
- **Crude oil**: Strength Feb-Jun (refinery maintenance, driving season buildup); weakness Sep-Nov
- **Grains**: Corn/wheat seasonal lows in harvest (Sep-Nov); highs in spring (planting uncertainty)
- **Gold**: Strongest Sep-Feb (Indian wedding season, Chinese New Year); weakest Jun-Aug
- **Implementation**: Use futures or commodity ETFs; enter 2 weeks before historical seasonal start

## Risk Management

- **Sample size**: Require 30+ years of data; patterns based on <20 years are statistically unreliable
- **Publication effect**: Many anomalies weaken after academic publication; verify persistence in recent data
- **Regime dependence**: Seasonal patterns work best in normal markets; overridden by recessions and crises
- **Sizing**: Seasonal patterns are modest edges (0.5-2%); size appropriately with tight stops
- **Confirmation**: Combine seasonal with momentum/mean-reversion signals; seasonal alone is insufficient
- **Cost awareness**: Many seasonal trades are short-duration; transaction costs and slippage can erode edge
- **Never force**: If price action contradicts seasonal expectation, trust price over calendar
