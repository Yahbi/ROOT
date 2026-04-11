---
name: Problem Solving
description: Root cause analysis, 5 Whys, fishbone diagrams, and systematic debugging
version: "1.0.0"
author: ROOT
tags: [general, problem-solving, root-cause, analysis, debugging]
platforms: [all]
---

# Problem Solving

Systematic methods for identifying root causes and developing effective solutions.

## Root Cause Analysis

### The 5 Whys
1. Start with the problem statement
2. Ask "Why did this happen?"
3. Take the answer and ask "Why?" again
4. Repeat until you reach a root cause (typically 3-7 iterations)
5. The root cause is something you can fix with a systemic change

### Example
- Problem: "The API returned errors for 30 minutes"
- Why? The database was unreachable
- Why? The connection pool was exhausted
- Why? A slow query was holding connections for 60+ seconds
- Why? A missing index caused a full table scan on a 10M row table
- Root cause: Missing index → Fix: Add the index + add query timeout + alert on slow queries

### 5 Whys Pitfalls
- Stopping too early (fixing symptoms, not root cause)
- Blame-focused answers ("because John made a mistake") — ask why the system allowed it
- Single-track analysis — problems often have multiple contributing causes

## Fishbone Diagram (Ishikawa)

### Categories for Software Systems
- **People**: Training gaps, unclear responsibilities, communication failures
- **Process**: Missing code review, no testing, inadequate deployment procedures
- **Technology**: Tool limitations, infrastructure failures, dependency issues
- **Environment**: Load spikes, configuration differences between environments
- **Data**: Bad input data, stale cache, data corruption

### How to Build
1. Write the problem at the "head" of the fish
2. Draw major category branches (bones)
3. Brainstorm potential causes under each category
4. Identify which causes are most likely (based on evidence)
5. Investigate top 3 most likely causes

## Problem Decomposition

### Breaking Down Complex Problems
1. **Define the problem precisely**: "Revenue dropped" is vague; "MRR decreased 15% in March" is specific
2. **Identify sub-problems**: Which segments? Which products? New vs existing customers?
3. **Isolate variables**: Change one thing at a time when testing solutions
4. **Validate assumptions**: What do you think is true that you haven't verified?

### MECE Framework (Mutually Exclusive, Collectively Exhaustive)
- Break the problem into non-overlapping categories that cover all possibilities
- Example: Revenue decline = fewer customers OR lower revenue per customer
- Each branch should be further decomposable until you reach actionable causes

## Solution Development

### Generating Options
- Brainstorm at least 3 solutions before evaluating any of them
- Include: quick fix (band-aid), medium fix (proper solution), long-term fix (systemic change)
- Consider: cost, time to implement, risk, reversibility, side effects

### Evaluating Solutions
| Criterion | Weight | Option A | Option B | Option C |
|-----------|--------|----------|----------|----------|
| Effectiveness | 30% | | | |
| Speed to implement | 25% | | | |
| Cost | 20% | | | |
| Risk | 15% | | | |
| Durability | 10% | | | |

### After Solving
- Document the problem, root cause, solution, and outcome
- Create monitoring/alerting so you detect this problem class early in the future
- Share the learning with the team (post-mortem or knowledge base entry)
- Ask: "What similar problems might exist that we haven't found yet?"
