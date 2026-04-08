---
name: Data Quality Framework
description: Establish dimensions, rules, validation pipelines, and metrics for data quality management
category: data-engineering
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [data-engineering, data-quality, validation, great-expectations, dbt-tests, observability]
platforms: [all]
---

# Data Quality Framework

Systematically measure, monitor, and improve the trustworthiness of data across the organization.

## The Six Dimensions of Data Quality

| Dimension | Definition | Example Issue | Measurement |
|-----------|-----------|---------------|-------------|
| **Completeness** | Required fields are populated | `email` is null for 15% of users | `COUNT(col IS NULL) / COUNT(*)` |
| **Accuracy** | Values reflect reality | Zip code doesn't match city | Cross-reference with authoritative source |
| **Consistency** | Same entity has same values across systems | CRM customer ID ≠ DWH customer ID | Join-based reconciliation |
| **Timeliness** | Data is current for its use case | Daily sales data arrives 2 days late | `MAX(updated_at)` vs SLA threshold |
| **Uniqueness** | No unintended duplicates | Same order appears twice in orders table | `COUNT(*) - COUNT(DISTINCT id)` |
| **Validity** | Values conform to defined rules | Date of birth is in the future | Rule-based assertion on column values |

## Rule Classification

### Criticality Levels
- **P0 — Block**: Pipeline stops, alert immediately. Example: primary key uniqueness, non-null foreign keys
- **P1 — Warn**: Pipeline continues, ticket created. Example: referential integrity gaps < 1%
- **P2 — Monitor**: Dashboard metric, weekly review. Example: address format inconsistencies

### Rule Categories
```yaml
# Example rule definitions
rules:
  - id: orders.pk_unique
    dimension: uniqueness
    sql: SELECT COUNT(*) - COUNT(DISTINCT order_id) AS duplicates FROM orders
    threshold: 0
    criticality: P0

  - id: users.email_completeness
    dimension: completeness
    sql: SELECT COUNT(*) FILTER (WHERE email IS NULL) * 1.0 / COUNT(*) AS null_rate FROM users
    threshold: 0.02   # max 2% null
    criticality: P1

  - id: orders.amount_validity
    dimension: validity
    sql: SELECT COUNT(*) FILTER (WHERE amount < 0) AS negative_amounts FROM orders
    threshold: 0
    criticality: P0
```

## Implementation with Great Expectations

### Expectation Suite Setup
```python
import great_expectations as gx

context = gx.get_context()
suite = context.add_expectation_suite("orders_suite")

validator = context.get_validator(
    datasource_name="postgres_dwh",
    data_asset_name="orders",
    expectation_suite_name="orders_suite",
)

# Completeness
validator.expect_column_values_to_not_be_null("order_id")
validator.expect_column_values_to_not_be_null("user_id")

# Validity
validator.expect_column_values_to_be_between("amount", min_value=0, max_value=1_000_000)
validator.expect_column_values_to_match_strftime_format("order_date", "%Y-%m-%d")

# Uniqueness
validator.expect_column_values_to_be_unique("order_id")

# Set membership
validator.expect_column_values_to_be_in_set("status", ["pending", "paid", "refunded", "cancelled"])

validator.save_expectation_suite(discard_failed_expectations=False)
```

### Checkpoint Integration (Airflow)
```python
from great_expectations.checkpoint import Checkpoint

checkpoint = Checkpoint(
    name="orders_checkpoint",
    config_version=1.0,
    template_name=None,
    run_name_template="%Y%m%d_%H%M%S",
    expectation_suite_name="orders_suite",
    action_list=[
        {"name": "store_validation_result", "action": {"class_name": "StoreValidationResultAction"}},
        {"name": "send_slack_notification", "action": {"class_name": "SlackNotificationAction",
                                                        "slack_webhook": "https://hooks.slack.com/..."}},
    ],
)
result = checkpoint.run()
if not result.success:
    raise AirflowFailException("Data quality checks failed")
```

## dbt Tests

### Built-in Tests (schema.yml)
```yaml
models:
  - name: orders
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: status
        tests:
          - accepted_values:
              values: ["pending", "paid", "refunded", "cancelled"]
      - name: user_id
        tests:
          - relationships:
              to: ref('users')
              field: user_id
```

### Custom Generic Test
```sql
-- tests/generic/assert_non_negative.sql
{% test assert_non_negative(model, column_name) %}
SELECT {{ column_name }}
FROM {{ model }}
WHERE {{ column_name }} < 0
{% endtest %}
```

## Data Quality Scoring

### Overall DQ Score Formula
```
DQ Score = Σ (dimension_score × dimension_weight)

Weights (example):
  Completeness  25%
  Uniqueness    25%
  Validity      20%
  Consistency   15%
  Timeliness    10%
  Accuracy       5%
```

### Tracking Over Time
- Store validation results in a `dq_results` table: `(table, rule_id, run_date, passed, failed_count, score)`
- Build trend dashboards: score per table per day, dimension breakdown, worst-offending tables
- Set minimum acceptable score per table (e.g., critical tables must score > 95%)

## Data Quality SLAs

| Asset | Completeness SLA | Freshness SLA | Owner |
|-------|-----------------|---------------|-------|
| `orders` | > 99% | < 4 hours | Data Engineering |
| `users` | > 98% | < 24 hours | Backend team |
| `revenue_summary` | 100% | < 1 hour | Finance |

## Incident Response for DQ Issues

1. **Detect**: Automated rule failure triggers alert
2. **Assess**: How many records affected? Which downstream consumers?
3. **Contain**: Mark affected records with `is_quarantined = true`; notify downstream teams
4. **Root Cause**: Was it upstream source, pipeline transformation, or schema change?
5. **Remediate**: Fix or backfill affected data; re-run validation
6. **Prevent**: Add the missed rule to the expectation suite; document in data catalog

## Metadata & Lineage

- Tag every table in the data catalog with its DQ score and last validated timestamp
- Document upstream sources and downstream consumers for impact analysis
- When a quality issue is detected, auto-generate impact report: which dashboards/reports are affected
