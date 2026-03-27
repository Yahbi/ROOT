---
name: parallel-delegation
description: Delegate tasks to multiple agents in parallel with isolated contexts
version: 1.0.0
author: ROOT
tags: [delegation, parallel, agents, orchestration]
platforms: [darwin, linux, win32]
---

# Parallel Delegation

Derived from HERMES delegate_tool.py and Agent Orchestrator patterns.

## When to Use
- Task can be broken into independent subtasks
- Multiple agents have relevant capabilities
- Time-sensitive work that benefits from parallelism

## Pattern

1. **Decompose** the task into independent subtasks
2. **Select** the best agent for each subtask based on capabilities
3. **Isolate** each agent's context (fresh conversation, restricted toolset)
4. **Execute** all subtasks concurrently (max 3 parallel)
5. **Collect** summaries only (opaque — no intermediate data leaks)
6. **Synthesize** results into unified response

## Key Rules
- MAX_CONCURRENT = 3 (prevents resource exhaustion)
- MAX_DEPTH = 2 (no grandchild delegation)
- Child agents NEVER get: delegate, memory, or clarify tools
- Parent sees ONLY summary + metadata
- Each child gets a focused system prompt from goal + context

## Error Handling
- If child fails, return partial results with error status
- Track duration and API call count per subtask
- Timeout after configurable limit (default 120s)

## Example Flow
```
ROOT receives: "Research market trends and backtest top strategy"
  ├── Subtask 1 → Trading Swarm: "Research latest crypto strategies"
  ├── Subtask 2 → MiRo: "Simulate market sentiment for top 3 coins"
  └── Subtask 3 → HERMES: "Find recent regulatory news"

Results merged → ROOT synthesizes report for Yohan
```
