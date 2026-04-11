---
name: Tail Risk Hedging
description: Protect portfolios against extreme events using put spreads, VIX instruments, and convexity strategies
version: "1.0.0"
author: ROOT
tags: [strategy, tail-risk, hedging, options, VIX, convexity]
platforms: [all]
---

# Tail Risk Hedging

Systematically protect portfolios against extreme drawdowns using convex instruments that provide asymmetric payoffs during market crashes.

## Crash Insurance Philosophy

- **Goal**: Limit max portfolio drawdown to 10-15% even in a 2008/2020-style crash (-35% to -55%)
- **Cost budget**: Allocate 0.5-2% of portfolio annually to tail hedges; treat as insurance premium
- **Convexity**: Seek instruments that gain 5-20x in crashes; small premium, massive payoff
- **Rebalancing alpha**: Hedged portfolio can rebalance into crash at better prices (behavioral + financial edge)
- **Negative carry**: Tail hedges lose money 90% of the time; must accept sustained bleed for crash protection

## Put Spread Strategies

- **Far OTM puts**: Buy 10-15% OTM SPX puts, 1-3 month expiry; pure crash protection
- **Put spreads**: Buy 10% OTM put, sell 25% OTM put; reduces cost by 40-60% while capping protection
- **Ratio put spreads**: Buy 1x ATM put, sell 3x 15% OTM puts; zero-cost but naked below lower strike
- **Rolling schedule**: Roll monthly, 1-3 months to expiry; stagger across 3 expiry dates for continuity
- **Sizing**: `notional_protected = put_delta_at_crash * num_contracts * 100 * SPX_price`
- **Strike selection**: Below the "crash point" where forced liquidation begins (-15% to -20% from spot)

## VIX-Based Hedging

- **VIX calls**: Buy 1-2 month VIX calls at strike 25-30; profit when VIX spikes from 15 to 40+
- **VIX call spread**: Buy VIX 25 call, sell VIX 50 call; reduces cost while capturing main spike range
- **VIX futures**: Long VIX futures (caution: contango bleeds ~5% monthly in calm markets)
- **VIX/VIX ratio**: `VIX / VIX3M < 0.85` (steep contango) = cheap protection; initiate hedges here
- **VVIX filter**: When VVIX < 80, VIX options are cheap; when VVIX > 120, protection is expensive
- **Sizing**: VIX calls provide ~$1000 per point above strike per contract; size to cover target loss

## Convexity Instruments

- **Long gamma far OTM**: Deep OTM options (5-10 delta) have highest convexity; gain accelerates as spot moves
- **Swaptions**: In rates space, receiver swaptions protect against rate collapse during flight-to-quality
- **CDS index**: Buy CDX HY protection; spikes during credit events; 3-5x return in crisis
- **Gold calls**: Far OTM gold calls benefit from flight-to-safety and dollar debasement narratives
- **Crypto puts**: For crypto portfolios, BTC puts provide protection against 50%+ drawdowns

## Sizing Framework

- **Target protection level**: Define max acceptable portfolio drawdown (e.g., -15%)
- **Crash scenario**: Assume SPX -30%, VIX to 60, credit spreads +500bps
- **Required payoff**: `hedge_payoff = portfolio_value * (crash_loss - target_max_loss)`
- **Premium budget**: `annual_cost = hedge_payoff / expected_payoff_multiplier * probability_adjustment`
- **Rule of thumb**: Spend 1% of portfolio for 10x payoff in a -30% crash; adjust by current vol level
- **Rebalance trigger**: If hedge gains > 50% in a spike, take partial profits and re-establish at new strikes

## Dynamic Hedging Regime

| VIX Level | Implied Correlation | Action |
|-----------|-------------------|--------|
| < 15 | Low | Maximum hedge allocation; protection cheapest |
| 15-20 | Normal | Standard hedge budget; maintain rolling program |
| 20-30 | Elevated | Reduce new purchases; existing hedges gaining |
| > 30 | Crisis | Take profits on hedges; redeploy into risk assets |

## Risk Management

- **Time decay management**: Never let hedges expire worthless if > 50% of time to expiry remains; roll
- **Basis risk**: VIX hedges don't perfectly correlate with portfolio losses; ensure instrument matches exposure
- **Counterparty risk**: OTC hedges carry counterparty default risk precisely when needed most; prefer exchange-traded
- **Crowding**: When everyone hedges simultaneously (high put/call ratio), protection is expensive and less effective
- **Over-hedging**: Too much protection creates massive negative carry; portfolio underperforms in bull markets
- **Monetization plan**: Pre-define levels at which to take profits on hedges (e.g., VIX > 40 = sell 50% of VIX calls)
