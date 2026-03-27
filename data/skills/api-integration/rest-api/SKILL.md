---
name: rest-api
description: Integrate with REST APIs including auth, pagination, and error handling
version: 1.0.0
author: ROOT
tags: [api, rest, integration, http]
platforms: [darwin, linux, win32]
---

# REST API Integration

## When to Use
When ROOT needs to communicate with external services via HTTP APIs.

## Procedure
1. **Read Docs**: Understand endpoints, auth, rate limits
2. **Authenticate**: API key, OAuth2, Bearer token
3. **Build Client**: Configure httpx with base URL, headers, timeout
4. **Make Requests**: GET/POST/PUT/DELETE with proper payloads
5. **Handle Errors**: Retry on 429/5xx, fail on 4xx
6. **Parse Response**: Validate JSON schema, extract data

## Error Handling
- 429 Too Many Requests: exponential backoff
- 500-503: retry up to 3 times with delay
- 401: refresh token, retry once
- 404: resource not found, don't retry
