---
name: web-scraping
version: "1.0"
description: Extract data from websites
category: automation
tags: [scraping, web, extraction]
triggers: [scrape a website, extract web data, crawl pages for data]
---

# Web Scraping

## Purpose
Extract structured data from websites by parsing HTML, handling pagination, managing rate limits, and outputting clean datasets ready for analysis or storage.

## Steps
1. Identify target URLs and the data fields to extract
2. Inspect page structure (HTML elements, CSS selectors, API endpoints)
3. Choose the scraping approach (static HTML parsing, browser automation, or API reverse-engineering)
4. Implement the scraper with proper selectors and data extraction logic
5. Handle pagination, dynamic loading, and anti-bot measures (rate limiting, headers, retries)
6. Clean and validate extracted data (type casting, deduplication, null handling)
7. Export results to the desired format (CSV, JSON, database)

## Output Format
A structured dataset in the requested format with a summary of pages scraped, records extracted, and any errors or skipped entries.
