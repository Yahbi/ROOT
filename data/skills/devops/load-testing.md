---
name: Load Testing
description: k6, Locust, stress testing, performance baselines, and capacity planning
version: "1.0.0"
author: ROOT
tags: [devops, load-testing, performance, k6, stress-testing, capacity]
platforms: [all]
---

# Load Testing

Verify system performance under load and establish capacity limits before users find them.

## Testing Types

| Type | Purpose | Load Profile |
|------|---------|-------------|
| Smoke test | Verify system works at minimal load | 1-5 users, 1-2 minutes |
| Load test | Verify performance at expected load | Expected users, 10-30 minutes |
| Stress test | Find the breaking point | Ramp to 2-5x expected, until failure |
| Soak test | Find memory leaks and degradation | Expected load, 4-24 hours |
| Spike test | Test sudden traffic surges | Normal → 10x → normal in minutes |

## Tool Selection

### k6 (JavaScript-based)
- Best for: API testing, developer-friendly, CI/CD integration
- Write tests in JavaScript, run from CLI
- Built-in metrics: request duration, throughput, error rate
- Cloud execution available for distributed load generation

### Locust (Python-based)
- Best for: Python teams, complex user behavior, distributed testing
- Define user behavior as Python classes
- Web UI for real-time monitoring during tests
- Easy to model complex multi-step user journeys

### Artillery (YAML + JS)
- Best for: Quick setup, configuration-driven tests
- YAML-based test definitions with JS for custom logic

## Test Design

### Realistic Load Modeling
1. Analyze production traffic patterns (peak hours, daily/weekly cycles)
2. Identify key user journeys (signup → browse → purchase → checkout)
3. Model think time between actions (3-10 seconds typical)
4. Set user ramp-up rate: don't start at full load (unrealistic and masks issues)
5. Include API mix that matches production (70% reads, 20% writes, 10% search)

### Performance Budget
| Metric | Target | Unacceptable |
|--------|--------|-------------|
| API p50 latency | < 100ms | > 500ms |
| API p95 latency | < 300ms | > 1,000ms |
| API p99 latency | < 1,000ms | > 3,000ms |
| Error rate | < 0.1% | > 1% |
| Throughput | > 500 RPS | < 100 RPS |

## Interpreting Results

### Key Patterns
- **Latency increases linearly with load**: Normal — system is scaling within capacity
- **Latency spike at specific load**: Bottleneck found — investigate resource at that point
- **Error rate increases suddenly**: System is past capacity — this is the breaking point
- **Gradual degradation over time**: Memory leak or resource exhaustion (soak test finding)

### Bottleneck Investigation
1. Check database: slow queries, connection pool exhaustion, lock contention
2. Check application: CPU-bound processing, thread pool limits, GC pauses
3. Check infrastructure: network bandwidth, disk I/O, container resource limits
4. Check external dependencies: third-party API rate limits, timeout cascades

## CI/CD Integration

### Automated Performance Gates
1. Run smoke test on every PR (1 minute, fail if p95 > 500ms)
2. Run load test nightly on staging (10 minutes, fail if regression > 20%)
3. Run full stress test before major releases (30 minutes, establish new baseline)
4. Track performance trends: chart p95 latency over time for each endpoint

### Baseline Management
- Establish baseline after each release
- Alert if any endpoint regresses > 20% from baseline
- Review and update baselines quarterly
- Store historical results for trend analysis
