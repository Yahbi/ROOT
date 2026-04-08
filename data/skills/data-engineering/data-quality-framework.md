---
name: Data Quality Framework
description: Implement comprehensive data quality checks, validation rules, and monitoring for data pipelines
version: "1.0.0"
author: ROOT
tags: [data-engineering, data-quality, validation, great-expectations, testing]
platforms: [all]
difficulty: intermediate
---

# Data Quality Framework

Bad data is worse than no data. Enforce quality gates at every stage of your pipeline
to prevent corrupt or incomplete data from reaching analytics and ML models.

## Data Quality Dimensions

| Dimension | Definition | Example Issue |
|-----------|-----------|---------------|
| Completeness | No missing required values | customer_id is NULL |
| Accuracy | Values are correct | negative revenue |
| Consistency | Same value across systems | user count differs by 10% |
| Timeliness | Data arrives on schedule | pipeline 3 hours late |
| Uniqueness | No duplicates | same order_id twice |
| Validity | Values within allowed range/format | invalid email format |
| Referential Integrity | Foreign keys exist in parent table | order has non-existent customer_id |

## Great Expectations Implementation

```python
import great_expectations as gx

def build_expectation_suite(df, suite_name: str):
    context = gx.get_context()
    suite = context.add_expectation_suite(suite_name)
    validator = context.get_validator(
        batch_request=..., expectation_suite_name=suite_name
    )

    # Completeness
    validator.expect_column_values_to_not_be_null("order_id")
    validator.expect_column_values_to_not_be_null("customer_id")

    # Uniqueness
    validator.expect_column_values_to_be_unique("order_id")

    # Validity
    validator.expect_column_values_to_be_between("total_amount", min_value=0, max_value=100000)
    validator.expect_column_values_to_match_regex(
        "email", r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    # Volume check — detect pipeline failures
    validator.expect_table_row_count_to_be_between(min_value=100, max_value=1000000)

    # Freshness
    validator.expect_column_max_to_be_between(
        "created_at",
        min_value=str(datetime.now() - timedelta(hours=25)),
        max_value=str(datetime.now())
    )

    validator.save_expectation_suite()
    return suite

def run_quality_checks(df: pd.DataFrame, suite_name: str) -> dict:
    results = context.run_validation_operator(
        "action_list_operator",
        assets_to_validate=[batch],
        expectation_suite_name=suite_name
    )
    return {
        "success": results["success"],
        "statistics": results["run_results"]["statistics"],
        "failed_expectations": [r for r in results["results"] if not r["success"]]
    }
```

## Custom Validation Rules

```python
class DataQualityChecker:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.errors = []
        self.warnings = []

    def check_completeness(self, required_columns: list, max_null_rate: float = 0.01):
        for col in required_columns:
            null_rate = self.df[col].isnull().mean()
            if null_rate > max_null_rate:
                self.errors.append({
                    "rule": "completeness",
                    "column": col,
                    "null_rate": null_rate,
                    "threshold": max_null_rate
                })
        return self

    def check_uniqueness(self, key_columns: list):
        dup_rate = self.df.duplicated(subset=key_columns).mean()
        if dup_rate > 0:
            self.errors.append({
                "rule": "uniqueness",
                "columns": key_columns,
                "duplicate_rate": dup_rate
            })
        return self

    def check_referential_integrity(self, column: str, valid_values: set):
        invalid_mask = ~self.df[column].isin(valid_values)
        if invalid_mask.any():
            self.errors.append({
                "rule": "referential_integrity",
                "column": column,
                "invalid_count": invalid_mask.sum(),
                "examples": self.df[column][invalid_mask].head(5).tolist()
            })
        return self

    def check_distribution(self, column: str, expected_mean: float, tolerance: float = 0.2):
        actual_mean = self.df[column].mean()
        deviation = abs(actual_mean - expected_mean) / expected_mean
        if deviation > tolerance:
            self.warnings.append({
                "rule": "distribution",
                "column": column,
                "expected_mean": expected_mean,
                "actual_mean": actual_mean,
                "deviation_pct": deviation * 100
            })
        return self

    def validate(self) -> dict:
        return {
            "passed": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "row_count": len(self.df)
        }
```

## Schema Validation

```python
from pydantic import BaseModel, validator, Field
from typing import Optional

class OrderRecord(BaseModel):
    order_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    total_amount: float = Field(..., ge=0, le=1_000_000)
    status: str = Field(..., regex="^(pending|completed|cancelled|refunded)$")
    created_at: datetime
    email: Optional[str] = None

    @validator("email")
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v

def validate_batch(records: list) -> dict:
    valid, invalid = [], []
    for record in records:
        try:
            valid.append(OrderRecord(**record).dict())
        except Exception as e:
            invalid.append({"record": record, "error": str(e)})
    return {"valid": valid, "invalid": invalid, "invalid_rate": len(invalid) / len(records)}
```

## Anomaly Detection in Data Quality

```python
def detect_volume_anomalies(daily_counts: list, today_count: int, z_threshold: float = 3.0) -> dict:
    """Alert if today's row count is unusually high or low."""
    if len(daily_counts) < 7:
        return {"anomaly": False, "reason": "insufficient_history"}

    mean = sum(daily_counts) / len(daily_counts)
    std = pd.Series(daily_counts).std()
    z_score = (today_count - mean) / std if std > 0 else 0

    if abs(z_score) > z_threshold:
        return {
            "anomaly": True,
            "z_score": z_score,
            "today": today_count,
            "historical_mean": mean,
            "direction": "spike" if z_score > 0 else "drop",
            "severity": "critical" if abs(z_score) > 5 else "high"
        }
    return {"anomaly": False, "z_score": z_score}
```

## Quality Gate Integration

```python
def pipeline_with_quality_gates(source_query: str, destination_table: str):
    """ETL pipeline with quality checks at each stage."""
    # Extract
    df = extract_data(source_query)

    # Gate 1: Source completeness
    quality_check = DataQualityChecker(df)
    result = (quality_check
              .check_completeness(["order_id", "customer_id", "total_amount"])
              .check_uniqueness(["order_id"])
              .validate())

    if not result["passed"]:
        raise PipelineQualityError(f"Source quality check failed: {result['errors']}")

    # Transform
    df = transform(df)

    # Gate 2: Post-transform validation
    post_result = validate_batch(df.to_dict("records"))
    if post_result["invalid_rate"] > 0.01:  # > 1% invalid records
        raise PipelineQualityError(f"Transform produced too many invalid records: {post_result['invalid_rate']:.2%}")

    # Load
    rows_loaded = load_to_warehouse(df, destination_table)

    # Gate 3: Volume check
    anomaly = detect_volume_anomalies(get_historical_counts(), rows_loaded)
    if anomaly.get("anomaly"):
        alert_data_team(f"Volume anomaly detected: {anomaly}")

    return {"rows_loaded": rows_loaded, "quality_warnings": result["warnings"]}
```

## Quality Score Dashboard

Track per pipeline, per day:
- Null rate per column
- Duplicate rate
- Schema violations per batch
- Volume vs. expectation (actual/expected ratio)
- Freshness: hours since latest record timestamp
- Overall quality score = weighted average of all checks
