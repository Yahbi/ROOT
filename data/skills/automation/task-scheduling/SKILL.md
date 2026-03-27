---
name: task-scheduling
description: Schedule and automate recurring tasks with cron patterns and event triggers
version: 1.0.0
author: ROOT
tags: [automation, scheduling, cron, tasks]
platforms: [darwin, linux, win32]
---

# Task Scheduling & Automation

## When to Use
When ROOT needs to run tasks periodically or in response to events.

## Procedure
1. **Define Task**: Clear description, input/output, success criteria
2. **Set Schedule**: Choose frequency (cron, interval, event-driven)
3. **Build Handler**: Create async function that performs the work
4. **Register Hook**: Use HookEngine for event-driven tasks
5. **Monitor**: Track execution, failures, and timing
6. **Alert**: Notify on failure or drift from expected behavior

## Schedule Patterns
- interval: Every N seconds/minutes/hours
- daily: Once per day at specific time
- on_event: Triggered by hook events (ON_CHAT, ON_LEARN, etc.)
- on_condition: When a specific condition becomes true

## Best Practices
- Always set timeouts for scheduled tasks
- Log every execution with duration and outcome
- Use idempotent operations (safe to retry)
- Handle partial failures gracefully
