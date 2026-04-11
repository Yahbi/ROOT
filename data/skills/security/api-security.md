---
name: API Security
description: JWT, OAuth2, rate limiting, CORS, input validation, and API hardening
version: "1.0.0"
author: ROOT
tags: [security, api, JWT, OAuth2, rate-limiting, CORS, validation]
platforms: [all]
---

# API Security

Protect APIs against common attack vectors with defense-in-depth.

## Authentication

### JWT Best Practices
- Use RS256 (asymmetric) over HS256 (symmetric) for multi-service architectures
- Short expiration: access tokens 15-30 minutes, refresh tokens 7-30 days
- Include only necessary claims: `sub`, `exp`, `iat`, `roles` (minimize token size)
- Store refresh tokens securely (httpOnly cookie or encrypted storage)
- Implement token revocation via blocklist for logout and security incidents

### OAuth2 Flows
| Flow | Use Case | Security Level |
|------|---------|---------------|
| Authorization Code + PKCE | Web apps, mobile apps | Highest |
| Client Credentials | Server-to-server | High |
| Device Code | Smart TVs, CLI tools | High |
| Implicit (deprecated) | Legacy SPAs | Low — do not use |

### API Key Authentication
- Use for server-to-server calls where OAuth2 is overkill
- Compare keys using `hmac.compare_digest()` (timing-safe)
- Prefix keys for identification: `sk_live_...`, `sk_test_...`
- Support key rotation: accept old key for 48 hours after new key issued

## Rate Limiting

### Strategy
- Per-IP: 100 requests/minute for anonymous, 1000/minute for authenticated
- Per-user: 500 requests/minute with burst allowance of 50
- Per-endpoint: tighter limits on expensive endpoints (search, export)
- Use sliding window algorithm (more accurate than fixed window)

### Response
- Return `429 Too Many Requests` with `Retry-After` header
- Include rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Input Validation

### Validation Checklist
- Type validation: reject wrong types early (string where int expected)
- Range validation: bound numeric inputs (max page size, min/max amounts)
- Length validation: limit string lengths (prevent memory exhaustion)
- Format validation: regex for emails, URLs, phone numbers
- Content validation: sanitize HTML, reject dangerous characters for SQL/XSS
- Use Pydantic or JSON Schema for automatic validation

### Common Attacks to Defend Against
| Attack | Defense |
|--------|---------|
| SQL Injection | Parameterized queries, ORM, input validation |
| XSS | Output encoding, CSP headers, input sanitization |
| SSRF | Allowlist URLs, block internal IPs, validate redirects |
| Mass Assignment | Explicit field allowlists (not blocklists) |
| IDOR | Authorization check on every resource access |

## CORS Configuration

- Never use `Access-Control-Allow-Origin: *` with credentials
- Allowlist specific origins: `["https://app.example.com"]`
- Restrict methods: only allow methods the API actually supports
- Set `Access-Control-Max-Age` to cache preflight (3600 seconds)

## Security Headers

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
X-Request-ID: <uuid> (for tracing)
```
