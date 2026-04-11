---
name: Log Aggregation
description: Structured logging, correlation IDs, ELK vs Loki, retention policies
version: "1.0.0"
author: ROOT
tags: [infrastructure, logging, ELK, Loki, structured-logging, observability]
platforms: [all]
---

# Log Aggregation

Collect, structure, and query logs effectively for debugging, auditing, and alerting.

## Structured Logging

### JSON Log Format
```python
import structlog
import logging

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()
log.info("order_processed", order_id="12345", amount=99.99, duration_ms=142)
# Output: {"event":"order_processed","order_id":"12345","amount":99.99,"duration_ms":142,"level":"info","timestamp":"2025-01-15T10:30:00Z"}
```

### Why Structured Over Unstructured
- Parseable by machines: query `amount > 100` across millions of log lines
- Consistent schema: every log entry has the same fields (level, timestamp, event)
- Filterable: search by order_id, user_id, service_name without regex
- Aggregatable: count events by type, calculate P99 latency from duration_ms

## Correlation IDs

### Implementation
```python
import uuid
from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')

# Middleware: extract or generate correlation ID
async def correlation_middleware(request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    correlation_id.set(req_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

# Structlog processor: automatically inject correlation ID
def add_correlation_id(logger, method_name, event_dict):
    event_dict["correlation_id"] = correlation_id.get("")
    return event_dict
```

### Propagation Rules
- Pass `X-Request-ID` header to all downstream HTTP calls
- Include `correlation_id` field in all message queue messages
- Log the correlation ID in every structured log entry
- Result: trace a single user request across 10+ services by searching one ID

## Log Aggregation Stacks

### ELK vs Loki vs CloudWatch
| Feature | ELK (Elasticsearch) | Grafana Loki | CloudWatch Logs |
|---------|---------------------|-------------|-----------------|
| Full-text search | Excellent (inverted index) | Label-based only | Good |
| Storage cost | High (indexes everything) | Low (stores compressed chunks) | Medium |
| Query language | KQL / Lucene | LogQL (PromQL-like) | CloudWatch Insights |
| Operational burden | High (JVM tuning, shards) | Low (object storage backend) | Zero (managed) |
| Best for | Complex search across fields | High-volume with label filtering | AWS-native stacks |

### Loki Setup (Recommended for Cost-Sensitive Deployments)
```yaml
# Promtail config: scrape container logs, add labels
scrape_configs:
  - job_name: containers
    static_configs:
      - targets: [localhost]
        labels:
          job: app
          __path__: /var/log/app/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            service: service
      - labels:
          level:
          service:
```

### LogQL Query Examples
```
# All errors from order-service in the last hour
{service="order-service", level="error"} |= "timeout"

# Count errors per service over 5-minute windows
sum(rate({level="error"}[5m])) by (service)

# Extract and filter on JSON fields
{job="app"} | json | amount > 1000 | duration_ms > 500
```

## Retention Policies

### Tiered Retention
| Log Type | Retention | Rationale |
|----------|-----------|-----------|
| Application errors | 90 days | Debugging recent issues |
| Access logs | 30 days | Traffic analysis, abuse detection |
| Audit logs | 1-7 years | Compliance (SOC2, GDPR, HIPAA) |
| Debug/trace logs | 7 days | High volume, short-term debugging only |
| Security events | 1 year | Incident investigation |

### Cost Control
- Index only fields you query on (not the entire log body in ELK)
- Use log levels correctly: DEBUG in dev, INFO in prod (do not log DEBUG in production)
- Sample high-volume logs: log 10% of successful requests, 100% of errors
- Compress and archive to object storage (S3/GCS) for long-term compliance retention
- Set index lifecycle policies: hot (7d, SSD) -> warm (30d, HDD) -> cold (90d, S3) -> delete

## Log Level Guidelines

| Level | When to Use | Example |
|-------|------------|---------|
| ERROR | Something failed that needs attention | Database connection lost, payment failed |
| WARNING | Unexpected but handled gracefully | Retry succeeded, fallback activated, rate limited |
| INFO | Normal business events | Order created, user logged in, task completed |
| DEBUG | Diagnostic detail (dev/staging only) | SQL query text, request payload, cache hit/miss |
