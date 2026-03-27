---
name: skill-creation
description: Create new reusable skills from successful patterns and experience
version: 1.0.0
author: ROOT
tags: [skills, creation, patterns, procedural-memory]
platforms: [darwin, linux, win32]
---

# Skill Creation

Derived from HERMES skills system + ECC skill-create command.

## When to Use
- A successful pattern has been used 3+ times
- Yohan explicitly asks ROOT to remember a workflow
- A complex task was solved and the approach is generalizable
- After reflecting on a series of similar tasks

## SKILL.md Format

```yaml
---
name: descriptive-kebab-case
description: One line explaining when to use this skill
version: 1.0.0
author: ROOT
tags: [relevant, keywords]
platforms: [darwin, linux, win32]
---

# Skill Title

## When to Use
- Trigger conditions

## Steps
1. Step-by-step procedure
2. With code examples where helpful

## Key Rules
- Constraints and gotchas

## Anti-Patterns
- What NOT to do
```

## Creation Process
1. Identify the repeating pattern from memory/reflections
2. Extract the generalizable steps (remove specifics)
3. Write the SKILL.md with frontmatter
4. Store in data/skills/{category}/{name}/SKILL.md
5. Reload skill engine to index
6. Log creation in memory

## Categories
- agent-orchestration/: Multi-agent coordination
- self-improvement/: Learning and evolution
- coding-standards/: Code quality patterns
- security/: Security practices
- llm-inference/: Model usage patterns
- swarm-simulation/: Simulation techniques
- multi-platform/: Cross-platform patterns
- trading/: Financial analysis patterns
