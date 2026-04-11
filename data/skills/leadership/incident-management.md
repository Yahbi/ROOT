---
name: Incident Management
description: Severity levels, on-call rotation, blameless post-mortems, SLOs
version: "1.0.0"
author: ROOT
tags: [leadership, incident-management, on-call, post-mortem, SLO, reliability]
platforms: [all]
---

# Incident Management

Run reliable systems with structured incident response, sustainable on-call, and continuous learning from failures.

## Severity Levels

### Classification
| Level | Criteria | Response | Communication |
|-------|----------|----------|---------------|
| SEV-1 | Service down, data loss, security breach | All-hands, immediate | Status page, exec notification, customer comms |
| SEV-2 | Major feature broken, significant degradation | On-call + team lead, < 30 min | Status page, internal notification |
| SEV-3 | Minor feature broken, workaround exists | On-call, < 4 hours | Internal notification |
| SEV-4 | Cosmetic issue, non-customer-facing | Next business day | Ticket only |

### Severity Decision Guide
- Ask: "How many users are affected?" and "Is there a workaround?"
- When in doubt, escalate to higher severity (can always downgrade)
- Automated alerts should include suggested severity based on signal type
- On-call engineer has authority to escalate severity without approval

## On-Call Rotation

### Sustainable On-Call Design
```
Primary:    Engineer A (week 1) → Engineer B (week 2) → ...
Secondary:  Engineer B (week 1) → Engineer C (week 2) → ...

Rotation: Weekly, handoff on Monday morning
Coverage: All team members participate (including leads)
Compensation: Comp time or additional pay (on-call without compensation breeds resentment)
```

### On-Call Expectations
- Acknowledge alerts within 15 minutes (SEV-1/2) or 1 hour (SEV-3)
- Carry laptop and phone, maintain internet access during on-call shift
- Keep response time low: automated runbooks and playbooks for common issues
- Escalate to secondary if unable to respond or issue exceeds expertise

### Reducing On-Call Burden
| Problem | Fix |
|---------|-----|
| Too many alerts | Tune alert thresholds, deduplicate, fix noisy alerts |
| Alerts during sleep | Fix the root cause, not the symptom. If pages happen nightly, it is a reliability bug |
| Single point of expertise | Cross-train team, document runbooks, pair on incident response |
| Alert fatigue | Target < 2 actionable alerts per on-call shift per week |

## Blameless Post-Mortems

### Principles
- **Blameless**: Focus on system failures, not individual mistakes. Humans make errors; systems should catch them.
- **Mandatory**: Every SEV-1 and SEV-2 gets a post-mortem (no exceptions)
- **Timely**: Schedule within 48 hours of resolution (memories fade, details matter)
- **Actionable**: Every post-mortem produces specific, assigned, deadline action items

### Post-Mortem Template
```markdown
# Post-Mortem: [Title]
**Date**: YYYY-MM-DD  **Severity**: SEV-X  **Duration**: Xh Xm

## Summary
[One paragraph: what happened, impact, resolution]

## Timeline (UTC)
- 14:00 — Alert fired: API error rate > 5%
- 14:05 — On-call acknowledged, began investigation
- 14:15 — Root cause identified: database connection pool exhausted
- 14:20 — Mitigation: increased pool size, restarted service
- 14:25 — Service recovered, monitoring confirmed

## Impact
- Users affected: X,XXX
- Duration: XX minutes
- Revenue impact: $X,XXX (estimated)
- Data loss: None / Description

## Root Cause
[Technical explanation of what failed and why]

## Contributing Factors
- [What made the incident more likely or harder to resolve]

## Action Items
| Action | Owner | Priority | Due Date |
|--------|-------|----------|----------|
| Add connection pool monitoring alert | @engineer | P0 | 3 days |
| Implement connection pool auto-scaling | @team | P1 | 2 weeks |
| Update runbook for DB connection issues | @oncall | P2 | 1 week |

## Lessons Learned
[What we want the organization to remember]
```

### Post-Mortem Meeting Format (45 min)
1. Read the written post-mortem silently (10 min)
2. Walk through the timeline together (10 min)
3. Discuss root cause and contributing factors (10 min)
4. Generate and assign action items (10 min)
5. Share lessons learned and close (5 min)

## SLOs (Service Level Objectives)

### Defining SLOs
```
SLI (Indicator): What we measure
  → Availability: % of successful requests (status < 500)
  → Latency: % of requests completing under threshold (P99 < 500ms)
  → Correctness: % of requests returning correct data

SLO (Objective): Our target
  → 99.9% availability (allows 43 minutes downtime/month)
  → 99% of requests under 500ms

Error Budget: The allowed failure
  → 0.1% of requests can fail = ~4,320 failures per 4.32M requests/month
```

### Error Budget Policy
| Budget Status | Action |
|--------------|--------|
| > 50% remaining | Ship features normally |
| 25-50% remaining | Increase testing rigor, reduce deployment frequency |
| < 25% remaining | Freeze features, focus on reliability work |
| Exhausted | Full reliability sprint until budget replenishes |

### SLO Best Practices
- Start with fewer SLOs (2-3 per service) and add as needed
- Set SLOs based on user expectations, not system capability
- Review SLOs quarterly: are they too tight (constant fire drills) or too loose (users complaining)?
- SLOs drive prioritization: reliability work competes with features via error budget
