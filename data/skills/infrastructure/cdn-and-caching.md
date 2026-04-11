---
name: CDN and Caching
description: Cache headers, invalidation strategies, edge computing, stale-while-revalidate
version: "1.0.0"
author: ROOT
tags: [infrastructure, cdn, caching, edge, http-headers, invalidation]
platforms: [all]
---

# CDN and Caching

Design caching layers that maximize hit rates while maintaining content freshness.

## HTTP Cache Headers

### Header Reference
```
# Cacheable for 1 hour by CDN and browser, revalidate after
Cache-Control: public, max-age=3600, must-revalidate

# Cacheable by CDN for 1 day, browser for 5 minutes
Cache-Control: public, max-age=300, s-maxage=86400

# Never cache (API responses with user data)
Cache-Control: no-store, no-cache, must-revalidate, private

# Stale-while-revalidate: serve stale for 60s while fetching fresh copy
Cache-Control: public, max-age=300, stale-while-revalidate=60

# ETag for conditional requests (saves bandwidth on 304 Not Modified)
ETag: "v1-abc123"
```

### Cache-Control Decision Tree
1. Contains user-specific data? -> `private` (browser only, not CDN)
2. Sensitive data (auth, PII)? -> `no-store` (never cache)
3. Static asset with hash in filename? -> `max-age=31536000, immutable`
4. API response that changes? -> `max-age=0, s-maxage=60, stale-while-revalidate=30`
5. HTML page? -> `max-age=0, s-maxage=300` (CDN caches, browser always revalidates)

## Invalidation Strategies

### Purge Methods
| Method | Speed | Precision | Use Case |
|--------|-------|-----------|----------|
| TTL expiration | Automatic | Per-resource | Default for most content |
| Explicit purge (API) | Seconds | Single URL or tag | Content update, corrections |
| Surrogate keys/tags | Seconds | Group of URLs | All pages referencing changed data |
| Versioned URLs | Instant | Per-asset | CSS, JS, images with content hash |

### Cache Busting Patterns
```
# Content-hashed filenames (best for static assets)
/static/app.a1b2c3d4.js    → Cache for 1 year (immutable)
/static/styles.e5f6g7h8.css → Cache for 1 year (immutable)

# Query string versioning (works but some CDNs ignore query strings)
/api/config?v=20250115      → Less reliable, avoid if possible

# Path-based versioning (APIs)
/v2/api/users               → Version in URL, cache per-version
```

## CDN Architecture

### Multi-Tier Caching
```
Client → Browser Cache → CDN Edge (POP) → CDN Shield/Origin Shield → Origin Server
```

- **Edge POP**: Closest to user, many locations, small cache capacity
- **Shield/Mid-tier**: Single origin-facing cache that reduces origin load by 90%+
- **Origin**: Your server, ideally handling < 10% of total requests

### Edge Computing
- Run lightweight logic at CDN edge: A/B testing, geo-routing, auth token validation
- Use cases: redirect logic, header manipulation, rate limiting, bot detection
- Platforms: Cloudflare Workers, Fastly Compute, Lambda@Edge
- Constraints: limited compute time (typically 50ms CPU), limited memory, no persistent state

## Stale-While-Revalidate

### How It Works
1. CDN serves cached response to client immediately (even if TTL expired)
2. CDN simultaneously fetches fresh copy from origin in the background
3. Next request gets the fresh copy
4. Result: zero latency penalty for cache misses, eventual freshness

### Configuration
```
# Serve stale content for up to 60 seconds while revalidating
Cache-Control: public, max-age=300, stale-while-revalidate=60

# Also serve stale if origin is down (resilience)
Cache-Control: public, max-age=300, stale-if-error=86400
```

### When to Use
- Content pages where 30-60 seconds of staleness is acceptable
- API responses where freshness is preferred but not critical
- Dashboard data that updates periodically
- NOT for: financial transactions, real-time inventory, authentication responses

## Monitoring Cache Performance

### Key Metrics
| Metric | Target | Investigation if Below |
|--------|--------|----------------------|
| Cache hit ratio | > 90% for static, > 70% for dynamic | Check Vary headers, Cache-Control, cookies |
| Origin request rate | < 10% of total | Shield misconfigured or too many unique URLs |
| Time to first byte (TTFB) | < 100ms at edge | POP distance, cold cache, slow origin |
| Bandwidth savings | > 80% | Low TTLs, high churn content |

### Common Cache Poisoning Pitfalls
- `Vary: *` disables caching entirely (check middleware isn't adding this)
- `Set-Cookie` in cached response serves one user's session to everyone
- Query parameter ordering: `/api?a=1&b=2` vs `/api?b=2&a=1` are different cache keys
- Accept-Encoding: CDN should normalize to prevent duplicate cache entries
