---
name: web-scraping
description: Extract data from websites using httpx and HTML parsing
version: 1.0.0
author: ROOT
tags: [web, scraping, data, extraction]
platforms: [darwin, linux, win32]
---

# Web Scraping

## When to Use
When ROOT needs to extract structured data from websites.

## Procedure
1. **Analyze Target**: Inspect HTML structure, identify data elements
2. **Build Request**: Set headers (User-Agent), handle cookies, respect robots.txt
3. **Fetch Page**: Use httpx with timeout and retry logic
4. **Parse HTML**: Extract data using regex or string operations
5. **Handle Pagination**: Follow next-page links or offset parameters
6. **Store Results**: Save to memory or file system

## Safety Rules
- Always set reasonable timeouts (15-30s)
- Respect robots.txt and rate limits
- Use delays between requests (1-3s)
- Never scrape personal data without authorization
