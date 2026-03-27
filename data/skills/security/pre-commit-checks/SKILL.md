---
name: pre-commit-checks
description: Security checklist before any code commit
version: 1.0.0
author: ROOT
tags: [security, commits, checklist, OWASP]
platforms: [darwin, linux, win32]
---

# Pre-Commit Security Checks

From ECC security rules — MANDATORY before any commit.

## Checklist

- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated at system boundaries
- [ ] SQL injection prevention (parameterized queries only)
- [ ] XSS prevention (sanitized HTML output)
- [ ] CSRF protection enabled on state-changing endpoints
- [ ] Authentication and authorization verified
- [ ] Rate limiting on all public endpoints
- [ ] Error messages don't leak sensitive data (no stack traces in prod)

## Secret Management
- NEVER hardcode secrets in source code
- Use environment variables or secret manager
- Validate required secrets at startup
- .env files in .gitignore

## If Security Issue Found
1. STOP immediately — don't commit
2. Fix the issue
3. Check for similar patterns elsewhere
4. Rotate any potentially exposed secrets
5. Document the fix and pattern to avoid
