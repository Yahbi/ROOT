---
name: Covered Call Strategy
description: Generate consistent income by selling call options against long equity positions
version: "1.0.0"
author: ROOT
tags: [trading, options, income-generation, covered-calls, risk-management]
platforms: [all]
difficulty: intermediate
---

# Covered Call Strategy

Sell upside optionality on existing long positions to collect premium income while capping gains.

## Core Concept

A covered call = long 100 shares + short 1 call option at a higher strike.
Premium collected reduces cost basis; strike price caps maximum profit.

## Strike Selection Framework

| Market Outlook | Strike Choice | Premium | Upside Cap |
|---------------|---------------|---------|------------|
| Neutral/Slightly Bullish | ATM (at-the-money) | High | Low |
| Moderately Bullish | 5-10% OTM | Medium | Moderate |
| Strongly Bullish | 15%+ OTM | Low | High |

## Expiry Selection

1. **30-45 DTE (days to expiration)** — optimal theta decay zone; sell here
2. **Weekly options** — higher annualized yield but require active management
3. **Leaps (> 365 DTE)** — low premium, not recommended for income generation
4. **Roll rule**: Close and re-sell at 50% of max profit or 21 DTE, whichever comes first

## Execution Steps

1. Identify long equity positions with > 100 shares held
2. Screen for IV Rank > 30 (implied volatility above historical average)
3. Select strike 5-10% OTM with 30-45 DTE
4. Calculate annualized yield: (premium / stock price) * (365 / DTE) * 100
5. Target minimum 8-12% annualized yield before entering
6. Sell to open 1 call contract per 100 shares
7. Set GTC buy-to-close order at 50% of premium collected

## Risk Management

- **Assignment risk**: Stock gets called away if price exceeds strike at expiry
  - Accept assignment if unwilling to hold, or roll before expiry
  - Roll up and out: buy back current call, sell higher strike / further expiry
- **Downside protection**: Premium provides partial hedge (e.g., $3 premium = $3/share protection)
- **Avoid earnings**: Never hold short call through earnings — IV crush cuts premium value
- **Position limit**: Do not sell calls on more than 30% of portfolio value simultaneously

## Rolling Mechanics

```
When to roll:
  - Position at 50% profit → close early, lock gains, redeploy capital
  - Approaching expiry (21 DTE) → roll to next month to avoid gamma risk
  - Stock surging past strike → roll up and out (pay debit, extend time)
  - Stock crashing hard → let call expire worthless, sell new call at lower strike
```

## Tax Considerations

- Short-term capital gains apply to option premiums (< 1 year)
- Assignment triggers stock sale — track holding period for long-term rates
- Wash sale rules apply if stock is repurchased within 30 days after assignment
- Qualified covered calls (QCC) rules affect holding period calculation

## Performance Metrics

- **Monthly premium yield**: premium / (stock price * shares) * 100
- **Cost basis reduction**: track cumulative premium received vs. stock cost
- **Rolling win rate**: % of rolls that improved position
- **Assignment rate**: % of expirations resulting in share call-away

## Example Trade

```
Stock: AAPL @ $195
Sell: 1x AAPL $210 Call, 35 DTE, $3.50 premium
Premium collected: $350 (per contract)
Annualized yield: ($3.50 / $195) * (365 / 35) * 100 = 18.7%
Breakeven: $195 - $3.50 = $191.50
Max profit: ($210 - $195 + $3.50) * 100 = $1,850
```
