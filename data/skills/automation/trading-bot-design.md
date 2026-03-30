---
name: Trading Bot Design
description: Architecture patterns for building reliable automated trading systems
version: "1.0.0"
author: ROOT
tags: [automation, trading-bot, architecture, systems]
platforms: [all]
---

# Trading Bot Architecture

Design principles and architecture for automated trading systems.

## System Components

### 1. Data Layer
- **Market data feed**: WebSocket for real-time (Alpaca, Polygon), REST for historical
- **Order book feed**: Level 2 data for microstructure signals
- **Alternative data**: news API, sentiment feed, prediction markets
- **Storage**: time-series DB (TimescaleDB) for tick data, SQLite for state

### 2. Signal Engine
- Consume data streams and compute indicators in real-time
- Maintain rolling windows for technical indicators (SMA, RSI, MACD)
- Run signal models: output = (direction, confidence, magnitude)
- Each signal has a unique ID for tracking and attribution

### 3. Risk Manager (pre-trade)
- Position size calculator: Kelly criterion or fixed fractional
- Exposure limits: max per-position, per-sector, total portfolio
- Drawdown circuit breaker: halt trading if daily loss exceeds threshold
- Correlation check: reject signals that increase portfolio concentration

### 4. Execution Engine
- Convert signals to orders (market, limit, stop)
- Smart order routing: split large orders to minimize market impact
- Retry logic with exponential backoff for transient API failures
- Order state machine: pending → submitted → partial → filled / cancelled

### 5. Portfolio Tracker
- Real-time P&L calculation (realized + unrealized)
- Track performance attribution by strategy, signal, and asset
- Monitor margin usage and buying power
- Generate alerts on drawdown milestones (1%, 2%, 5%)

## Architecture Pattern

```
[Data Feeds] → [Signal Engine] → [Risk Manager] → [Execution Engine]
      ↓                                                    ↓
[Time-Series DB]                                   [Broker API]
      ↓                                                    ↓
[Backtester]                                    [Portfolio Tracker]
                                                           ↓
                                                   [Alert System]
```

## Key Design Principles

1. **Separation of concerns**: signals, risk, and execution are independent modules
2. **Idempotency**: re-running a signal must not create duplicate orders
3. **Fail-safe defaults**: if any component fails, halt trading (do not assume)
4. **Audit trail**: log every decision with timestamp, signal ID, and rationale
5. **Paper trade first**: run in simulation for 30+ days before live capital

## Deployment

- Run on always-on infrastructure (VPS, not local machine)
- Health check endpoint: monitor heartbeat every 60 seconds
- Automatic restart on crash with state recovery from persistent store
- Deploy updates during market close to avoid mid-session disruption
