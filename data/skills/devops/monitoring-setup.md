---
name: Monitoring Setup
description: Prometheus, Grafana, OpenTelemetry, alerting, and observability practices
version: "1.0.0"
author: ROOT
tags: [devops, monitoring, prometheus, grafana, observability, alerting]
platforms: [all]
---

# Monitoring and Observability

Set up comprehensive monitoring to detect issues before users do.

## Three Pillars of Observability

### Metrics (Prometheus)
- Numeric time-series data: counters, gauges, histograms
- Best for: dashboards, alerts, capacity planning, SLO tracking
- Cardinality warning: avoid high-cardinality labels (user IDs, request IDs)

### Logs (Structured)
- Event-level detail with context (timestamp, level, message, metadata)
- Use structured JSON logging: `{"level": "error", "msg": "...", "request_id": "..."}`
- Centralize with ELK stack, Loki, or CloudWatch Logs
- Always include correlation ID for request tracing

### Traces (OpenTelemetry)
- Distributed trace across services: follow a request through the entire system
- Each span: operation name, duration, status, attributes
- Essential for microservices — identifies which service is the bottleneck
- Use OpenTelemetry SDK for vendor-neutral instrumentation

## Key Metrics to Monitor

### Application Metrics (RED Method)
| Metric | What to Track | Alert Threshold |
|--------|--------------|-----------------|
| **R**ate | Requests per second | > 2x baseline or < 0.5x baseline |
| **E**rrors | Error rate (5xx / total) | > 1% for 5 minutes |
| **D**uration | Latency p50, p95, p99 | p95 > 2x baseline for 5 minutes |

### Infrastructure Metrics (USE Method)
| Resource | Utilization | Saturation | Errors |
|----------|------------|------------|--------|
| CPU | % used | Run queue length | System errors |
| Memory | % used | Swap usage | OOM kills |
| Disk | % used | IO wait | Read/write errors |
| Network | Bandwidth % | Dropped packets | Connection errors |

## Alerting Strategy

### Alert Severity Levels
- **Critical (page)**: Service down, data loss risk, security breach — immediate response
- **Warning (notify)**: Degraded performance, approaching limits — respond within 1 hour
- **Info (log)**: Anomalies, capacity trends — review next business day

### Alert Design Rules
1. Alert on symptoms (error rate up), not causes (CPU high)
2. Include runbook link in every alert
3. Set appropriate thresholds: avoid alert fatigue (max 2-3 pages per week)
4. Use escalation: if not acknowledged in 15 min, escalate
5. Review and prune alerts monthly — delete alerts nobody acts on

## Dashboard Design

### Service Dashboard (one per service)
- Top row: request rate, error rate, latency (the RED metrics)
- Middle: resource usage (CPU, memory, connections)
- Bottom: business metrics (signups, transactions, revenue)
- Time range selector: last 1h, 6h, 24h, 7d

### On-Call Dashboard
- All critical alerts in one view
- Service health status (green/yellow/red per service)
- Recent deployments (correlate with incidents)
- Error log stream (last 100 errors)

## Implementation Checklist

1. Instrument application with OpenTelemetry SDK
2. Deploy Prometheus for metrics collection (15s scrape interval)
3. Deploy Grafana for dashboards (connect to Prometheus data source)
4. Configure alerting rules in Prometheus Alertmanager
5. Set up log aggregation with structured logging
6. Create runbooks for every alert
7. Test alerting: intentionally trigger each alert to verify delivery
