---
name: Volatility Trading
description: Trade realized vs implied volatility spread using VIX products, options, and variance swaps
version: "1.0.0"
author: ROOT
tags: [trading, volatility, VIX, options, vega, variance]
platforms: [all]
difficulty: advanced
---

# Volatility Trading

Volatility is an asset class. Trade it by exploiting the persistent gap between implied (IV)
and realized (RV) volatility, and by positioning around volatility regime changes.

## Key Concepts

- **Implied Volatility (IV)**: Market's expectation of future volatility (priced into options)
- **Realized Volatility (RV)**: Actual observed volatility in the underlying
- **Volatility Risk Premium (VRP)**: IV - RV (historically positive — sellers collect premium)
- **IV Rank**: Current IV vs. past 52-week range (0-100%)
- **VIX**: CBOE Volatility Index — 30-day implied vol for S&P 500

## The Volatility Risk Premium Edge

Historically: IV exceeds RV about 80% of the time by ~3-5 vol points.
This is the core edge for short volatility strategies.

```
If AAPL IV = 35% and actual realized vol = 22%
→ Seller of options collects 13 vol points of excess premium
→ This edge persists but can blow up during crisis events
```

## Trading Instruments

| Product | Exposure | Use Case |
|---------|----------|---------|
| VXX / UVXY | Long vol (ETF) | Crisis hedging, spike plays |
| SVXY | Short vol (ETF) | Harvest VRP in calm markets |
| SPX options | Pure vega | Precise vol positioning |
| VIX futures | Term structure plays | Calendar spreads |
| Variance swaps | Realized vs implied | Institutional VRP harvesting |
| VIX calls | Cheap crisis hedge | Tail risk protection |

## VIX Term Structure Strategies

### Contango Trade (Normal Market)
- VIX futures trade at premium to spot VIX (contango) ~75% of the time
- Short front-month VIX futures → profit from roll-down as expiry approaches
- Risk: VIX spikes above entry price (require stop-loss at 2x entry)

### Backwardation Trade (Fear Event)
- During market stress, front-month VIX > back-month (backwardation)
- Long front-month / short back-month calendar spread
- Profit: backwardation normalizes as fear subsides

## IV Rank-Based Options Strategies

```
IV Rank 0-20%  → Buy options (underpriced vol)
                  Straddles, strangles, long calls/puts
IV Rank 20-50% → Neutral strategies
                  Iron condors, calendars, diagonals
IV Rank 50-80% → Sell options (overpriced vol)
                  Covered calls, cash-secured puts, credit spreads
IV Rank > 80%  → Aggressive premium selling
                  Iron condors with wide strikes, ratio spreads
```

## Volatility Regime Detection

1. **Calm regime** (VIX < 15): Short vol, sell premium, harvest VRP
2. **Normal regime** (VIX 15-25): Mixed strategies, neutral stance
3. **Elevated regime** (VIX 25-35): Reduce short vol, add hedges
4. **Crisis regime** (VIX > 35): Close short vol immediately, consider long vol

### Regime Change Signals
- VIX term structure flip to backwardation → danger warning
- VIX 1-day move > 20% → elevated stress signal
- SPX 1-month realized vol > IV → unusual, investigate cause
- VVIX (vol of vol) spike > 120 → extreme instability

## Risk Management (Critical for Short Vol)

Short volatility can lose multiples of premium collected in crisis events:

1. **Position limits**: Max 15% of portfolio in short-vol strategies
2. **VIX stop**: Close all short vol if VIX crosses 30 from below
3. **Tail hedges**: Always hold small position in VIX calls or long puts
4. **Never short naked**: Always define maximum loss with spreads
5. **Correlation warning**: Short vol + short equities = double-exposure to crashes

## Calendar Spread Technique

```
Sell 30-DTE ATM straddle (high theta)
Buy  60-DTE ATM straddle (less theta decay)
Net: short front-month vol, long back-month vol
Profit: IV remains stable or falls; front-month decays faster
Risk: IV spikes sharply → both legs lose value
```

## Monitoring Dashboard

Track daily:
- VIX spot, VIX futures term structure (M1-M7)
- IV Rank for positions held
- VVIX level (vol of vol indicator)
- VRP = 30-day IV vs. 30-day realized vol (rolling)
- Short vol P&L vs. tail hedge cost
