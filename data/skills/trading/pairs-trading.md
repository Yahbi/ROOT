---
name: Pairs Trading
description: Statistical arbitrage by trading mean-reverting correlated pairs
version: "1.0.0"
author: ROOT
tags: [trading, statistical-arbitrage, pairs, quantitative]
platforms: [all]
---

# Pairs Trading (Statistical Arbitrage)

Exploit temporary divergences between historically correlated securities.

## Pair Selection

1. **Screen for candidates** — same sector, similar market cap, shared revenue drivers
2. **Cointegration test** — run Engle-Granger or Johansen test (p < 0.05 required)
3. **Correlation filter** — minimum 0.80 rolling 252-day correlation
4. **Verify economic link** — pairs must have fundamental reason to move together
5. **Avoid spurious pairs** — statistical significance alone is insufficient

## Classic Pairs

- XOM / CVX (oil majors)
- KO / PEP (beverages)
- GS / MS (investment banks)
- HD / LOW (home improvement)
- GOOG / META (digital advertising)

## Signal Construction

1. **Compute spread**: spread = log(price_A) - beta * log(price_B)
2. **Calculate z-score**: z = (spread - mean_60d) / std_60d
3. **Entry**: z-score > 2.0 or < -2.0
4. **Exit**: z-score reverts to 0 (or within +/- 0.5)
5. **Stop-loss**: z-score exceeds +/- 3.5 (pair may be broken)

## Execution

| Z-Score | Action |
|---------|--------|
| > +2.0 | SHORT A / LONG B (spread too wide) |
| < -2.0 | LONG A / SHORT B (spread too narrow) |
| -0.5 to +0.5 | Close position (mean reverted) |
| > +3.5 or < -3.5 | Stop-loss — close and reassess pair |

## Position Sizing

- Dollar-neutral: equal dollar value long and short legs
- Beta-neutral: adjust sizes by beta ratio for market-neutral exposure
- Max 5% of portfolio per pair, max 5 active pairs

## Risk Management

- Re-test cointegration monthly — close pair if p-value exceeds 0.10
- Average holding period: 5-20 trading days
- Avoid pairs during earnings for either stock
- Monitor sector-wide shocks that break correlation regimes
- Track pair half-life — shorter half-life = faster mean reversion = better
