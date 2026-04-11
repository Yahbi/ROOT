---
name: API Gateway Design
description: Rate limiting, authentication, request transformation, versioning, canary routing
version: "1.0.0"
author: ROOT
tags: [architecture, api-gateway, rate-limiting, versioning, canary, routing]
platforms: [all]
---

# API Gateway Design

Implement a robust API gateway that handles cross-cutting concerns and routes traffic intelligently.

## Gateway Responsibilities

### Core Functions
```
Client → API Gateway → Backend Services
           │
           ├── Authentication & Authorization
           ├── Rate Limiting & Throttling
           ├── Request/Response Transformation
           ├── Load Balancing & Routing
           ├── Caching (response-level)
           ├── Logging & Metrics
           └── Circuit Breaking
```

### Gateway Selection
| Gateway | Type | Best For |
|---------|------|----------|
| Kong | Self-hosted, plugin-based | Full control, extensive plugins |
| AWS API Gateway | Managed | AWS-native, serverless backends |
| Envoy + custom control plane | Programmable proxy | Service mesh integration |
| Traefik | Self-hosted, auto-discovery | Docker/Kubernetes, simple config |
| FastAPI middleware | Application-level | Small deployments, Python stack |

## Rate Limiting

### Multi-Tier Strategy
```yaml
rate_limits:
  global:
    requests_per_second: 10000     # Total gateway capacity
  per_ip:
    anonymous: 60/minute           # Unauthenticated clients
    authenticated: 600/minute      # Authenticated clients
  per_user:
    standard: 1000/hour            # Standard tier
    premium: 10000/hour            # Premium tier
  per_endpoint:
    POST /api/chat: 20/minute      # Expensive LLM endpoint
    GET /api/health: 600/minute    # Lightweight health check
    POST /api/export: 5/minute     # Resource-intensive export
```

### Algorithm Choice
| Algorithm | Behavior | Trade-off |
|-----------|----------|-----------|
| Fixed window | Reset counter every N seconds | Simple; allows burst at window boundary |
| Sliding window | Count requests in rolling window | Accurate; slightly more memory |
| Token bucket | Tokens refill at steady rate, burst allowed | Smooth; allows controlled bursts |
| Leaky bucket | Process at constant rate, queue excess | Smoothest; adds latency |

### Rate Limit Response
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705312800

{"error": "rate_limit_exceeded", "retry_after_seconds": 30}
```

## Authentication at the Gateway

### Auth Flow
1. Client sends request with token (Bearer JWT, API key, session cookie)
2. Gateway validates token (JWT signature check, API key lookup, session store)
3. Gateway injects identity headers: `X-User-ID`, `X-User-Roles`, `X-Tenant-ID`
4. Backend trusts these headers (only accepts them from gateway, not directly)
5. Gateway strips auth headers from responses

### Token Validation
- JWT: validate signature, expiry, issuer, audience at gateway (no backend call needed)
- API key: hash lookup in Redis/database (cache results for 60 seconds)
- Session: check session store (Redis) at gateway
- Gateway should reject 100% of invalid auth before it reaches backends

## Request Transformation

### Common Transformations
```yaml
# Add headers based on auth context
request_transform:
  add_headers:
    X-User-ID: "{{ jwt.sub }}"
    X-Request-ID: "{{ uuid() }}"
    X-Forwarded-For: "{{ client_ip }}"
  remove_headers:
    - Authorization  # Strip before forwarding (backend uses X-User-ID)

# Response transform: remove internal headers
response_transform:
  remove_headers:
    - X-Internal-Trace
    - Server
  add_headers:
    X-Request-ID: "{{ request.X-Request-ID }}"
```

### Request Aggregation
- Frontend requests `/api/dashboard` → gateway fans out to 3 backend services
- Gateway merges responses and returns single payload
- Reduces client-side complexity and number of round trips
- Set timeout per backend call; return partial data if one backend is slow

## API Versioning

### Versioning Strategies
| Strategy | Example | Pros | Cons |
|----------|---------|------|------|
| URL path | `/v2/api/users` | Explicit, easy to route | URL changes on version bump |
| Header | `Accept: application/vnd.api.v2+json` | Clean URLs | Hidden, harder to test |
| Query param | `/api/users?version=2` | Simple | Easily lost in caching |

### Version Lifecycle
1. **Active**: Current version, full support
2. **Deprecated**: 6-month sunset notice, return `Deprecation` header
3. **Retired**: Return 410 Gone with migration guide URL
4. Route deprecated version traffic through a compatibility layer if possible

## Canary Routing

### Traffic Splitting
```yaml
# Route 5% of traffic to new version
routes:
  - match: { path: "/api/orders" }
    backends:
      - service: orders-v2
        weight: 5              # 5% canary
      - service: orders-v1
        weight: 95             # 95% stable
```

### Canary Decision Criteria
| Metric | Canary Threshold | Action if Exceeded |
|--------|-----------------|-------------------|
| Error rate | > 1% (or 2x baseline) | Auto-rollback |
| P99 latency | > 2x baseline | Pause rollout, investigate |
| Success rate | < 99% | Auto-rollback |

### Progressive Rollout
1. 1% traffic for 10 minutes → check metrics
2. 5% for 30 minutes → check metrics
3. 25% for 1 hour → check metrics
4. 50% for 2 hours → check metrics
5. 100% → complete rollout, decommission old version
