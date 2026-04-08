---
name: Agent Design
description: Designing multi-agent systems with roles, communication patterns, and consensus mechanisms
version: "1.0.0"
author: ROOT
tags: [ai-engineering, agents, multi-agent, orchestration, consensus]
platforms: [all]
---

# Multi-Agent System Design

Design effective multi-agent architectures with clear roles, communication, and decision-making.

## Agent Architecture Patterns

### 1. Hierarchical (Manager-Worker)
- A coordinator agent decomposes tasks and delegates to specialist agents
- Workers report results back to coordinator for synthesis
- **Best for**: Complex tasks with clear subtask decomposition
- **Example**: ROOT's ASTRA routing to specialized agents

### 2. Pipeline (Sequential)
- Each agent processes output from the previous agent
- Linear chain: Research -> Analyze -> Draft -> Review -> Publish
- **Best for**: Multi-stage workflows with clear ordering

### 3. Fan-Out / Fan-In (Parallel)
- Multiple agents work on the same input independently
- Results are aggregated (vote, merge, best-of-n)
- **Best for**: Tasks benefiting from diverse perspectives

### 4. Council (Debate)
- Agents with different perspectives debate a question
- Moderator synthesizes consensus or highlights disagreements
- **Best for**: High-stakes decisions, risk assessment

## Agent Role Design Principles

1. **Single responsibility**: each agent has one clear domain of expertise
2. **Clear interface**: define exact input format, output format, and failure modes
3. **Stateless preference**: agents should be callable without prior context when possible
4. **Graceful degradation**: define fallback behavior when an agent fails or times out
5. **Observable**: every agent logs its reasoning, confidence, and sources

## Communication Patterns

- **Direct messaging**: agent-to-agent for targeted delegation
- **Pub/sub topics**: broadcast events (e.g., "market_alert") for reactive agents
- **Shared memory**: common knowledge base all agents can read/write
- **Structured handoffs**: JSON schema defining exact fields passed between agents

## Consensus and Conflict Resolution

| Method | When to Use | Mechanism |
|--------|------------|-----------|
| Majority vote | Low-stakes, clear categories | Count votes, majority wins |
| Weighted vote | Agents have different expertise | Weight by historical accuracy |
| Moderator synthesis | Complex, nuanced decisions | One agent synthesizes all views |
| Confidence-gated | Variable certainty | Highest-confidence agent wins |
| Escalation | No agreement | Escalate to human or higher authority |

## Error Handling

- **Timeout**: set per-agent timeout (30-120s), fallback to cached/default response
- **Retry**: retry transient failures (API errors) up to 3 times with exponential backoff
- **Circuit breaker**: disable agent after 5 consecutive failures, re-enable after cooldown
- **Fallback chain**: if primary agent fails, try secondary, then default response
