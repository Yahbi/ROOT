---
name: Order Flow Analysis
description: Read market intent through volume, delta, and cumulative order flow patterns
version: "1.0.0"
author: ROOT
tags: [trading, order-flow, volume-profile, delta, footprint]
platforms: [all]
---

# Order Flow Analysis

Decode institutional intent by analyzing how volume transacts at each price level, revealing supply/demand imbalances invisible on standard charts.

## Volume Profile

- **Point of Control (POC)**: Price with highest traded volume; acts as fair value magnet
- **Value Area (VA)**: 70% of volume; defines the trading range (VA High / VA Low)
- **High Volume Nodes (HVN)**: Acceptance zones where price consolidates; act as support/resistance
- **Low Volume Nodes (LVN)**: Rejection zones; price moves quickly through these levels
- **Developing vs Fixed**: Use developing profile intraday, fixed profiles for multi-day context
- **Naked POC**: Previous session POC that price hasn't revisited; strong magnet

## Delta Analysis

- **Delta** = `(volume traded at ask) - (volume traded at bid)` per bar
- **Positive delta**: Aggressive buyers dominating; bullish pressure
- **Negative delta**: Aggressive sellers dominating; bearish pressure
- **Delta divergence**: Price makes new high but delta is declining = exhaustion signal
- **Stacked imbalances**: 3+ consecutive price levels with bid/ask ratio > 3:1 = institutional aggression

## Cumulative Volume Delta (CVD)

- Running sum of delta over time; shows net aggression trend
- **CVD rising + price rising**: Confirmed uptrend (aggressive buyers in control)
- **CVD falling + price rising**: Divergence; rally driven by passive sellers lifting, not conviction
- **CVD flat + price moving**: Passive order absorption; look for breakout failure
- Reset CVD at session open for intraday; use multi-day CVD for swing context

## Footprint Chart Patterns

- **Finished auction**: Single prints at extremes (only buyers at high, only sellers at low)
- **Unfinished auction**: Activity on both sides at extreme = continuation likely
- **Absorption**: Large volume on one side with no price movement = strong passive orders
- **Initiative vs Responsive**: Initiative = trading away from value; responsive = trading back to value

## Practical Signals

### Buy Setup
1. Price tests prior VA Low or naked POC from above
2. Delta turns positive at test (aggressive buying)
3. Absorption pattern visible (large bid volume, price stops falling)
4. CVD divergence: making higher low while price makes lower low

### Sell Setup
1. Price tests prior VA High or naked POC from below
2. Delta turns negative at test (aggressive selling)
3. Stacked ask imbalances appear on footprint
4. CVD divergence: making lower high while price makes higher high

## Data Requirements

- Level 2 / depth-of-book data for real delta (not tick-approximated)
- Tick-level data minimum; millisecond timestamps preferred
- Futures preferred over equities (centralized order book, no fragmentation)
- Tools: Sierra Chart, Bookmap, Jigsaw, Quantower for visualization
