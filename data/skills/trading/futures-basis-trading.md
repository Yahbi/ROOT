---
name: Futures Basis Trading
description: Exploit the spread between futures price and spot price using cash-and-carry and reverse cash-and-carry
version: "1.0.0"
author: ROOT
tags: [trading, futures, basis, arbitrage, cash-and-carry, quantitative]
platforms: [all]
difficulty: advanced
---

# Futures Basis Trading

Capture risk-free (or near-risk-free) returns by exploiting mispricings between
futures contracts and their underlying spot prices.

## Core Concept: The Basis

```
Basis = Spot Price - Futures Price

Theoretical futures price = Spot * e^(r - d) * T
Where:
  r = risk-free rate
  d = dividend yield (or storage cost for commodities)
  T = time to expiration (in years)

If Futures price ≠ Theoretical price → arbitrage opportunity exists
```

## Cash-and-Carry Arbitrage

When futures are EXPENSIVE relative to theoretical fair value:

```
1. BUY the underlying asset at spot price
2. SELL the futures contract at inflated price
3. HOLD until expiry — deliver asset against futures contract
4. Profit = (Futures price - Spot price - Financing cost - Storage cost)

Example (Gold):
  Gold spot: $2,000/oz
  6-month futures: $2,080
  Theoretical: $2,000 * e^(0.05 * 0.5) = $2,050
  Arb profit: $2,080 - $2,050 = $30/oz (risk-free)

Costs to account for:
  - Financing cost (borrow rate * spot price * T)
  - Storage/insurance (for physical commodities)
  - Transaction costs (bid-ask spread)
```

## Reverse Cash-and-Carry

When futures are CHEAP relative to fair value:

```
1. SHORT the underlying (borrow and sell spot)
2. BUY the futures contract at discounted price
3. Receive delivery at expiry
4. Return borrowed asset, keep the spread
5. Profit = (Spot price - Futures price + Financing rebate)
```

## Crypto Futures Basis (Perpetual Funding Rate)

Crypto perpetual futures have no expiry; instead use funding rates:

```
Funding Rate = (Futures price - Spot price) / Spot price * (8-hour rate)

Cash-and-carry in crypto:
  - BUY spot BTC
  - SHORT BTC perpetual futures
  - Collect positive funding rate (paid every 8 hours by longs to shorts)
  - Profit: Annual yield = funding rate * 3 * 365

When funding rate > 0.05% per 8h (5% monthly):
  - High demand for longs, futures expensive
  - Short futures + long spot captures this yield
  - Risk: Funding rate can go negative (net cost)
```

## Index Futures Basis

S&P 500 futures basis trade:

```
Fair value = Index level * (1 + r - d) ^ T
  r = 1-month Treasury rate
  d = S&P 500 dividend yield

If SPX futures > fair value:
  Sell futures, buy basket of 500 stocks proportionally
  Risk: Tracking error in stock selection
  Better: Use SPY ETF against SPX futures (same exposure, less tracking error)
```

## Commodity Storage and Convenience Yield

For physical commodities, futures price includes:
- **Storage cost**: Physical commodity (oil, grain) costs money to store
- **Convenience yield**: Value of having physical commodity on hand (drives backwardation)

```
Futures price = Spot * e^(r + storage_cost - convenience_yield) * T

Contango: Futures > Spot (storage cost > convenience yield)
Backwardation: Futures < Spot (convenience yield > storage cost)
```

### Calendar Spread Basis
```
Buy near-month futures
Sell far-month futures
Net: Long the calendar spread = benefit from storage cost convergence

Roll yield in contango markets: Calendar spread is NEGATIVE
Roll yield in backwardation: Calendar spread is POSITIVE
```

## Execution Considerations

1. **Capital efficiency**: Futures are margined — can use 5-10x leverage on basis trade
2. **Mark-to-market risk**: Even a risk-free arb can have margin calls during volatile periods
3. **Delivery mechanics**: Know whether futures are cash-settled or physical delivery
4. **Corporate actions**: Dividends, splits affect index futures fair value calculation
5. **Rollover cost**: Must roll futures position before expiry — roll yield is part of return

## Risk Factors

| Risk | Description | Mitigation |
|------|-------------|-----------|
| Financing risk | Borrowing rate changes | Lock in fixed rate |
| Basis risk | Spread widens before convergence | Size conservatively |
| Delivery risk | Physical delivery complications | Use cash-settled instruments |
| Counterparty | Broker/exchange default | Use central clearing |
| Regulatory | Short-selling restrictions | Monitor regulatory changes |

## Monitoring Framework

```
Daily checks:
  - Current basis vs. theoretical fair value
  - Funding rate (crypto) vs. 30-day average
  - Carry cost vs. locked-in spread
  - Days to expiry and rollover timing
  - Mark-to-market P&L and margin utilization
```
