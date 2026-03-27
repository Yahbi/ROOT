---
name: session-lifecycle
description: Manage agent session states from spawn to completion
version: 1.0.0
author: ROOT
tags: [sessions, lifecycle, state-machine]
platforms: [darwin, linux, win32]
---

# Session Lifecycle Management

Derived from Agent Orchestrator's session state machine.

## When to Use
- Managing long-running agent tasks
- Tracking work across multiple agents
- Handling CI/review/merge workflows

## States

```
spawning → working → pr_open → ci_failed → review_pending
                                    ↓
                           changes_requested → approved → mergeable → merged → done
```

Activity states: active, ready, idle, waiting_input, blocked, exited

## Reactions (Auto-Handling)
- CI fails → forward logs to agent for fixes (max 2 retries)
- Review comments → send to agent for changes
- Approved + green CI → notify Yohan to merge
- Stuck for >30min → escalate to ROOT for reassignment

## Key Patterns
- Metadata stored as simple key=value (not JSON)
- Hash-based namespacing prevents ID collisions
- Archive completed sessions (don't delete)
- Single source of truth in config file
