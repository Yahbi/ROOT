---
name: Data Warehouse Modeling
description: Dimensional modeling, star and snowflake schemas, slowly changing dimensions, and DWH best practices
category: data-engineering
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [data-engineering, data-warehouse, dimensional-modeling, star-schema, slowly-changing-dimensions, dbt]
platforms: [all]
---

# Data Warehouse Modeling

Design analytical data models that are intuitive for business users, performant for queries, and maintainable as the business evolves.

## Dimensional Modeling Fundamentals

### Core Components
- **Fact table**: Records business events/measurements — orders, clicks, payments, logins
- **Dimension table**: Describes the "who, what, where, when, why" of facts — customer, product, date, location
- **Grain**: The level of detail represented by a single fact row — one row per order line, per session, per daily balance
- **Measure**: Numeric value in a fact table that can be aggregated — revenue, quantity, duration

### Choosing the Grain
The grain is the most critical decision in dimensional modeling:
- Too coarse: can't answer detailed questions
- Too fine: poor query performance, storage explosion
- Rule: define the grain, then identify dimensions that apply at that grain
- Example grains: "one row per customer per day", "one row per order line item", "one row per page view"

## Star Schema

```
                    dim_date
                       │
dim_customer ──── fact_orders ──── dim_product
                       │
                  dim_geography
```

### Fact Table Design
```sql
CREATE TABLE fact_orders (
    -- Surrogate keys (integer FKs to dimension tables)
    order_date_key      INTEGER     NOT NULL REFERENCES dim_date(date_key),
    customer_key        INTEGER     NOT NULL REFERENCES dim_customer(customer_key),
    product_key         INTEGER     NOT NULL REFERENCES dim_product(product_key),
    geography_key       INTEGER     NOT NULL REFERENCES dim_geography(geography_key),

    -- Degenerate dimension (source system key, no separate dim table needed)
    order_id            VARCHAR(50) NOT NULL,

    -- Measures
    quantity            INTEGER     NOT NULL,
    unit_price          DECIMAL(10,2) NOT NULL,
    discount_amount     DECIMAL(10,2) DEFAULT 0,
    gross_revenue       DECIMAL(10,2) NOT NULL,
    net_revenue         DECIMAL(10,2) NOT NULL,

    -- Audit
    etl_loaded_at       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
```

### Dimension Table Design
```sql
CREATE TABLE dim_customer (
    customer_key        INTEGER     PRIMARY KEY,    -- Surrogate key
    customer_id         VARCHAR(50) NOT NULL,       -- Natural/source key
    full_name           VARCHAR(200),
    email               VARCHAR(200),
    segment             VARCHAR(50),
    city                VARCHAR(100),
    country             CHAR(2),
    -- SCD Type 2 fields
    valid_from          DATE        NOT NULL,
    valid_to            DATE,                       -- NULL = current record
    is_current          BOOLEAN     DEFAULT TRUE,
    -- Audit
    created_at          TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
```

## Slowly Changing Dimensions (SCD)

### SCD Type 1 — Overwrite
- Simply update the row; no history retained
- When to use: corrections (fixing typos), attributes where history doesn't matter
- Simple but destroys historical accuracy of past fact rows

### SCD Type 2 — Add New Row (Most Common)
```sql
-- When customer changes their email:
-- 1. Close the old record
UPDATE dim_customer
SET valid_to = CURRENT_DATE - 1, is_current = FALSE
WHERE customer_id = 'C123' AND is_current = TRUE;

-- 2. Insert new record
INSERT INTO dim_customer (customer_key, customer_id, email, valid_from, is_current)
VALUES (nextval('customer_key_seq'), 'C123', 'new@email.com', CURRENT_DATE, TRUE);
```
- Full history preserved; fact rows point to correct historical dimension state
- Tradeoff: table grows with each change; queries need `is_current = TRUE` filter

### SCD Type 3 — Add Column
- Adds a `previous_value` column alongside the current value
- Only tracks one level of history
- Useful when business needs to know "current vs previous" without full history

### SCD Type 6 — Hybrid (1+2+3)
- Adds current value, previous value, and version rows
- Best of all approaches; most complex to implement

## Date Dimension

```sql
-- Pre-populated date dimension (generate for 20+ years)
CREATE TABLE dim_date (
    date_key            INTEGER     PRIMARY KEY,    -- YYYYMMDD format: 20240115
    full_date           DATE        NOT NULL UNIQUE,
    day_of_week         SMALLINT,                   -- 1=Monday, 7=Sunday
    day_name            VARCHAR(10),
    day_of_month        SMALLINT,
    day_of_year         SMALLINT,
    week_of_year        SMALLINT,
    month_number        SMALLINT,
    month_name          VARCHAR(10),
    quarter             SMALLINT,
    year                SMALLINT,
    is_weekend          BOOLEAN,
    is_holiday          BOOLEAN,
    fiscal_quarter      SMALLINT,
    fiscal_year         SMALLINT
);
```

## Fact Table Types

| Type | Description | Example | Key Design |
|------|-------------|---------|------------|
| **Transaction** | One row per discrete event | Order placed, payment made | Finest grain; additive measures |
| **Snapshot** | State at regular intervals | Daily account balance | Periodic; additive + semi-additive |
| **Accumulating** | Updates as process progresses | Order fulfillment lifecycle | Multiple date FKs; lag measures |

### Accumulating Snapshot Example
```sql
CREATE TABLE fact_order_fulfillment (
    order_key               INTEGER,
    -- Multiple date FKs — each updated as stage completes
    order_placed_date_key   INTEGER REFERENCES dim_date(date_key),
    payment_date_key        INTEGER REFERENCES dim_date(date_key),
    shipped_date_key        INTEGER REFERENCES dim_date(date_key),
    delivered_date_key      INTEGER REFERENCES dim_date(date_key),
    -- Lag measures in days
    days_to_payment         INTEGER,
    days_to_ship            INTEGER,
    days_to_deliver         INTEGER
);
```

## Modeling with dbt

### Model Layers
```
staging/           # 1:1 with source tables, light renaming + casting
  └── stg_orders.sql
intermediate/      # Business logic, joins, grain transformations
  └── int_orders_enriched.sql
marts/             # Final dimensional tables for consumption
  ├── dim_customer.sql
  ├── dim_product.sql
  └── fct_orders.sql
```

### Surrogate Key Generation
```sql
-- dbt: generate surrogate key from natural key
SELECT
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'valid_from']) }} AS customer_key,
    customer_id,
    email,
    valid_from,
    valid_to,
    is_current
FROM {{ ref('int_customer_scd2') }}
```

## Performance Optimization

| Technique | Warehouse | Impact |
|-----------|-----------|--------|
| Clustering keys | BigQuery, Snowflake | Eliminate partition scans |
| Sort keys + distribution keys | Redshift | Reduce data movement in joins |
| Materialized views | All | Pre-compute expensive aggregates |
| Columnar storage | All | 3-10x faster analytical reads |
| Pre-aggregate grain | Model design | Reduce query compute |

## Naming Conventions

- Fact tables: `fct_<business_process>` — `fct_orders`, `fct_sessions`, `fct_payments`
- Dimension tables: `dim_<entity>` — `dim_customer`, `dim_product`, `dim_date`
- Staging: `stg_<source>__<table>` — `stg_postgres__orders`
- Intermediate: `int_<description>` — `int_orders_with_returns`
- Measures: snake_case noun — `gross_revenue`, `session_duration_seconds`
- Keys: `<table>_key` for surrogate, `<table>_id` for natural key
