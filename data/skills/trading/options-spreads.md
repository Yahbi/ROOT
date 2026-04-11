---
name: Options Vertical Spreads
description: Define risk directional plays using bull call spreads, bear put spreads, and credit spreads
version: "1.0.0"
author: ROOT
tags: [trading, options, spreads, credit-spreads, debit-spreads, directional]
platforms: [all]
difficulty: intermediate
---

# Options Vertical Spreads

Control risk on directional options plays by buying and selling options at different strikes.
Defined risk means maximum loss is known at entry — no unlimited risk exposure.

## Spread Types Overview

| Spread | Outlook | Structure | Profit From |
|--------|---------|-----------|------------|
| Bull Call Spread | Bullish | Buy lower call + Sell higher call | Price rise |
| Bear Put Spread | Bearish | Buy higher put + Sell lower put | Price drop |
| Bull Put Spread | Neutral-bullish | Sell higher put + Buy lower put | Price stays above sold strike |
| Bear Call Spread | Neutral-bearish | Sell lower call + Buy higher call | Price stays below sold strike |

## Bull Call Spread (Debit Spread)

```
Setup (AAPL @ $190):
  Buy  $190 Call (ATM) @ $5.00
  Sell $200 Call (OTM) @ $2.50
  Net debit: -$2.50/share (-$250/contract)

Max profit: ($200 - $190 - $2.50) * 100 = $750
Max loss:   $2.50 * 100 = $250
Breakeven:  $190 + $2.50 = $192.50
Risk/reward: $750 max profit / $250 max loss = 3:1
```

Use when: Moderately bullish with defined risk.
Avoid when: Expecting extreme move (long call captures more upside).

## Bear Put Spread (Debit Spread)

```
Setup (SPY @ $450):
  Buy  $450 Put (ATM) @ $6.00
  Sell $435 Put (OTM) @ $3.00
  Net debit: -$3.00/share (-$300/contract)

Max profit: ($450 - $435 - $3.00) * 100 = $1,200
Max loss:   $3.00 * 100 = $300
Breakeven:  $450 - $3.00 = $447
```

## Bull Put Spread (Credit Spread)

```
Setup (SPY @ $450):
  Sell $440 Put @ $4.00
  Buy  $430 Put @ $2.00
  Net credit: +$2.00/share (+$200/contract)

Max profit: $200 (keep credit if SPY stays above $440)
Max loss:   ($440 - $430 - $2.00) * 100 = $800
Breakeven:  $440 - $2.00 = $438
```

## Strike Selection Guidelines

### Debit Spreads (directional bet)
- Lower strike (long leg): ATM or slightly OTM — captures most delta
- Upper strike (short leg): Target 1:2 or 1:3 risk/reward ratio
- Width: Typically 5-10% of stock price
- Expiry: 30-60 DTE for balance of time value and gamma

### Credit Spreads (income / neutral play)
- Short strike: 1 standard deviation OTM (16 delta) — highest probability
- Long strike: 5-10 points further OTM for protection
- Expiry: 30-45 DTE for optimal theta decay
- Min credit: 30% of spread width (e.g., $10 spread → at least $3 credit)

## Management Rules

```
Debit spreads:
  - Close at 50% of max profit (secure gains)
  - Let expire worthless if out of the money at expiry
  - Roll 2-3 weeks before expiry if still on track

Credit spreads:
  - Close at 50% of max profit (don't be greedy)
  - Close if position reaches 2x credit received (loss management)
  - Roll down and out if short strike is breached
```

## Greek Analysis

| Greek | Debit Spread | Credit Spread |
|-------|-------------|---------------|
| Delta | Positive (bull call) | Positive net (bull put) |
| Theta | Negative (time decay hurts) | Positive (time decay helps) |
| Vega | Positive (IV rise helps) | Negative (IV rise hurts) |
| Gamma | Positive near lower strike | Negative near short strike |

## Probability Framework

```python
# Estimate probability of profit for credit spread
prob_OTM = N(-delta)  # Black-Scholes approximation
# 16-delta short strike → ~84% chance of expiring worthless

# For debit spread:
prob_profit = N((S - breakeven) / (sigma * sqrt(T)))
```

## Common Mistakes

1. **Too narrow spread**: Low max profit relative to cost; move strikes farther apart
2. **Not managing winners**: Many traders hold credit spreads to expiry; 50% rule prevents disasters
3. **Ignoring IV**: Buying debit spreads in high-IV environment overpays for options
4. **Wrong expiry**: Too short (< 21 DTE) causes excessive gamma risk for credit spreads
5. **Over-sizing**: Define risk per position; max 3-5% account on any single spread

## Spread Selection Cheat Sheet

```
High conviction directional play → Debit spread (bull call or bear put)
Income in neutral market → Credit spread (bull put or bear call)
Earnings play (limited budget) → Debit spread before earnings
High IV environment → Credit spread (sell rich premium)
Low IV environment → Debit spread (buy cheap premium)
```
