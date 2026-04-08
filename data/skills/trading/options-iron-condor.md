---
name: Iron Condor Strategy
description: Profit from low-volatility environments by selling OTM puts and calls simultaneously
version: "1.0.0"
author: ROOT
tags: [trading, options, iron-condor, premium-selling, neutral-strategy]
platforms: [all]
difficulty: advanced
---

# Iron Condor Strategy

Collect premium by selling an OTM call spread and OTM put spread simultaneously.
Best deployed when implied volatility is elevated and the underlying is expected to trade sideways.

## Structure

```
Iron Condor = Short Put Spread + Short Call Spread

Example (SPY @ $450):
  Buy  $420 Put  (lower wing protection)
  Sell $430 Put  (collect premium)
  Sell $470 Call (collect premium)
  Buy  $480 Call (upper wing protection)

Width of spreads: $10 each
Net credit: $1.80 (collect)
Max profit: $180/contract (keep credit if SPY stays 430-470)
Max loss:   $820/contract ($1000 spread width - $180 credit)
```

## Setup Criteria

1. **IV Rank > 40**: Elevated implied volatility means richer premiums
2. **Underlying trend neutral**: No strong directional momentum
3. **30-45 DTE**: Optimal theta decay, maximum premium collection zone
4. **Strike selection**:
   - Short strikes at 1 standard deviation (16 delta) or 2 SD (5 delta) from price
   - 1 SD: ~68% probability of expiring worthless — more premium, more risk
   - 2 SD: ~95% probability — less premium, higher win rate
5. **Spread width**: 5-10% of underlying price; wider = more premium and more risk

## Position Sizing

- Max risk per trade: 2-5% of account value
- Calculate: max loss = (spread width - net credit) * 100 * contracts
- Example: $10 spread - $1.80 credit = $8.20 max loss * 100 = $820 per contract
- With $50k account and 5% max risk = $2,500 / $820 = 3 contracts max

## Management Rules

| Situation | Action |
|-----------|--------|
| 50% of max profit reached | Close entire position — lock in gains |
| 21 DTE remaining | Close or roll to next month |
| Short strike breached | Close untested side (opposite spread), roll tested side |
| Underlying moves > 1 SD | Consider closing for small loss before it worsens |
| Position at 2x credit received | Close — max loss defense |

## Adjustment Techniques

### One-Sided Roll
When price approaches one short strike:
1. Close the threatened spread for a debit
2. Re-sell further OTM in same or later expiry
3. Net: accept smaller total credit or debit for more safety room

### Convert to Broken Wing Butterfly
When one side is tested:
1. Move the untested long option to the same strike as the tested short
2. Creates asymmetric risk — protects one side, limits the other
3. Can reduce or eliminate max loss on the tested side

## Greeks Profile

| Greek | Effect on Iron Condor |
|-------|----------------------|
| Theta (time decay) | Positive — decay works in your favor daily |
| Vega (volatility) | Negative — rising IV hurts, falling IV helps |
| Delta | Near-zero initially — position is delta neutral |
| Gamma | Negative — large moves are harmful |

## Best Underlying Assets

- **Index ETFs**: SPY, QQQ, IWM (less single-stock risk, cash-settled)
- **High-liquidity stocks**: AAPL, TSLA, NVDA (tight spreads)
- **Avoid**: earnings announcements, FDA decisions, macro events within the expiry window

## Earnings Avoidance

- Check earnings calendar before entry: no earnings within expiry period
- IV typically spikes before earnings (good for premium) then collapses after
- If earnings fall within position window: close before the event or skip the trade

## Performance Tracking

- **Win rate**: target > 70% (2 SD strikes) or > 55% (1 SD strikes)
- **Average credit collected vs. average loss**: Risk/reward must be acceptable
- **Average DTE at close**: shorter = faster capital recycling
- **IV rank at entry**: track whether high-IV entries outperform
