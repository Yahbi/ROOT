---
name: rest-api
version: "1.0"
description: Connect and consume REST APIs
category: api-integration
tags: [api, rest, http]
triggers: [connect to an API, consume REST endpoint, integrate with API]
---

# REST API Integration

## Purpose
Connect to and consume REST APIs by handling authentication, request construction, response parsing, error handling, and rate limiting for reliable data exchange.

## Steps
1. Review API documentation to understand endpoints, authentication, and rate limits
2. Set up authentication (API key, OAuth, bearer token) using environment variables
3. Build request functions with proper headers, parameters, and payload formatting
4. Implement response parsing with schema validation and error code handling
5. Add retry logic with exponential backoff for transient failures
6. Handle pagination to retrieve complete datasets
7. Test each endpoint and verify data integrity of responses

## Output Format
Working API integration code with authentication configured, request/response examples, error handling coverage, and a summary of available endpoints and their data shapes.
