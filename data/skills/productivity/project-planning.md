---
name: Project Planning
description: Work breakdown structure, estimation, dependency tracking, and execution
version: "1.0.0"
author: ROOT
tags: [productivity, project-planning, estimation, WBS, dependencies]
platforms: [all]
---

# Project Planning

Break projects into manageable pieces with realistic estimates and clear dependencies.

## Work Breakdown Structure (WBS)

### Creating the WBS
1. Start with the final deliverable (what does "done" look like?)
2. Decompose into major phases (3-7 phases is ideal)
3. Break each phase into tasks (each task = 2-8 hours of work)
4. Stop when tasks are small enough to estimate confidently
5. Every task must have a clear completion criteria (how do you know it's done?)

### WBS Rules
- No task should take more than 2 days (if it does, break it down further)
- Every task has exactly one owner (shared ownership = no ownership)
- Include "invisible" tasks: testing, documentation, code review, deployment
- Add buffer tasks: integration testing, bug fixing, polish

## Estimation

### Estimation Methods
| Method | When to Use | Accuracy |
|--------|------------|----------|
| Expert judgment | Familiar work, experienced team | Medium |
| Analogy | Similar past project exists | Medium-High |
| Three-point (PERT) | Uncertain tasks | High |
| T-shirt sizing | Early planning, portfolio | Low (relative) |

### Three-Point Estimation (PERT)
```
Expected = (Optimistic + 4 * Most Likely + Pessimistic) / 6
Standard deviation = (Pessimistic - Optimistic) / 6
```
- Optimistic: Everything goes perfectly (10th percentile)
- Most likely: Realistic scenario
- Pessimistic: Significant problems (90th percentile)
- This naturally accounts for uncertainty and right-skewed task distributions

### Estimation Calibration
- Track actual vs estimated time for every task
- Compute your personal multiplier (if you consistently take 1.5x, multiply estimates by 1.5)
- Review estimates retroactively monthly to improve accuracy
- Common bias: developers underestimate by 50-100% — apply a buffer

## Dependency Tracking

### Dependency Types
- **Finish-to-Start**: B can't start until A finishes (most common)
- **Start-to-Start**: B can't start until A starts (parallel with lag)
- **External**: Blocked by something outside your control (API access, vendor delivery)

### Critical Path
- The longest sequence of dependent tasks = the project's minimum duration
- Any delay on the critical path delays the entire project
- Non-critical tasks have "float" — can slip without impacting the deadline
- Focus management attention on critical path tasks

## Execution Tracking

### Daily Check-In
- What was completed yesterday?
- What's planned for today?
- Any blockers? (escalate immediately, don't wait)

### Status Signals
| Signal | Status | Action |
|--------|--------|--------|
| On track, no issues | Green | Continue as planned |
| Minor risk, mitigation in progress | Yellow | Monitor closely, update stakeholders |
| Behind schedule or blocked | Red | Escalate, reallocate resources, cut scope |

### Scope Management
- Maintain a "not doing" list alongside the "doing" list
- New requests go to a backlog, not into the current plan
- If scope must increase, something else must decrease (time, quality, other features)
- Document every scope change with impact assessment

## Planning Checklist

- [ ] Goal and success criteria clearly defined
- [ ] WBS created with tasks < 2 days each
- [ ] Estimates include buffer for unknowns (15-25%)
- [ ] Dependencies mapped, critical path identified
- [ ] Owners assigned for every task
- [ ] Risks identified with mitigation plans
- [ ] Communication cadence agreed with stakeholders
- [ ] Definition of "done" documented
