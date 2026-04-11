---
name: On-Chain Analysis
description: Wallet tracking, flow analysis, and whale watching for crypto trading signals
version: "1.0.0"
author: ROOT
tags: [crypto, on-chain, wallet-tracking, whale-watching, flow-analysis]
platforms: [all]
---

# On-Chain Analysis

Extract trading signals from blockchain data by tracking wallet behavior, fund flows, and network activity.

## Wallet Tracking

### Smart Money Identification
1. Identify wallets with consistent profitable trading history
2. Track known entity wallets: exchanges, funds, project treasuries, MEV bots
3. Monitor wallets that accumulated before major price moves (historical signal)
4. Tools: Arkham Intelligence, Nansen, Etherscan labels, DeBank

### Key Wallet Signals
| Signal | Interpretation | Action |
|--------|---------------|--------|
| Whale accumulation | Large wallets buying quietly | Bullish — follow with smaller size |
| Exchange inflow spike | Tokens moving to exchanges | Bearish — likely selling pressure |
| Exchange outflow | Tokens leaving exchanges | Bullish — moving to cold storage |
| Treasury diversification | Project selling own token | Bearish — insiders reducing exposure |

## Flow Analysis

### Exchange Flow Metrics
- **Net flow** = inflow - outflow (negative = bullish, positive = bearish)
- **Exchange reserve**: total tokens held on exchanges — declining is bullish
- **Deposit count spike**: many small deposits = retail selling; few large = whale selling
- Track across top 5 exchanges (Binance, Coinbase, OKX, Bybit, Kraken)

### Stablecoin Flows
- Stablecoins flowing to exchanges = "dry powder" ready to buy (bullish)
- Stablecoins flowing out of exchanges = capital exiting crypto (bearish)
- USDT minting events historically precede price rallies

## Network Activity Metrics

### Fundamental Health
- **Active addresses**: Daily unique senders + receivers (adoption proxy)
- **Transaction count**: Network usage independent of price
- **Fee revenue**: Real economic activity on the network
- **NVT ratio**: Market cap / daily transaction volume (high = overvalued)

### Developer Activity
- GitHub commits, unique contributors, PRs merged per week
- Declining dev activity + high valuation = red flag
- New repo creation signals expansion into new areas

## On-Chain Analysis Workflow

1. **Screen**: Filter for tokens with anomalous on-chain activity (volume spike, whale moves)
2. **Investigate**: Drill into specific wallets and transactions driving the anomaly
3. **Contextualize**: Cross-reference with news, social media, and price action
4. **Score**: Rate conviction 1-5 based on signal strength and historical reliability
5. **Act**: Only trade on signals rated 4+ with confirming price action

## Pitfalls

- On-chain data has latency — by the time you see it, fast actors already moved
- Wash trading inflates volume metrics on some chains
- Wallet labeling is imperfect — misidentified wallets lead to false signals
- Internal exchange transfers can look like meaningful flows
- Always combine on-chain signals with price action and fundamentals
