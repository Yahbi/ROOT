---
name: Dividend Strategies
description: Dividend capture, aristocrat selection, yield trap avoidance, and ex-date trading techniques
version: "1.0.0"
author: ROOT
tags: [trading, dividends, income, yield, ex-date]
platforms: [all]
---

# Dividend Strategies

Generate income and exploit dividend-related price anomalies through systematic approaches to dividend-paying equities.

## Dividend Capture Strategy

- **Concept**: Buy before ex-date, collect dividend, sell after; profit if price drop < dividend amount
- **Ex-date mechanics**: Stock opens ex-dividend adjusted down by dividend amount; must own by record date (T+1 from ex-date)
- **Edge**: Tax-advantaged accounts eliminate tax drag; stocks often recover ex-date drop within 1-5 days
- **Entry**: Buy 1-3 days before ex-date; avoid buying same day (price already reflects anticipation)
- **Exit**: Sell 1-5 days after ex-date once price recovers; use 10-day max holding period
- **Filter**: Only capture when yield > 0.5% per event, average daily volume > $10M, spread < 0.1%
- **Expected P&L**: Dividend income minus price decay; net positive ~60% of the time on high-quality names

## Dividend Aristocrats

- **Definition**: S&P 500 companies with 25+ consecutive years of dividend increases
- **Universe**: ~65 companies; sectors: industrials, consumer staples, healthcare overrepresented
- **Selection criteria**: Payout ratio < 60%, free cash flow covers dividend 1.5x, debt/EBITDA < 3
- **Yield trap filter**: Reject if dividend growth rate < inflation (real yield erosion)
- **Portfolio construction**: Equal-weight top 20 by dividend growth rate; rebalance quarterly
- **Historical alpha**: ~1-2% annualized vs S&P 500 with 20% lower drawdowns

## Yield Trap Identification

A high yield often signals distress, not opportunity. Red flags:

- **Payout ratio > 80%**: Unsustainable; earnings decline will force a cut
- **Declining revenue**: 3+ quarters of revenue decline with stable dividend = borrowing to pay
- **Rising debt for dividends**: Debt/equity increasing while FCF stagnant = financial engineering
- **Sector distress**: Entire sector under pressure (e.g., energy 2020, REITs during rate hikes)
- **Yield > 2x sector average**: Almost always a trap; market is pricing in a cut
- **Credit downgrade**: Recent rating downgrade often precedes dividend reduction by 6-12 months

## Ex-Date Trading Patterns

- **Pre-ex-date drift**: Stocks with yield > 3% tend to drift up 0.3-0.5% in 5 days before ex-date
- **Ex-date drop**: Average drop = 85-90% of dividend amount (not full 100% due to tax effects)
- **Post-ex-date recovery**: High-quality names recover full drop within 5-10 trading days on average
- **Options play**: Sell covered calls expiring just after ex-date to capture premium + dividend
- **Special dividends**: Large specials (> 5%) cause significant dislocations; option pricing adjusts poorly

## Dividend Growth Investing

- **Core metric**: 5-year dividend CAGR > 7% with payout ratio trajectory stable or declining
- **Yield on cost**: Initial yield + growth compounds; 2% yield growing 10%/year = 5.2% yield on cost in 10 years
- **DRIP math**: Reinvested dividends compound; `Future_value = D * ((1+g)^n - (1+r)^n) / (g - r)` where g = growth, r = reinvestment return
- **Valuation**: DDM fair value = `D1 / (r - g)` where D1 = next year dividend, r = required return, g = perpetual growth
- **Margin of safety**: Buy only below 80% of DDM fair value; sell above 120%

## Risk Management

- **Concentration limit**: Max 5% portfolio in any single dividend stock; max 25% in any sector
- **Rate sensitivity**: Dividend stocks inversely correlated with rates; reduce when Fed hiking aggressively
- **Dividend cut response**: Sell immediately on announcement; average post-cut decline is 5-10% beyond announcement day
- **Tax efficiency**: Hold > 1 year for qualified dividend rate (15-20%) vs ordinary income (up to 37%)
- **Currency risk**: International dividend stocks have FX exposure; hedge if yield < FX volatility
