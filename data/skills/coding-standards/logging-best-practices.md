---
name: Logging Best Practices
description: Structured logging, log levels, context propagation, PII redaction
version: "1.0.0"
author: ROOT
tags: [coding-standards, logging, structured-logging, observability, PII, context]
platforms: [all]
---

# Logging Best Practices

Write logs that are useful for debugging, auditing, and monitoring in production.

## Structured Logging

### Setup with structlog
```python
import structlog
import logging

def configure_logging(log_level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,    # Auto-inject context
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
    )

log = structlog.get_logger()

# Structured fields are first-class, not embedded in message strings
log.info("order_processed", order_id="12345", amount=99.99, duration_ms=142)
# Bad: log.info(f"Processed order 12345 for $99.99 in 142ms")
```

### Why Structured Over String Interpolation
- **Searchable**: Query `order_id = "12345"` across all logs
- **Aggregatable**: Calculate average `duration_ms` per endpoint
- **Alertable**: Trigger on `level = "error" AND service = "payment"`
- **Machine-parseable**: No regex needed to extract fields from log lines
- **Consistent**: Every entry has the same schema regardless of who wrote it

## Log Levels

### Level Guidelines
| Level | When | Example | Production? |
|-------|------|---------|-------------|
| DEBUG | Diagnostic detail for developers | SQL queries, cache hits, request payloads | No (staging only) |
| INFO | Normal business operations | User login, order created, task completed | Yes |
| WARNING | Unexpected but handled gracefully | Retry succeeded, fallback activated, deprecated API used | Yes |
| ERROR | Unhandled failure needing attention | DB connection lost, payment failed, LLM timeout | Yes |
| CRITICAL | System cannot continue | Disk full, all replicas down, data corruption | Yes |

### Common Mistakes
- Logging at ERROR for expected conditions (user not found = INFO, not ERROR)
- Logging at DEBUG in production (generates massive volume, slows system)
- Logging at INFO for every loop iteration (use DEBUG or aggregate)
- Not logging at all in error handlers (silent failures are the worst)

## Context Propagation

### Request-Scoped Context
```python
import structlog
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar("request_id", default="")
user_id: ContextVar[str] = ContextVar("user_id", default="")

# FastAPI middleware: bind context at request start
async def logging_middleware(request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=req_id,
        path=request.url.path,
        method=request.method,
    )
    response = await call_next(request)
    return response

# Every log call in this request automatically includes request_id, path, method
log.info("memory_stored", category="fact", confidence=0.85)
# Output: {"event":"memory_stored","category":"fact","confidence":0.85,
#          "request_id":"abc-123","path":"/api/chat","method":"POST",...}
```

### Cross-Service Propagation
- Pass `X-Request-ID` header to all downstream HTTP calls
- Include `correlation_id` in message queue payloads
- Log the correlation ID in every service that handles the request
- Result: trace a single user action across the entire system by searching one ID

## PII Redaction

### Automatic Redaction
```python
import re

PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
}

SENSITIVE_FIELDS = {"password", "token", "secret", "api_key", "authorization"}

def redact_processor(logger, method_name, event_dict):
    for key, value in list(event_dict.items()):
        if key.lower() in SENSITIVE_FIELDS:
            event_dict[key] = "***REDACTED***"
        elif isinstance(value, str):
            for pattern_name, pattern in PII_PATTERNS.items():
                if pattern.search(value):
                    event_dict[key] = f"***{pattern_name.upper()}_REDACTED***"
    return event_dict
```

### PII Rules
- Never log passwords, tokens, API keys, or session IDs in plaintext
- Log user identifiers (user_id) but not user data (email, name, address)
- Redact at the logging layer, not at every call site (centralized enforcement)
- Audit logs quarterly for PII leaks (search for email patterns in log archives)
- Compliance: GDPR requires ability to delete user data from logs (or redact at write time)

## Performance and Cost

### Log Volume Control
| Strategy | Impact | Implementation |
|----------|--------|---------------|
| Log level gating | 10-100x reduction | DEBUG off in production |
| Sampling | 10-90% reduction | Log 10% of successful requests, 100% of errors |
| Rate limiting | Prevents log storms | Max 100 identical logs per minute |
| Aggregation | 10-50x reduction | Count events instead of logging each one |

### Async Logging
```python
# Use QueueHandler to avoid blocking the event loop
import logging
from logging.handlers import QueueHandler, QueueListener
from queue import Queue

log_queue = Queue()
handler = QueueHandler(log_queue)
listener = QueueListener(log_queue, logging.StreamHandler())
listener.start()  # Processes logs in a background thread
```

### Cost Estimation
- Estimate log volume: requests/day x lines/request x bytes/line
- Example: 1M requests/day x 5 log lines x 500 bytes = 2.5 GB/day
- Retention at 30 days: 75 GB
- Apply compression (typically 10x): ~7.5 GB stored
