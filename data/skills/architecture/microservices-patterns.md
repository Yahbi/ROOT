---
name: Microservices Patterns
description: Service mesh, circuit breaker, bulkhead, retry with backoff, sidecar
version: "1.0.0"
author: ROOT
tags: [architecture, microservices, circuit-breaker, service-mesh, resilience, bulkhead]
platforms: [all]
---

# Microservices Patterns

Implement resilience, observability, and communication patterns for distributed microservice architectures.

## Circuit Breaker

### State Machine
```
CLOSED (normal) → failures exceed threshold → OPEN (reject all calls)
  ↑                                               ↓ (after timeout)
  └──── success ←── HALF-OPEN (allow 1 probe call)
```

### Implementation
```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0

    async def call(self, func, *args):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("Circuit is open, call rejected")
        try:
            result = await func(*args)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failures = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.threshold:
            self.state = CircuitState.OPEN
```

### Configuration Guidelines
- `failure_threshold`: 5-10 failures before opening (tune per service reliability)
- `recovery_timeout`: 30-60 seconds before probing (enough for transient issues to clear)
- Monitor circuit state: alert when circuits open (indicates downstream problem)
- Separate circuits per downstream service (a failing payment service should not block user service)

## Bulkhead Pattern

### Thread Pool Isolation
```
Service A has separate pools for each downstream dependency:
  ├── Payment Service Pool (max 10 threads)
  ├── Inventory Service Pool (max 20 threads)
  └── Email Service Pool (max 5 threads)

If Payment Service hangs, only its 10 threads are consumed.
Inventory and Email continue functioning normally.
```

### Semaphore-Based Bulkhead
```python
import asyncio

class Bulkhead:
    def __init__(self, name: str, max_concurrent: int):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, func, *args, timeout=10):
        try:
            async with asyncio.timeout(timeout):
                async with self.semaphore:
                    return await func(*args)
        except TimeoutError:
            raise BulkheadTimeoutError(f"{self.name} bulkhead timeout")

payment_bulkhead = Bulkhead("payment", max_concurrent=10)
result = await payment_bulkhead.execute(call_payment_api, order_id)
```

## Retry with Backoff

### Exponential Backoff with Jitter
```python
import random

async def retry_with_backoff(func, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            return await func()
        except TransientError:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
            jitter = random.uniform(0, delay * 0.5)  # Prevent thundering herd
            await asyncio.sleep(delay + jitter)
```

### Retry Decision Matrix
| Error Type | Retry? | Example |
|-----------|--------|---------|
| 429 Too Many Requests | Yes (with Retry-After) | Rate limited |
| 500 Internal Server Error | Yes (transient) | Server overloaded |
| 502/503/504 | Yes (infrastructure) | Deployment, scaling |
| 400 Bad Request | No (client error) | Invalid payload |
| 401/403 | No (auth issue) | Fix credentials |
| Connection timeout | Yes (network) | Transient network issue |

## Service Mesh

### What a Service Mesh Provides
- **mTLS**: Automatic encryption between all services (no application code changes)
- **Traffic management**: Canary deployments, traffic splitting, retries, timeouts
- **Observability**: Distributed tracing, metrics, access logs for every service call
- **Policy**: Rate limiting, authorization policies, circuit breaking

### Sidecar Architecture
```
Pod/Container
  ├── Application Container (your code, no networking logic)
  └── Sidecar Proxy (Envoy) — handles all inbound/outbound traffic
        ├── mTLS termination
        ├── Retry logic
        ├── Circuit breaking
        ├── Metrics collection
        └── Access logging
```

### Mesh Selection
| Mesh | Complexity | Best For |
|------|-----------|----------|
| Istio | High | Large deployments, full feature set |
| Linkerd | Low | Simplicity, low resource overhead |
| Consul Connect | Medium | HashiCorp ecosystem, multi-platform |

## Service Communication Patterns

### Synchronous vs Asynchronous
| Pattern | When to Use | Trade-off |
|---------|------------|-----------|
| REST/gRPC (sync) | Need immediate response | Tight coupling, cascading failures |
| Message queue (async) | Fire-and-forget, batch processing | Eventual consistency, harder debugging |
| Event streaming | Multiple consumers, event replay | Infrastructure complexity |
| Request-reply over queue | Async with response needed | Moderate complexity |

### API Gateway
- Single entry point for all external traffic
- Cross-cutting concerns: auth, rate limiting, request logging
- Request routing: path-based routing to backend services
- Response aggregation: combine data from multiple services for frontend
