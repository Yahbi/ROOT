---
name: Volatility Trading
description: Trade volatility directly via VIX, volatility surface, and variance strategies
version: "1.0.0"
author: ROOT
tags: [strategy, volatility, VIX, options, variance]
platforms: [all]
---

# Volatility Trading Strategy

Trade volatility as an asset class using VIX products, options strategies, and variance instruments.

## VIX Term Structure Trading

### Contango (Normal: VIX futures > spot)
- VIX futures roll down toward spot as expiry approaches
- **Strategy**: short VIX futures or short UVXY/VXX (vol ETPs decay over time)
- **Entry**: when VIX term structure slope > 5% (front month vs second month)
- **Stop**: if VIX spot spikes above 25, close all short-vol positions immediately

### Backwardation (Stress: VIX futures < spot)
- Indicates market panic — near-term fear exceeds longer-term
- **Strategy**: buy VIX futures or calls (hedge portfolio) OR wait for reversion
- **Contrarian entry**: when VIX > 35 and term structure inverts, start selling vol in back months
- **Sizing**: small — backwardation regimes are volatile and unpredictable

## Volatility Surface Strategies

### Skew Trading
- Equity put skew = OTM puts cost more than OTM calls (crash protection premium)
- When skew is extreme (>10 delta put IV / ATM IV > 1.5): sell put spreads
- When skew is flat: buy put spreads as crash hedges (cheap insurance)

### Calendar Spreads
- Sell near-term options, buy longer-term at same strike
- Profits when near-term IV decays faster (typical in contango)
- Best before known events: sell pre-event expiry, buy post-event expiry

### Volatility Risk Premium Harvest
- Implied vol systematically overestimates realized vol by 2-4 points
- Sell ATM straddles on index (SPY), delta-hedge daily
- Collect the vol risk premium over time (insurance premium analogy)
- Risk: large gap moves destroy this strategy — always cap exposure

## Variance Swaps (Institutional)

- Pay fixed variance, receive realized variance (or vice versa)
- Variance swap payoff: notional * (realized_var - strike_var)
- Convexity: variance is quadratic in vol — large moves pay disproportionately
- Available via OTC dealers or replicated with options strip

## Risk Management

| Rule | Threshold |
|------|-----------|
| Max short-vol exposure | 10% of portfolio notional |
| VIX stop-loss | Close shorts if VIX > 25 |
| Max calendar spread risk | 2% of portfolio per spread |
| Hedging requirement | Always hold VIX calls or put spreads as tail hedge |
| Position review | Daily during market hours |

## Key Principles

1. Volatility mean-reverts — extreme VIX readings (>30 or <12) are tradeable
2. Short volatility is like picking up pennies — profitable until it is catastrophic
3. Always hedge tail risk — the one time you do not hedge is when it blows up
4. VIX ETP decay (UVXY, VXX) is a real edge but requires strict risk management
5. Combine vol trading with directional views for higher expected Sharpe
