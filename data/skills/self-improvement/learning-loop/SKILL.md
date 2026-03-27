---
name: learning-loop
description: Extract learnings from interactions and improve over time
version: 1.0.0
author: ROOT
tags: [learning, evolution, memory, reflection]
platforms: [darwin, linux, win32]
---

# Learning Loop

Derived from HERMES memory system + ECC learn command + ROOT reflection engine.

## When to Use
- After every meaningful interaction with Yohan
- After completing a complex task
- When discovering new patterns or making mistakes
- Periodically (every 10 interactions or 1 hour)

## The Loop

```
Interaction → Extract Facts → Store in Memory → Periodic Reflection
     ↑                                                    ↓
     └────────── Apply Learnings ← Prune/Strengthen ←────┘
```

## Steps

### 1. Auto-Extract (after each interaction)
- Use fast model to identify: facts, preferences, goals, observations
- Cap at 5 new memories per exchange
- Confidence starts at 0.85 (verified through use)

### 2. Memory Management
- Strengthen memories that get accessed (boost +0.05)
- Decay unused memories (factor 0.995 daily)
- Supersede outdated memories (link old → new)
- Prune below 0.05 confidence threshold

### 3. Self-Reflection (periodic)
- Examine recent 30 + strongest 20 memories
- Identify patterns, contradictions, gaps
- Create new learning memories from insights
- Adjust confidence on existing memories
- Propose action items for improvement

### 4. Skill Creation
- When a successful pattern emerges 3+ times, create a SKILL.md
- Skills are reusable procedural memory
- Skills improve through use (version bumps)

## Anti-Patterns
- Don't store everything — be selective
- Don't override user corrections
- Don't create duplicate memories
- Don't reflect on trivial interactions
