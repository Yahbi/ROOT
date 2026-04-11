---
name: Crypto Market Making
description: AMM mechanics, concentrated liquidity provision, and impermanent loss quantification
version: "1.0.0"
author: ROOT
tags: [trading, crypto, market-making, AMM, DeFi, liquidity]
platforms: [all]
---

# Crypto Market Making

Provide liquidity in decentralized and centralized crypto venues, understanding AMM mathematics, impermanent loss, and yield optimization.

## Automated Market Maker (AMM) Mechanics

- **Constant product**: `x * y = k` (Uniswap V2); price = `y/x`; any trade changes both reserves
- **Price impact**: `slippage = trade_size / (reserve + trade_size)`; larger trades suffer more
- **Fee accrual**: Typically 0.3% per swap; fees added to reserves, compounding LP positions
- **Arbitrage**: External price changes create arbitrage; arbitrageurs realign AMM price to market
- **LP return**: `fees_earned - impermanent_loss - opportunity_cost`; positive only if fees dominate

## Concentrated Liquidity (Uniswap V3 / V4)

- **Range orders**: Provide liquidity only within price range [P_lower, P_upper]
- **Capital efficiency**: Concentrated range = `sqrt(P_upper/P_lower)` times more capital efficient than full range
- **Example**: ETH/USDC LP in $2000-$2500 range is 5x more efficient than full range
- **Liquidity formula**: `L = Delta_x * sqrt(P_upper * P_current) / (sqrt(P_upper) - sqrt(P_current))`
- **Out-of-range**: If price exits your range, you hold 100% of the depreciating asset; no fees earned
- **Rebalancing**: Must actively manage ranges; optimal rebalance frequency depends on gas costs vs IL

## Impermanent Loss Mathematics

- **IL formula**: `IL = 2 * sqrt(price_ratio) / (1 + price_ratio) - 1` where `price_ratio = P_new / P_initial`
- **IL by price change**:
  - 1.25x price change = -0.6% IL
  - 1.5x = -2.0%, 2x = -5.7%, 3x = -13.4%, 5x = -25.5%
- **Concentrated IL**: IL amplified by capital efficiency multiplier; 5x concentration = 5x IL
- **Breakeven**: Required fee APR to offset IL = `IL_annual / LP_value`; often needs >50% APR for volatile pairs
- **IL is permanent when**: You withdraw at a different price than entry; "impermanent" only if price returns

## CEX Market Making for Crypto

- **Spread capture**: Place bids and asks around mid; wider spreads for illiquid altcoins (0.3-2%)
- **Inventory management**: Crypto markets 24/7; no EOD flatten — use hard inventory limits per asset
- **Funding rate arb**: Long spot + short perp when funding > 0; collect funding every 8 hours
- **Cross-exchange**: Quote on illiquid exchange, hedge on Binance/Coinbase; latency advantage critical
- **Wash trading risk**: Avoid venues with fake volume; check real volume via Kaiko, CoinGecko adjusted

## Yield Optimization Strategies

- **LP stacking**: Provide LP tokens as collateral for lending; compound yield layers
- **Incentive farming**: Chase protocol token emissions; APR = `(token_emissions * price) / TVL`; decays quickly
- **Range management**: Tighten range during low-vol (more fees); widen during high-vol (less IL risk)
- **Hedging IL**: Buy put options on the LP pair or use perpetual futures to delta-hedge
- **Stablecoin pairs**: USDC/USDT pools have near-zero IL; lower yield but safe base layer (3-8% APR)

## Risk Management

- **Smart contract risk**: Only LP on audited protocols; limit exposure per protocol to 10% of capital
- **Rug pull protection**: Check TVL trajectory, team doxxing, audit reports before providing liquidity
- **Gas cost accounting**: On Ethereum mainnet, each rebalance costs $5-50; factor into breakeven analysis
- **Oracle risk**: AMMs relying on external oracles can be manipulated; prefer TWAP-based pricing
- **Max allocation**: No more than 20% of portfolio in any single LP position; diversify across chains
- **Emergency withdrawal**: Monitor pool health; withdraw if TVL drops > 30% in 24 hours (bank run signal)
