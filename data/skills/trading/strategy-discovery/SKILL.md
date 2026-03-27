---
name: strategy-discovery
description: Discover, evaluate, and backtest trading strategies autonomously
version: 1.0.0
author: ROOT
tags: [trading, strategies, backtesting, finance]
platforms: [darwin, linux, win32]
---

# Autonomous Trading Strategy Discovery

From the Trading Swarm (3-agent architecture).

## When to Use
- Yohan asks about market opportunities
- Periodic strategy refresh cycle
- After significant market events

## Three-Agent Pipeline

### 1. Research Agent
- Sources: TradingView, Polymarket, Binance, crypto news
- Discovers up to 5 new strategies per cycle
- Tags with: asset class, timeframe, risk level

### 2. Analysis Agent
- Evaluates feasibility and logic
- Assesses risk/reward ratio
- Assigns confidence scores (0-100)
- Filters out strategies below threshold

### 3. Backtest Agent
- Tests on historical data (configurable period)
- Calculates: ROI, Sharpe ratio, max drawdown
- Stores top performers in strategy_intelligence.db

## Cycle Timing
- Default: every 5 minutes (288 cycles/day max)
- Adjustable based on market conditions

## Integration with ROOT
- Delegate to Trading Swarm connector
- Read results from strategy_intelligence.db
- Store winning strategies in memory
- Alert Yohan when high-confidence strategy found
