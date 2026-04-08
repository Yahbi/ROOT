---
name: Technical Writing
description: Documentation, API docs, architecture decision records, and writing standards
version: "1.0.0"
author: ROOT
tags: [communication, technical-writing, documentation, API-docs, ADR]
platforms: [all]
---

# Technical Writing

Create clear, maintainable technical documentation that serves its intended audience.

## Documentation Types

### API Documentation
- **Endpoint reference**: Method, path, parameters, request/response examples, error codes
- **Authentication guide**: How to obtain and use credentials
- **Quickstart**: Get from zero to first API call in < 5 minutes
- **Use OpenAPI/Swagger spec** as the source of truth — generate docs from it
- Include runnable examples (curl, Python, JavaScript)

### Architecture Decision Records (ADRs)
```
# ADR-001: Use SQLite for local storage

## Status: Accepted

## Context
We need a persistent storage solution that works offline,
requires no separate server process, and supports concurrent reads.

## Decision
Use SQLite with WAL mode for all local databases.

## Consequences
- Positive: Zero configuration, single file per database, fast reads
- Negative: Limited concurrent write throughput, no built-in replication
- Risk: Database file corruption if improper shutdown (mitigated by WAL)
```

### README Structure
1. One-sentence description of what the project does
2. Quick start: install + run in 3 commands
3. Key features (bullet list, not paragraphs)
4. Configuration reference (environment variables, config files)
5. API overview (link to full API docs)
6. Contributing guide

## Writing Principles

### Audience-First
- **Developer docs**: Assume coding knowledge, focus on integration details
- **User guides**: Assume no technical knowledge, focus on outcomes
- **Operations docs**: Assume infrastructure knowledge, focus on procedures

### Clarity Rules
- One idea per sentence, one topic per paragraph
- Use active voice: "The function returns X" not "X is returned by the function"
- Define acronyms on first use
- Use consistent terminology (pick one term and stick with it)
- Code examples should be copy-paste runnable (tested in CI)

### Structure
- Use headings liberally (readers scan, they don't read linearly)
- Tables for structured comparisons
- Code blocks for anything that goes in a file or terminal
- Numbered lists for procedures, bullet lists for options

## Maintenance

### Keep Docs Current
- Treat documentation as code — review in PRs alongside code changes
- Automated tests for code examples (doctest, mdx-test)
- Quarterly review: mark stale docs, update or archive
- Version docs alongside software versions
- Dead documentation is worse than no documentation — it misleads

### Documentation Metrics
- Measure: search queries with no results (gap indicator)
- Measure: support tickets about documented topics (quality indicator)
- Measure: time-to-first-API-call for new developers (onboarding effectiveness)
