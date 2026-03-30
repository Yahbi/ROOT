---
name: Live Monitoring
description: Real-time position tracking, P&L monitoring, and alerting
version: "1.0.0"
author: ROOT
tags: [automation, monitoring, P&L, alerts, risk]
platforms: [all]
---

# Live Position and P&L Monitoring

Real-time monitoring system for active trading positions and portfolio health.

## Dashboard Metrics

### Position Level
- **Ticker, direction, size**: current holdings with entry price
- **Unrealized P&L**: (current_price - entry_price) * quantity (updated every tick)
- **% of portfolio**: position weight vs total equity
- **Time in trade**: days since entry — flag positions held >20 days
- **Distance to stop**: current price vs stop-loss level (% and $)

### Portfolio Level
- **Total equity**: cash + market value of all positions
- **Daily P&L**: today's realized + unrealized change
- **Drawdown from peak**: current equity vs all-time high watermark
- **Gross exposure**: sum of absolute position values / equity
- **Net exposure**: (long_value - short_value) / equity
- **Cash available**: buying power remaining

## Alert Thresholds

| Alert | Trigger | Action |
|-------|---------|--------|
| Position stop-loss | Price within 0.5% of stop | Push notification |
| Daily loss limit | Daily P&L < -2% of equity | Halt new trades |
| Max drawdown | Drawdown > 5% from peak | Reduce all positions 50% |
| Concentration | Single position > 10% of equity | Warning to rebalance |
| Margin call risk | Margin usage > 80% | Liquidate weakest position |
| Stale data | No price update for 60 seconds | Alert: data feed issue |

## Implementation Architecture

```
[Broker API] → [Price Poller (5s interval)] → [Position Calculator]
                                                       ↓
                                              [Alert Engine]
                                                       ↓
                                    [Telegram / Discord / Dashboard]
```

### Polling Schedule
- **Market hours**: poll positions every 5 seconds, P&L every 1 second
- **Pre/post market**: poll every 30 seconds
- **Market closed**: poll once per hour for overnight gaps (futures, crypto)

## Daily Reconciliation

1. At market close, fetch all positions from broker API
2. Compare to internal state — flag any discrepancies
3. Calculate realized P&L for closed trades
4. Update performance log with daily return
5. Archive trade history to database
6. Generate end-of-day summary notification

## Health Checks

- Verify broker API connectivity every 60 seconds
- Confirm data feed latency < 500ms
- Check that all stop-loss orders are active on the broker side
- Validate cash balance matches expected (no unauthorized transactions)
- Log all anomalies for review

## Integration with ROOT

- Position monitor runs as background loop every 5 minutes
- Triggers notification engine for HIGH/CRITICAL alerts
- Feeds P&L data to hedge fund performance tracker
- Stale position data triggers escalation to Yohan
