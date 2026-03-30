---
name: Prediction Markets
description: Extract trading alpha from prediction market data and probabilities
version: "1.0.0"
author: ROOT
tags: [research, prediction-markets, probabilities, polymarket]
platforms: [all]
---

# Prediction Markets for Trading Alpha

Use prediction market prices as real-time probability estimates for tradeable events.

## Key Platforms

| Platform | Focus | Data Access |
|----------|-------|-------------|
| Polymarket | Crypto, politics, macro events | REST API, on-chain |
| Kalshi | US regulated, economic events | REST API |
| Metaculus | Science, technology, geopolitics | Public API |
| PredictIt | US politics (winding down) | Public data |

## How to Extract Alpha

### 1. Event Probability to Asset Price
- Map prediction market outcomes to affected assets
- Example: "Fed cuts rates in March" at 75% → overweight rate-sensitive stocks
- Example: "US-China tariffs increase" at 60% → reduce China exposure

### 2. Probability Momentum
- Track daily change in contract price (probability)
- Sharp moves (>10% in 24h) signal new information entering the market
- Front-run traditional markets — prediction markets often price events faster

### 3. Calibration Arbitrage
- Compare prediction market probability to options-implied probability
- If Polymarket says 80% chance of event but options price 60%, trade the gap
- Build a mapping: prediction market contracts → options strategies

### 4. Contrarian Signals
- When prediction market reaches 90%+ for an outcome, the trade is crowded
- If the event fails to materialize, assets re-price violently
- Position for the low-probability scenario when risk/reward is asymmetric

## Practical Workflow

1. **Monitor daily**: scan Polymarket/Kalshi for markets with >$500K volume
2. **Map to tradeable assets**: identify which stocks/ETFs/commodities are affected
3. **Compare to market pricing**: check if equity/options markets agree with prediction
4. **Identify mispricings**: act when prediction market and financial markets diverge by >15%
5. **Size conservatively**: prediction markets are thin — overconfidence is the main risk

## Integration with ROOT

- Polymarket bot fetches contract prices on schedule
- MiRo evaluates probability changes against portfolio exposure
- Trading Swarm cross-references prediction signals with technical setup
- Alert when any tracked contract moves >10% in 24 hours

## Risks

- Prediction markets have limited liquidity — prices can be manipulated
- Political markets are noisy and subject to sentiment bubbles
- Always validate with at least one independent data source
- Do not bet the portfolio on a single prediction market signal
