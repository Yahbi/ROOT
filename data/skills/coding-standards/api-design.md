---
name: API Design
description: REST best practices, versioning, pagination, error handling, and API conventions
version: "1.0.0"
author: ROOT
tags: [coding-standards, api, REST, design, best-practices]
platforms: [all]
---

# API Design

Design consistent, intuitive, and maintainable REST APIs.

## Resource Naming

### Conventions
- Use nouns, not verbs: `/users` not `/getUsers`
- Use plural: `/users`, `/orders`, `/products`
- Use kebab-case: `/user-profiles` not `/userProfiles`
- Nest for relationships: `/users/{id}/orders` (orders belonging to a user)
- Maximum 3 levels of nesting (deeper = use query parameters or separate endpoints)

### Resource Hierarchy
```
GET    /api/v1/users              # List users
POST   /api/v1/users              # Create user
GET    /api/v1/users/{id}         # Get specific user
PUT    /api/v1/users/{id}         # Replace user
PATCH  /api/v1/users/{id}         # Partial update
DELETE /api/v1/users/{id}         # Delete user
GET    /api/v1/users/{id}/orders  # List user's orders
```

## Pagination

### Cursor-Based (preferred)
```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTAwfQ==",
    "has_more": true
  }
}
```
- Consistent performance regardless of page depth
- Stable results when data changes between requests
- Use opaque cursors (base64-encoded) — clients should not parse them

### Offset-Based (simple but limited)
```
GET /api/v1/users?offset=20&limit=10
```
- Familiar but degrades with large offsets
- Results can shift when data is added/removed between pages

### Best Practices
- Default page size: 20, max: 100 (prevent accidental resource exhaustion)
- Always return total count or has_more indicator
- Include pagination metadata in response body (not just headers)

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request was invalid.",
    "details": [
      {"field": "email", "message": "Must be a valid email address"},
      {"field": "age", "message": "Must be a positive integer"}
    ]
  }
}
```

### HTTP Status Code Usage
| Code | Meaning | When to Use |
|------|---------|------------|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST that creates a resource |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid input, validation errors |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate creation, state conflict |
| 422 | Unprocessable | Syntactically valid but semantically wrong |
| 429 | Too Many Requests | Rate limited |
| 500 | Server Error | Unexpected server-side failure |

## Versioning

### URL Versioning (recommended)
- `/api/v1/users` — simple, explicit, cacheable
- Increment major version only for breaking changes
- Support previous version for minimum 12 months after new version launch

### What's a Breaking Change
- Removing a field from response
- Changing field type (string to integer)
- Removing an endpoint
- Changing authentication mechanism
- Making optional parameter required

### What's NOT a Breaking Change
- Adding a new field to response
- Adding a new endpoint
- Adding a new optional parameter

## Design Checklist

- [ ] Resources use plural nouns with consistent naming
- [ ] Pagination implemented for all list endpoints
- [ ] Error responses follow consistent format with machine-readable codes
- [ ] API versioned with clear deprecation policy
- [ ] Request/response examples documented for every endpoint
- [ ] Rate limits defined and communicated via headers
- [ ] Idempotent: POST with idempotency key, PUT is naturally idempotent
