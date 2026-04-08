---
name: Data Pipeline Testing
description: Test ETL pipelines, data transformations, and data quality assertions with pytest and dbt tests
version: "1.0.0"
author: ROOT
tags: [data-engineering, testing, pytest, dbt, unit-tests, integration-tests]
platforms: [all]
difficulty: intermediate
---

# Data Pipeline Testing

Data pipelines fail silently — wrong transformations produce plausible-looking wrong answers.
Test your transformations, schemas, and business rules the same way you test application code.

## Testing Pyramid for Data

```
                /\
               /  \   E2E Tests (full pipeline on real data)
              /    \
             /------\  Integration Tests (multiple transforms chained)
            /        \
           /----------\  Unit Tests (individual transform functions)
          /            \
         /--------------\  dbt Schema Tests (column constraints)
```

## Unit Testing Transformations

```python
import pytest
import pandas as pd
from datetime import datetime

# Import the function under test
from transforms.orders import clean_orders, compute_order_metrics

class TestOrderTransformations:
    @pytest.fixture
    def raw_orders(self):
        """Sample raw data that mirrors real source schema."""
        return pd.DataFrame({
            "order_id": ["O001", "O002", "O003", "O001"],  # O001 is duplicate
            "customer_id": ["C1", "C2", None, "C1"],
            "total_amount": [100.0, -50.0, 200.0, 100.0],  # -50 is invalid
            "status": ["COMPLETED", "completed", "PENDING", "COMPLETED"],  # mixed case
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-01"]
        })

    def test_cleans_status_case(self, raw_orders):
        result = clean_orders(raw_orders)
        assert result["status"].str.islower().all(), "Status should be lowercase"

    def test_removes_duplicates(self, raw_orders):
        result = clean_orders(raw_orders)
        assert result["order_id"].nunique() == result["order_id"].count(), "Duplicates not removed"

    def test_removes_negative_amounts(self, raw_orders):
        result = clean_orders(raw_orders)
        assert (result["total_amount"] >= 0).all(), "Negative amounts should be removed"

    def test_drops_null_customer_ids(self, raw_orders):
        result = clean_orders(raw_orders)
        assert result["customer_id"].isnull().sum() == 0, "Null customer_ids should be removed"

    def test_preserves_valid_records(self, raw_orders):
        result = clean_orders(raw_orders)
        assert "O002" not in result["order_id"].values, "Negative amount order should be excluded"
        assert "O001" in result["order_id"].values, "Valid order should be preserved"
        assert len(result) == 1, "Only 1 valid unique record expected"

    def test_schema_output_columns(self, raw_orders):
        result = clean_orders(raw_orders)
        required_cols = {"order_id", "customer_id", "total_amount", "status", "created_at"}
        assert required_cols.issubset(set(result.columns))

class TestOrderMetrics:
    def test_compute_customer_ltv(self):
        orders = pd.DataFrame({
            "customer_id": ["C1", "C1", "C2"],
            "total_amount": [100, 200, 150]
        })
        result = compute_order_metrics(orders)
        assert result.loc[result["customer_id"] == "C1", "ltv"].iloc[0] == 300
        assert result.loc[result["customer_id"] == "C2", "ltv"].iloc[0] == 150
```

## dbt Schema Tests

```yaml
# models/staging/schema.yml
version: 2

models:
  - name: stg_orders
    description: Cleaned orders from order management system
    columns:
      - name: order_id
        description: Primary key — unique order identifier
        tests:
          - unique
          - not_null

      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('stg_customers')
              field: customer_id

      - name: total_amount
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: ">= 0"
              name: total_amount_non_negative

      - name: status
        tests:
          - accepted_values:
              values: ['pending', 'completed', 'cancelled', 'refunded']

      - name: created_at
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: ">= '2020-01-01'"
              name: created_at_reasonable_date
```

```sql
-- tests/assert_no_revenue_decrease.sql
-- Custom dbt singular test: revenue today should not be less than 50% of yesterday
WITH today AS (
    SELECT SUM(total_amount) AS revenue
    FROM {{ ref('fact_orders') }}
    WHERE created_at >= CURRENT_DATE
),
yesterday AS (
    SELECT SUM(total_amount) AS revenue
    FROM {{ ref('fact_orders') }}
    WHERE created_at >= CURRENT_DATE - 1 AND created_at < CURRENT_DATE
)
SELECT 1
FROM today, yesterday
WHERE today.revenue < yesterday.revenue * 0.5
-- Returns rows if test FAILS (dbt convention)
```

## Integration Testing

```python
class TestOrderPipelineIntegration:
    @pytest.fixture(scope="class")
    def pipeline_output(self, tmp_path_factory):
        """Run the full orders pipeline against test database."""
        tmp = tmp_path_factory.mktemp("pipeline_test")
        test_db = setup_test_database(seed_data="tests/fixtures/orders_seed.sql")

        # Run full pipeline
        from pipelines.orders_pipeline import run_orders_pipeline
        result = run_orders_pipeline(
            source_db=test_db,
            output_path=str(tmp / "output"),
            test_mode=True
        )
        return result

    def test_pipeline_completes_successfully(self, pipeline_output):
        assert pipeline_output["status"] == "success"
        assert pipeline_output["errors"] == []

    def test_output_row_count_reasonable(self, pipeline_output):
        assert 100 <= pipeline_output["rows_loaded"] <= 10000

    def test_no_data_loss(self, pipeline_output):
        """Verify we didn't drop valid records."""
        source_count = get_source_row_count()
        # Allow for deduplication (max 5% loss)
        assert pipeline_output["rows_loaded"] >= source_count * 0.95

    def test_aggregate_metrics_match(self, pipeline_output, test_db):
        """Verify aggregates match source data."""
        expected_revenue = test_db.execute("SELECT SUM(amount) FROM orders").scalar()
        actual_revenue = get_output_metric(pipeline_output, "total_revenue")
        assert abs(actual_revenue - expected_revenue) / expected_revenue < 0.001  # < 0.1% tolerance
```

## Property-Based Testing with Hypothesis

```python
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.pandas import data_frames, column

@given(data_frames(columns=[
    column("order_id", elements=st.text(min_size=1, max_size=50)),
    column("customer_id", elements=st.text(min_size=1, max_size=50)),
    column("total_amount", elements=st.floats(min_value=0, max_value=1e6)),
    column("status", elements=st.sampled_from(["pending", "completed", "cancelled"])),
]))
@settings(max_examples=200)
def test_clean_orders_never_crashes(df):
    """clean_orders should handle any valid input without raising."""
    result = clean_orders(df)
    assert isinstance(result, pd.DataFrame)
    # Verify output is always a subset of input
    assert len(result) <= len(df)
    # Verify no negative amounts in output
    if len(result) > 0:
        assert (result["total_amount"] >= 0).all()
```

## Performance Testing

```python
import time
import pytest

@pytest.mark.slow
def test_pipeline_completes_within_sla(large_dataset_fixture):
    """Pipeline must complete within 10 minutes for 1M rows."""
    start = time.time()
    result = run_pipeline(large_dataset_fixture)  # 1M row fixture
    elapsed = time.time() - start

    assert result["status"] == "success"
    assert elapsed < 600, f"Pipeline took {elapsed:.0f}s, SLA is 600s"
    assert result["rows_per_second"] > 10000, "Must process > 10k rows/sec"
```

## CI/CD Integration

```yaml
# .github/workflows/data-tests.yml
name: Data Pipeline Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --tb=short -x
          pytest tests/integration/ -v --tb=short

  dbt-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Run dbt tests
        run: |
          dbt deps
          dbt run --target ci
          dbt test --target ci
          dbt source freshness
```
