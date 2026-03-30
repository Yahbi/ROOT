---
name: Market Microstructure
description: Order flow analysis, bid-ask dynamics, and market making concepts
version: "1.0.0"
author: ROOT
tags: [research, microstructure, order-flow, market-making]
platforms: [all]
---

# Market Microstructure

Understand how orders become trades and extract alpha from order flow data.

## Core Concepts

### Order Book Anatomy
- **Bid**: highest price buyers will pay (demand side)
- **Ask**: lowest price sellers will accept (supply side)
- **Spread**: ask - bid (compensation for liquidity providers)
- **Depth**: total volume available at each price level
- **Imbalance**: bid_volume / (bid_volume + ask_volume) at top-of-book

### Order Types and Their Signals
| Order Type | Information Content |
|------------|-------------------|
| Market order | Urgency — informed traders use these |
| Limit order | Patience — provides liquidity, earns spread |
| Iceberg order | Large hidden size — institutional activity |
| Cancel/replace | Probing — testing depth, often algorithmic |

## Order Flow Indicators

### Volume-Weighted Analysis
- **VWAP**: benchmark for institutional execution quality
- **Delta**: buy_volume - sell_volume (positive = buying pressure)
- **Cumulative delta divergence**: price up + delta down = weak rally

### Bid-Ask Spread Signals
- Widening spread = uncertainty, volatility incoming
- Narrowing spread = consensus, trend likely to continue
- Sudden spread blowout = news event or liquidity withdrawal

### Tape Reading Patterns
1. **Absorption**: large resting order absorbs market orders without price moving
2. **Exhaustion**: decreasing volume at price extreme, reversal imminent
3. **Sweep**: aggressive orders clear multiple price levels — strong directional intent
4. **Spoofing**: large orders placed then cancelled — illegal but detectable

## Practical Application

1. **Monitor Level 2 data** before entry — check depth imbalance
2. **Track large prints** on time and sales — block trades signal institutional flow
3. **Compare lit vs dark volume** — high dark pool % = institutional accumulation
4. **Use footprint charts** — visualize buy/sell volume at each price level
5. **Watch for liquidity voids** — thin areas in order book where price accelerates

## For Automated Systems

- Collect tick-level data and aggregate into 1-second bars
- Calculate real-time order imbalance ratio every 100ms
- Flag unusual spread widening as pre-event warning
- Track aggressive order ratio (market orders / total) as urgency metric
