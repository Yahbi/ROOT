---
name: data-pipeline
description: Build data pipelines to collect, clean, and analyze structured data
version: 1.0.0
author: ROOT
tags: [data, pipeline, etl, analysis]
platforms: [darwin, linux, win32]
---

# Data Pipeline Construction

## When to Use
When ROOT needs to process data from any source into actionable insights.

## Procedure
1. **Identify Source**: Determine data origin (API, file, database, web scrape)
2. **Extract**: Pull raw data using httpx, sqlite3, or file I/O
3. **Transform**: Clean, normalize, deduplicate, type-cast
4. **Load**: Store in SQLite or memory for analysis
5. **Validate**: Check row counts, null rates, type consistency
6. **Analyze**: Apply statistical methods, find patterns

## Best Practices
- Always validate data quality before analysis
- Use streaming for large datasets (>1GB)
- Cache intermediate results for reprocessing
- Log every transformation step for auditability

## Common Pitfalls
- Assuming data types without checking
- Not handling encoding issues (UTF-8 vs Latin-1)
- Ignoring null values in aggregations
