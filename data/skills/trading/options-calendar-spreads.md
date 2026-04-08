---
name: Options Calendar Spreads
description: Profit from time decay differences using same-strike options at different expiry dates
version: "1.0.0"
author: ROOT
tags: [trading, options, calendar-spreads, theta, time-decay, advanced]
platforms: [all]
difficulty: advanced
---

# Options Calendar Spreads

Exploit differential time decay by selling a near-term option and buying a later-term option
at the same strike. Profit when the underlying stays near the strike and front-month decays faster.

## Structure

```
Calendar Spread:
  Sell 1x 30-DTE ATM Call @ $3.00
  Buy  1x 60-DTE ATM Call @ $5.00
  Net debit: -$2.00 (max risk)

Profit zone: Stock stays near the strike until front-month expires
Max profit:  Realized when front-month expires worthless (collect $3.00, still own $4.50 back-month)
Max loss:    Net debit paid ($2.00) — occurs if stock moves far from strike
```

## Types of Calendar Spreads

| Type | Long Leg | Short Leg | Outlook |
|------|----------|-----------|---------|
| Call calendar | Far-month call | Near-month call | Neutral to slightly bullish |
| Put calendar | Far-month put | Near-month put | Neutral to slightly bearish |
| Double calendar | Far-month strangle | Near-month strangle | Neutral, benefits wider zone |
| Diagonal | Far-month OTM | Near-month ATM | Directional with time component |

## Strike Selection

- **ATM calendar**: Neutral outlook, maximum profit when stock pins strike
- **OTM call calendar**: Bullish bias — profit zone shifts above current price
- **OTM put calendar**: Bearish bias — profit zone shifts below current price
- **Double calendar**: Sell ATM strangle, buy 60-DTE strangle → wider profit tent

## Optimal Conditions

1. **Flat underlying**: Stock expected to remain near current price for 30 days
2. **IV term structure**: Front-month IV > back-month IV (contango in vol term structure)
   - Sell expensive near-term vol, buy cheaper far-term vol
   - Avoid calendars when IV term structure is inverted (backwardation)
3. **Post-earnings**: Enter after a big move with low near-term IV, or right after earnings
4. **Low IV environment**: Back-month is cheap, limiting capital at risk

## Profit/Loss Mechanics

```
At front-month expiry:
  If stock = strike:     Max profit (front expired worthless, back still has value)
  If stock ± 5% away:    Near breakeven or small profit
  If stock ± 10%+ away:  Loss (both options lose intrinsic alignment)

The position has a "tent-shaped" profit zone around the strike at front-month expiry.
```

## Volatility Impact

- **Rising IV (both months)**: Helps the position — back-month gains more than front-month
- **Falling IV (both months)**: Hurts position — back-month loses more than front-month
- **IV increase in near-month only**: Hurts (short near-term vega)
- **IV collapse in near-month**: Benefits (short leg loses value faster)

## Management Rules

```
Enter:  When IV rank 20-50% and outlook is neutral for 30 days
Adjust: Roll short leg to next month if position at max profit before expiry
Exit:   At 25-35% of max profit (calendars have limited upside)
Stop:   If back-month value drops to less than net debit paid (full loss scenario)
```

## Diagonal Spreads (Calendar Variation)

```
Diagonal = Different strike + Different expiry:
  Sell 30-DTE $210 Call @ $2.00 (slightly OTM)
  Buy  90-DTE $200 Call @ $7.00 (ATM, deeper in time)
  Net debit: -$5.00

Benefit: Can be set up for small credit if back-month is deep ITM
Use case: Replacement for covered calls (less capital required than owning stock)
```

## Rolling the Short Leg

When front-month expires or is near expiry:
1. Close the expiring short option (or let expire worthless)
2. Sell next month's ATM option against remaining long leg
3. Transform calendar into ongoing "poor man's covered call" or "PMCC"
4. Continue rolling monthly to collect premium against the long LEAPS position

## PMCC (Poor Man's Covered Call)

```
Buy LEAPS (1-2 year) deep ITM call @ 70+ delta as stock proxy
Sell monthly 30-DTE OTM call against it
Net cost: ~20-30% of owning 100 shares outright
Behaves like covered call at fraction of capital
Roll short call monthly; collect premium indefinitely
```

## Risk Factors

- **Gap move**: Large overnight gap beyond profit zone → significant loss
- **IV crush**: If implied vol drops sharply in both months, back-month loses too much
- **Early assignment**: Short near-month call exercised early (deep ITM American-style)
  - Solution: Use European-style cash-settled index options (SPX, NDX)
- **Liquidity**: Wide bid-ask spreads on back-month — use limit orders, patient fills
