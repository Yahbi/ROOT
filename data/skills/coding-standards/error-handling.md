---
name: Error Handling
description: Exception hierarchy, retry strategies, circuit breakers, graceful degradation
version: "1.0.0"
author: ROOT
tags: [coding-standards, error-handling, exceptions, retry, circuit-breaker, resilience]
platforms: [all]
---

# Error Handling

Build resilient systems that fail gracefully and recover automatically from transient errors.

## Exception Hierarchy

### Designing Custom Exceptions
```python
class AppError(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, code: str, retry: bool = False):
        self.message = message
        self.code = code
        self.retry = retry  # Should the caller retry?
        super().__init__(message)

class TransientError(AppError):
    """Temporary failure, safe to retry."""
    def __init__(self, message: str, code: str = "TRANSIENT"):
        super().__init__(message, code, retry=True)

class PermanentError(AppError):
    """Permanent failure, do not retry."""
    def __init__(self, message: str, code: str = "PERMANENT"):
        super().__init__(message, code, retry=False)

# Specific errors inherit from the right category
class LLMUnavailableError(TransientError):
    def __init__(self, provider: str):
        super().__init__(f"LLM provider {provider} is temporarily unavailable")

class InvalidInputError(PermanentError):
    def __init__(self, field: str, reason: str):
        super().__init__(f"Invalid input for {field}: {reason}", code="INVALID_INPUT")
```

### Exception Rules
- Never catch bare `except:` or `except Exception:` without logging
- Catch specific exceptions at the appropriate level (not too high, not too low)
- Re-raise with context: `raise AppError("Failed to process") from original_exception`
- Use exception groups (Python 3.11+) for multiple simultaneous errors

## Retry Strategies

### Exponential Backoff with Jitter
```python
import asyncio
import random

async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable: tuple[type[Exception], ...] = (TransientError,)
):
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await func()
        except retryable as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
    raise last_exception
```

### Retry Decision Matrix
| Scenario | Retry? | Backoff | Max Retries |
|----------|--------|---------|-------------|
| HTTP 429 (rate limited) | Yes | Use Retry-After header | 3 |
| HTTP 500/502/503 | Yes | Exponential + jitter | 3 |
| HTTP 400 (bad request) | No | N/A | 0 |
| Connection timeout | Yes | Exponential | 3 |
| DNS resolution failure | Yes | Fixed 5s delay | 2 |
| Database deadlock | Yes | Random 0-1s | 3 |
| Disk full | No | N/A | 0 |

### Idempotency Requirement
- Only retry operations that are idempotent (safe to execute twice)
- GET, DELETE (by ID), PUT (full replace): naturally idempotent
- POST (create): use idempotency key to prevent duplicates
- Non-idempotent + transient failure = log error, alert, do not retry

## Circuit Breaker Pattern

### Integration with Retry
```
Request → Circuit Breaker Check → If OPEN: fail fast (no retry)
                                → If CLOSED/HALF_OPEN: attempt call
                                    → Success: reset failures
                                    → Failure: increment failures
                                        → If threshold reached: OPEN circuit
```

### Per-Dependency Circuits
- Separate circuit breaker per external dependency (LLM API, database, payment gateway)
- A broken payment gateway should not prevent user login
- Monitor circuit state in dashboards: open circuit = downstream outage

## Graceful Degradation

### Degradation Levels
| Level | Behavior | Example |
|-------|----------|---------|
| Full service | All features working normally | Normal operation |
| Reduced features | Non-critical features disabled | LLM down: use offline brain |
| Cached results | Serve stale data | API down: return last known good response |
| Static fallback | Minimal functionality | Database down: serve static health page |
| Maintenance mode | Informative error page | Full outage: "We'll be back soon" |

### Fallback Chain Pattern
```python
async def get_response(query: str) -> str:
    """Try primary, fallback to secondary, then offline."""
    try:
        return await call_primary_llm(query)        # Tier 1: Anthropic
    except LLMUnavailableError:
        try:
            return await call_secondary_llm(query)   # Tier 2: OpenAI
        except LLMUnavailableError:
            return await offline_brain(query)         # Tier 3: Local knowledge
```

### Timeout Budgets
- Total request timeout: 30 seconds
- Allocate per-step: LLM call 20s, DB query 5s, processing 5s
- If first step uses 25s, remaining steps have only 5s (cascade compression)
- Implement with `asyncio.timeout()` per step, not just at the top level

## Error Reporting

### Structured Error Responses
```python
from fastapi import HTTPException

class ErrorResponse(BaseModel):
    error: str          # Machine-readable code: "RATE_LIMITED"
    message: str        # Human-readable description
    details: dict = {}  # Additional context (field errors, limits)
    request_id: str     # For support/debugging correlation

# Never expose stack traces or internal details in production responses
# Log the full error internally, return sanitized version to client
```

### Logging Errors Effectively
- Log the full exception with traceback at ERROR level
- Include context: request_id, user_id, input parameters (redact PII)
- Differentiate expected errors (INFO) from unexpected errors (ERROR)
- Alert on unexpected error rate increase, not on individual errors
