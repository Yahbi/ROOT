---
name: code-review
description: Review code for bugs, security issues, performance, and best practices
version: 1.0.0
author: ROOT
tags: [code, review, quality, security]
platforms: [darwin, linux, win32]
---

# Code Review

## When to Use
When ROOT or Yohan needs to review code for quality and correctness.

## Checklist
### Correctness
- Logic matches requirements
- Edge cases handled
- Error handling present

### Security (OWASP Top 10)
- No hardcoded secrets
- Input validation present
- SQL injection prevention
- XSS prevention

### Performance
- No N+1 queries
- Appropriate caching
- Async where beneficial

### Style
- Consistent naming
- Functions under 50 lines
- Files under 800 lines
- Immutable patterns
