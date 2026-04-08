---
name: ETL Pipelines
description: Extract, transform, load patterns, tools, and best practices
version: "1.0.0"
author: ROOT
tags: [data-analysis, ETL, data-pipeline, extract, transform, load]
platforms: [all]
---

# ETL Pipelines

Design reliable data pipelines that extract, transform, and load data at scale.

## ETL vs ELT

| Approach | Transform Where | Best For | Tools |
|----------|---------------|---------|-------|
| ETL | Before loading (pipeline) | Structured data, compliance | Airflow, Luigi, custom Python |
| ELT | After loading (warehouse) | Large scale, exploratory | dbt, Snowflake, BigQuery |

### Modern Best Practice
- ELT is preferred when using a cloud data warehouse
- Load raw data first (preserves fidelity), transform with SQL in the warehouse
- dbt has become the standard for transformation-as-code

## Extract Patterns

### Source Types
| Source | Method | Considerations |
|--------|--------|---------------|
| REST API | HTTP client with pagination, rate limiting | Handle auth, retries, throttling |
| Database | SQL query or CDC (Change Data Capture) | Incremental vs full extract |
| Files (CSV, JSON) | File system read or cloud storage | Schema validation on read |
| Streaming | Kafka consumer, webhook receiver | Ordering, deduplication |
| Web scraping | HTTP + HTML parsing | Fragile, needs monitoring |

### Incremental Extraction
- Track last successful extract timestamp or ID
- Extract only new/changed records since last run
- Falls back to full extract if incremental metadata is lost
- Reduces load on source system and pipeline runtime

## Transform Patterns

### Common Transformations
1. **Schema mapping**: Rename columns, cast types, flatten nested structures
2. **Deduplication**: Remove duplicate records based on business keys
3. **Enrichment**: Join with reference data (geocoding, currency conversion)
4. **Aggregation**: Summarize to required granularity (daily, weekly)
5. **Validation**: Check data quality rules, quarantine bad records
6. **Derived fields**: Calculate new columns (profit = revenue - cost)

### Data Quality Rules
- Not-null constraints on required fields
- Range checks on numeric fields
- Referential integrity (foreign keys exist in lookup tables)
- Uniqueness constraints on business keys
- Freshness: data should not be older than expected

## Load Patterns

### Loading Strategies
| Strategy | Description | Use When |
|----------|------------|----------|
| Full replace | Drop and recreate table | Small tables, reference data |
| Append | Insert new records | Event/log data, immutable records |
| Upsert (merge) | Insert new, update existing | Dimension tables, mutable records |
| SCD Type 2 | Track historical changes | Need full history of changes |

## Pipeline Orchestration

### Airflow DAG Structure
- One DAG per data domain (users, orders, products)
- Tasks: extract → validate → transform → load → test
- Set retries (3) with exponential backoff
- Alert on failure (Slack, email, PagerDuty)

### Best Practices
- Idempotent tasks: running twice produces same result (safe to retry)
- Parameterize by date: `process_date` parameter enables backfilling
- Separate compute from orchestration (Airflow triggers, Spark processes)
- Monitor: rows processed, execution time, data freshness, error counts
- Test pipelines with sample data before deploying to production

## Observability

- Log row counts at each stage (extract: 10K, after dedup: 9.5K, loaded: 9.5K)
- Track pipeline duration trends (alert if 2x slower than usual)
- Data freshness SLA: define max acceptable age for each table
- Dead letter queue: quarantine bad records instead of failing the entire pipeline
