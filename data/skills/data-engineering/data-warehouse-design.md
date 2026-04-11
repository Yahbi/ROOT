---
name: Data Warehouse Design
description: Design star schemas, slowly changing dimensions, and performance-optimized analytical data models
version: "1.0.0"
author: ROOT
tags: [data-engineering, data-warehouse, star-schema, dimensional-modeling, BI, analytics]
platforms: [all]
difficulty: advanced
---

# Data Warehouse Design

Design analytical data models optimized for business intelligence queries,
reporting, and self-service analytics using dimensional modeling principles.

## Dimensional Modeling Concepts

```
Fact Table: Stores measurements/events (orders, sessions, transactions)
  - Each row = one event or aggregate
  - Contains foreign keys to dimension tables
  - Contains numeric measures (revenue, quantity, duration)

Dimension Table: Stores descriptive attributes (customers, products, dates)
  - Each row = one entity
  - Contains rich descriptive columns for filtering and grouping
  - Connected to fact tables via surrogate keys
```

## Star Schema Design

```sql
-- Fact table: one row per order
CREATE TABLE fact_orders (
    order_key          BIGINT PRIMARY KEY,      -- Surrogate key
    order_id           VARCHAR(50) NOT NULL,     -- Natural key from source
    customer_key       BIGINT REFERENCES dim_customers(customer_key),
    product_key        BIGINT REFERENCES dim_products(product_key),
    date_key           INTEGER REFERENCES dim_date(date_key),
    promotion_key      BIGINT REFERENCES dim_promotions(promotion_key),

    -- Measures (additive — can SUM, AVG, COUNT)
    quantity           INTEGER NOT NULL,
    unit_price         NUMERIC(10, 2) NOT NULL,
    discount_amount    NUMERIC(10, 2) DEFAULT 0,
    total_amount       NUMERIC(10, 2) NOT NULL,
    cost_amount        NUMERIC(10, 2),
    gross_margin       NUMERIC(10, 2) GENERATED ALWAYS AS (total_amount - cost_amount) STORED
);

-- Customer dimension
CREATE TABLE dim_customers (
    customer_key       BIGINT PRIMARY KEY,
    customer_id        VARCHAR(50) NOT NULL,
    full_name          VARCHAR(200),
    email              VARCHAR(200),
    country            VARCHAR(100),
    city               VARCHAR(100),
    customer_segment   VARCHAR(50),  -- 'enterprise', 'smb', 'consumer'
    acquisition_channel VARCHAR(100),
    acquisition_date   DATE,
    -- SCD Type 2 tracking
    effective_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date        DATE NOT NULL DEFAULT '9999-12-31',
    is_current         BOOLEAN NOT NULL DEFAULT TRUE,
    row_hash           VARCHAR(64)   -- Hash of all descriptive columns for change detection
);

-- Date dimension (pre-populated)
CREATE TABLE dim_date (
    date_key           INTEGER PRIMARY KEY,    -- YYYYMMDD format: 20260408
    full_date          DATE NOT NULL,
    year               SMALLINT NOT NULL,
    quarter            SMALLINT NOT NULL,
    month              SMALLINT NOT NULL,
    month_name         VARCHAR(20) NOT NULL,
    week_of_year       SMALLINT NOT NULL,
    day_of_month       SMALLINT NOT NULL,
    day_of_week        SMALLINT NOT NULL,
    day_name           VARCHAR(20) NOT NULL,
    is_weekend         BOOLEAN NOT NULL,
    is_holiday         BOOLEAN NOT NULL,
    fiscal_year        SMALLINT,
    fiscal_quarter     SMALLINT
);
```

## Slowly Changing Dimensions (SCD)

### SCD Type 1: Overwrite (No History)
```sql
-- Simple update — lose historical value
UPDATE dim_customers
SET email = 'newemail@example.com',
    row_hash = MD5('newemail@example.com' || full_name || country)
WHERE customer_id = 'CUST123' AND is_current = TRUE;
-- Use when: history doesn't matter (e.g., phone number typo correction)
```

### SCD Type 2: Add Row (Full History)
```sql
-- Expire old row, insert new row
BEGIN;
  -- Expire current record
  UPDATE dim_customers
  SET expiry_date = CURRENT_DATE - 1, is_current = FALSE
  WHERE customer_id = 'CUST123' AND is_current = TRUE;

  -- Insert new current record
  INSERT INTO dim_customers
  (customer_id, full_name, email, country, customer_segment,
   acquisition_channel, acquisition_date, effective_date, expiry_date, is_current)
  VALUES
  ('CUST123', 'Jane Doe', 'jane@newcompany.com', 'US', 'enterprise',
   'partner_referral', '2024-01-15', CURRENT_DATE, '9999-12-31', TRUE);
COMMIT;

-- Query at a point in time:
SELECT * FROM dim_customers
WHERE customer_id = 'CUST123'
  AND effective_date <= '2025-06-01'
  AND expiry_date >= '2025-06-01';
```

## Aggregate Tables and Materialized Views

```sql
-- Pre-aggregate common query patterns for BI performance
CREATE MATERIALIZED VIEW agg_daily_revenue AS
SELECT
    d.full_date,
    d.year,
    d.month,
    d.month_name,
    c.country,
    c.customer_segment,
    p.category AS product_category,
    COUNT(DISTINCT fo.order_key) AS order_count,
    COUNT(DISTINCT fo.customer_key) AS unique_customers,
    SUM(fo.total_amount) AS revenue,
    SUM(fo.gross_margin) AS gross_margin,
    AVG(fo.total_amount) AS avg_order_value
FROM fact_orders fo
JOIN dim_date d ON d.date_key = fo.date_key
JOIN dim_customers c ON c.customer_key = fo.customer_key AND c.is_current = TRUE
JOIN dim_products p ON p.product_key = fo.product_key AND p.is_current = TRUE
GROUP BY 1, 2, 3, 4, 5, 6, 7;

CREATE UNIQUE INDEX ON agg_daily_revenue (full_date, country, customer_segment, product_category);

-- Refresh on schedule:
REFRESH MATERIALIZED VIEW CONCURRENTLY agg_daily_revenue;
```

## dbt Dimensional Models

```sql
-- models/marts/core/dim_customers.sql
{{ config(
    materialized='table',
    sort=['is_current', 'customer_id'],
    dist='customer_id'
) }}

WITH source AS (
    SELECT * FROM {{ ref('stg_customers') }}
),

scd2 AS (
    SELECT
        {{ dbt_utils.surrogate_key(['customer_id', 'effective_date']) }} AS customer_key,
        customer_id,
        full_name,
        email,
        country,
        customer_segment,
        effective_date,
        COALESCE(
            LEAD(effective_date) OVER (PARTITION BY customer_id ORDER BY effective_date) - 1,
            '9999-12-31'::date
        ) AS expiry_date,
        CASE WHEN LEAD(effective_date) OVER (PARTITION BY customer_id ORDER BY effective_date) IS NULL
             THEN TRUE ELSE FALSE END AS is_current,
        MD5(email || COALESCE(country, '') || COALESCE(customer_segment, '')) AS row_hash
    FROM source
)

SELECT * FROM scd2
```

## Query Optimization for Analytics

```sql
-- Use ROLLUP for hierarchical aggregations
SELECT
    COALESCE(country, 'TOTAL') AS country,
    COALESCE(customer_segment, 'ALL') AS segment,
    SUM(revenue) AS revenue
FROM agg_daily_revenue
WHERE year = 2026
GROUP BY ROLLUP(country, customer_segment)
ORDER BY 1, 2;

-- Window functions for running totals and rankings
SELECT
    full_date,
    revenue,
    SUM(revenue) OVER (ORDER BY full_date ROWS UNBOUNDED PRECEDING) AS cumulative_revenue,
    revenue / LAG(revenue, 7) OVER (ORDER BY full_date) - 1 AS wow_growth,
    RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS rank_in_month
FROM agg_daily_revenue
WHERE year = 2026 AND country = 'US';
```

## Performance Design Decisions

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| Fact table grain | Lowest level of detail possible | Aggregation loses nothing; rollup gains flexibility |
| Surrogate keys | Always use — integers, not GUIDs | Smaller, faster joins, handles source system changes |
| Denormalization | Denormalize into wide dimension tables | Fewer joins = faster BI queries |
| Partitioning | Partition facts by date range | Most queries filter by date |
| Clustering | Cluster on frequent filter columns | Reduce data scanned per query |
| Indexes | Index on date_key + common join keys | Analytics queries are mostly reads |
