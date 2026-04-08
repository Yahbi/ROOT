---
name: Architecture Decision Records
description: ADR template, decision log, lightweight RFC process
version: "1.0.0"
author: ROOT
tags: [leadership, ADR, architecture, decision-log, RFC, documentation]
platforms: [all]
---

# Architecture Decision Records

Document architectural decisions to preserve context and rationale for future teams.

## Why ADRs Matter

### Problems ADRs Solve
- "Why was this built this way?" — New engineers reverse-engineering decisions from code
- "Should we change this?" — No record of trade-offs that led to the current design
- "Who decided this?" — Accountability and context lost when team members leave
- "We already tried that" — Repeating failed approaches because failures were not documented

### ADR Principles
- One ADR per decision (atomic, searchable)
- ADRs are immutable once accepted (supersede with new ADR, do not edit old ones)
- Short and focused (1-2 pages max, not a design document)
- Written by the proposer, reviewed by stakeholders

## ADR Template

### Minimal Viable ADR
```markdown
# ADR-NNN: [Title of Decision]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Context
[What is the situation? What forces are at play? Why does this decision need to be made now?]

## Decision
[What is the change that we are proposing and/or doing?]

## Consequences

### Positive
- [What becomes easier or better?]

### Negative
- [What becomes harder or worse?]

### Risks
- [What could go wrong? How do we mitigate?]

## Alternatives Considered

### [Alternative A]
- Pros: [...]
- Cons: [...]
- Why rejected: [...]

### [Alternative B]
- Pros: [...]
- Cons: [...]
- Why rejected: [...]
```

### Worked Example
```markdown
# ADR-007: Use SQLite with WAL Mode for All Local Databases

## Status
Accepted (2025-01-15)

## Context
ROOT needs persistent storage for 16 different data types (memories, conversations,
learning data, trading signals, etc.). The system runs as a single-server application
and must work offline. We need concurrent read access with low latency.

## Decision
Use SQLite in WAL mode for all local databases, one file per logical database.

## Consequences

### Positive
- Zero configuration: no separate database server to install or manage
- Excellent read performance with WAL mode (readers do not block writers)
- Simple backup: copy the file (or use SQLite backup API for hot backups)
- Battle-tested: SQLite is the most deployed database engine in the world

### Negative
- Single writer at a time (write throughput limited by serialization)
- No built-in replication (addressed by Litestream if needed later)
- No user-level access control (all code has full database access)

### Risks
- Write contention under heavy load: mitigated by keeping write transactions short
- Database file corruption on improper shutdown: mitigated by WAL mode + PRAGMA synchronous=NORMAL

## Alternatives Considered

### PostgreSQL
- Pros: Concurrent writes, built-in replication, robust tooling
- Cons: Requires separate server process, configuration, operational overhead
- Rejected: Overkill for single-server deployment; adds infrastructure complexity

### Redis
- Pros: Fastest reads, built-in pub/sub
- Cons: Memory-only by default, limited query capability, no relational data
- Rejected: Not suitable as primary data store for structured data
```

## Decision Log Management

### File Organization
```
docs/adr/
├── 0001-use-sqlite-for-storage.md
├── 0002-choose-fastapi-framework.md
├── 0003-adopt-pydantic-for-models.md
├── 0004-implement-plugin-engine.md
├── ...
├── 0007-use-sqlite-wal-mode.md
├── template.md
└── README.md  (index of all ADRs with status)
```

### ADR Index
Maintain a table in the README for quick scanning:

| ID | Title | Status | Date |
|----|-------|--------|------|
| 001 | Use SQLite for storage | Accepted | 2024-06-01 |
| 002 | Choose FastAPI framework | Accepted | 2024-06-01 |
| 003 | Adopt Pydantic for models | Accepted | 2024-06-15 |
| 004 | Implement plugin engine | Superseded by 012 | 2024-07-01 |

### Lifecycle
1. **Proposed**: Author writes ADR and submits for review
2. **Accepted**: Stakeholders approve (via PR review or meeting)
3. **Deprecated**: Decision no longer relevant (system decommissioned)
4. **Superseded**: New ADR replaces this one (link to successor)

## Lightweight RFC Process

### When ADR vs RFC
| Document | Length | Use When |
|----------|--------|----------|
| ADR | 1-2 pages | Single decision with clear options |
| RFC | 3-10 pages | Complex change requiring design exploration |
| Design Doc | 10+ pages | Major system redesign, new product |

### RFC Template Additions (beyond ADR)
```markdown
## Detailed Design
[Technical specification: APIs, data models, system interactions]

## Rollout Plan
[How to implement: phases, feature flags, migration steps]

## Open Questions
[Unresolved issues that need input from reviewers]

## Timeline
[Estimated effort and milestones]
```

### RFC Review Process
1. Author writes RFC draft (2-5 days)
2. Share for async review (3-5 business days review period)
3. Schedule 30-minute review meeting for outstanding questions
4. Author updates RFC based on feedback
5. Decision made: accept, reject, or request revision
6. If accepted, extract key decision into an ADR for the permanent record

## Tooling

### ADR Tools
```bash
# adr-tools: CLI for managing ADRs
adr new "Use SQLite for storage"      # Creates numbered file from template
adr list                               # Shows all ADRs
adr link 4 "Supersedes" 2             # Link related ADRs
```

### Integration with Development
- Store ADRs in the same repository as code (versioned together)
- Require ADR for PRs that change architecture (enforce in PR template)
- Reference ADR numbers in code comments: `# See ADR-007 for why we use WAL mode`
- Review ADRs during onboarding (fastest way to understand system context)
