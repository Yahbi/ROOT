---
name: Workflow Orchestration
description: DAG design, retry policies, idempotency patterns, and dead letter queue management
version: "1.0.0"
author: ROOT
tags: [automation, workflow, orchestration, DAG, reliability, queues]
platforms: [all]
---

# Workflow Orchestration

Design and operate reliable multi-step automated workflows with proper error handling, retry logic, and failure isolation.

## DAG (Directed Acyclic Graph) Design

### Structure Principles
- **Single responsibility**: Each task node does one thing; combine in the DAG, not in the task
- **Explicit dependencies**: Define edges between tasks; never rely on implicit ordering or timing
- **Narrow fan-out**: Max 5-7 parallel branches; wider fan-out creates resource contention and debugging difficulty
- **Checkpoint nodes**: Insert explicit state-saving nodes between expensive operations; enables restart from checkpoint
- **Idempotent by default**: Every task must produce the same result when run multiple times with same input

### Common DAG Patterns
- **Linear pipeline**: A → B → C → D; simplest; each step depends on previous
- **Fan-out/fan-in**: A → [B1, B2, B3] → C; parallel execution with aggregation
- **Conditional branching**: A → (if condition) B else C → D; dynamic routing based on data
- **Sub-DAG**: Reusable workflow nested within larger DAG; treat as single node externally
- **Sensor pattern**: Wait-node that polls until condition is met (file exists, API returns data, time reached)

### DAG Anti-Patterns
- **Mega-task**: Single task doing 10 things; impossible to debug, retry, or parallelize
- **Circular dependency**: A → B → A; not a valid DAG; redesign to break cycle
- **Implicit coupling**: Task B reads from file that Task A writes without explicit dependency edge
- **Calendar-only scheduling**: Running tasks at fixed times without checking data readiness

## Retry Policies

### Retry Strategy Design
- **Exponential backoff**: `wait = base * 2^attempt` (e.g., 1s, 2s, 4s, 8s); add jitter (+/- 25%) to prevent thundering herd
- **Linear backoff**: `wait = base * attempt`; appropriate for rate-limited APIs with predictable recovery
- **Max retries**: 3 for transient errors (network, timeout); 0 for deterministic errors (validation, permission)
- **Max elapsed time**: Cap total retry duration (e.g., 5 minutes); prevent indefinite retrying

### Error Classification
| Error Type | Retryable | Action |
|-----------|-----------|--------|
| Network timeout | Yes | Retry with backoff |
| HTTP 429 (rate limit) | Yes | Retry after Retry-After header |
| HTTP 500 (server error) | Yes | Retry with exponential backoff |
| HTTP 400 (bad request) | No | Fix input, send to DLQ |
| HTTP 401/403 (auth) | No | Alert, refresh credentials |
| Data validation failure | No | Send to DLQ for manual review |
| Out of memory | Maybe | Retry with larger instance or chunk data |

### Circuit Breaker
- **Purpose**: Stop retrying when downstream service is persistently failing; prevent cascade
- **States**: Closed (normal) → Open (failures > threshold) → Half-Open (probe after cooldown)
- **Threshold**: Open after 5 consecutive failures or >50% failure rate in 1-minute window
- **Cooldown**: Wait 30-60 seconds before half-open probe; single test request to check recovery
- **Fallback**: When circuit is open, execute fallback logic (cache, default value, skip)

## Idempotency Patterns

- **Idempotency key**: Generate deterministic key from input parameters; check before execution
- **Database upsert**: Use `INSERT ... ON CONFLICT UPDATE` instead of blind insert; prevents duplicates
- **File operations**: Write to temp file, then atomic rename; prevents partial writes on retry
- **API calls**: Include idempotency key in request header (Stripe pattern); server deduplicates
- **State machine**: Track task state (pending → running → success/failed); only execute if state = pending
- **Exactly-once semantics**: Hard in distributed systems; approximate with at-least-once + idempotent handlers

## Dead Letter Queue (DLQ) Management

### DLQ Design
- **Purpose**: Capture messages/tasks that fail after all retries; prevent data loss; enable investigation
- **Separate DLQ per task type**: Enables targeted reprocessing; different error patterns per task
- **Metadata**: Store original message, error details, timestamp, retry count, task context
- **TTL**: Retain DLQ messages for 30 days; auto-archive to cold storage after

### DLQ Operations
- **Monitoring**: Alert when DLQ depth > threshold (e.g., > 100 messages); indicates systemic issue
- **Replay**: After fixing root cause, replay DLQ messages through original pipeline; verify idempotency first
- **Manual review**: Dashboard for browsing DLQ; filter by error type, date, task; one-click replay
- **Metrics**: Track DLQ arrival rate, average age, replay success rate; SLA: process within 24 hours

## Orchestration Tools

| Tool | Type | Best For |
|------|------|----------|
| Apache Airflow | DAG scheduler | Complex data pipelines, many integrations |
| Prefect | DAG scheduler | Modern Python-native, dynamic workflows |
| Temporal | Workflow engine | Long-running workflows, durable execution |
| Celery | Task queue | Simple async tasks, real-time processing |
| AWS Step Functions | Serverless DAG | Cloud-native, event-driven, low maintenance |

## Observability

- **Structured logging**: JSON logs with task_id, dag_id, attempt, duration, status; queryable in ELK/Loki
- **Metrics**: Task duration (p50, p95, p99), success rate, retry rate, DLQ depth, DAG completion time
- **Tracing**: Distributed trace ID through entire DAG execution; correlate logs across tasks
- **Alerting**: SLA breach (DAG not complete by deadline), high retry rate (>20%), DLQ growth rate increase
- **Dashboard**: Real-time DAG execution view; task status, duration, dependencies; Gantt chart visualization

## Risk Management

- **Single point of failure**: Orchestrator itself must be highly available; use managed service or HA deployment
- **Resource exhaustion**: Limit concurrent task execution; queue excess; prevent OOM and CPU starvation
- **Data consistency**: If DAG fails mid-execution, ensure partial results are cleaned up or clearly marked incomplete
- **Secret management**: Never hardcode credentials in DAG definitions; use vault integration (HashiCorp Vault, AWS Secrets Manager)
- **Change management**: Version DAG definitions; test in staging before production; canary deployments for critical workflows
