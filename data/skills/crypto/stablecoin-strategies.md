---
name: Stablecoin Strategies
description: Yield generation on stablecoins and delta-neutral strategies
version: "1.0.0"
author: ROOT
tags: [crypto, stablecoins, yield, delta-neutral, lending]
platforms: [all]
---

# Stablecoin Yield Strategies

Generate yield on stablecoins with managed risk, including delta-neutral approaches.

## Direct Lending Yield

### Protocol Comparison
| Protocol | Typical APY | Risk Level | Mechanism |
|----------|------------|------------|-----------|
| Aave v3 | 3-8% | Low-Medium | Overcollateralized lending |
| Compound v3 | 3-7% | Low-Medium | Overcollateralized lending |
| MakerDAO DSR | 5-8% | Low | Protocol-set savings rate |
| Morpho | 4-10% | Medium | Peer-to-peer lending optimization |

### Best Practices
- Diversify across 2-3 lending protocols to reduce smart contract risk
- Monitor utilization rates — high utilization (>90%) means withdrawal delays
- Prefer USDC over USDT for transparency of reserves
- Check that lending rates exceed gas costs for deposits/withdrawals

## Liquidity Provision Strategies

### Stable-Stable Pairs
- USDC/USDT pools on Curve or Uniswap v3 (tight range)
- Minimal impermanent loss since both assets target $1
- Typical yield: 2-10% from fees + emissions
- Risk: one stablecoin depegs — position becomes 100% the depegged coin

### Concentrated Liquidity
- On Uniswap v3: set range 0.998-1.002 for stable pairs
- Capital efficiency 100-500x vs full range
- Must rebalance if price exits range (automated managers: Arrakis, Gamma)

## Delta-Neutral Strategies

### Basis Trade (Cash and Carry)
1. Buy spot ETH/BTC
2. Short equivalent perpetual futures
3. Collect funding rate (typically positive in bull markets: 10-30% APY)
4. Net market exposure: zero (delta-neutral)
5. Risk: negative funding, exchange failure, liquidation on short leg

### Yield Arbitrage
1. Borrow stablecoin at low rate (Aave: 3-5%)
2. Deploy to higher-yield protocol (new protocol incentives: 10-20%)
3. Net yield = high rate - borrow rate - gas costs
4. Risk: smart contract exploit on either protocol, rate compression

## Risk Management

### Position Limits
- Max 30% of stablecoin portfolio in any single protocol
- Max 50% in any single stablecoin denomination
- Keep 20% in cold storage as reserve (not deployed for yield)

### Monitoring
- Check protocol health (TVL, utilization, governance) weekly
- Monitor stablecoin peg — exit if deviation > 0.5% persists for 4+ hours
- Track real vs advertised APY — if actual < 50% of advertised, likely unsustainable
- Set alerts for governance proposals that change risk parameters

## Red Flags

- APY > 20% on stablecoins without clear source of real yield
- Algorithmic stablecoins without full exogenous collateral
- Protocols with < $10M TVL (low liquidity, higher rug risk)
- Yields that increase as TVL declines (death spiral signal)
