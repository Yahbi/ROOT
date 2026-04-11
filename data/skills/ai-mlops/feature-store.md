---
name: Feature Store Design and Operations
description: Build and operate centralized feature stores for consistent ML feature serving across training and inference
version: "1.0.0"
author: ROOT
tags: [mlops, feature-store, data-engineering, machine-learning, feast, tecton]
platforms: [all]
difficulty: advanced
---

# Feature Store Design and Operations

A feature store eliminates training-serving skew, enables feature reuse across teams,
and provides point-in-time correct historical features for model training.

## Core Problems Feature Stores Solve

1. **Training-serving skew**: Feature computed differently at train time vs. serve time → model underperforms
2. **Duplication**: Every team recomputes the same features independently → waste and inconsistency
3. **Point-in-time correctness**: Training data accidentally uses future information → data leakage
4. **Feature discovery**: Engineers don't know what features exist → reinvent the wheel
5. **Freshness monitoring**: Features go stale and models degrade silently

## Architecture Components

```
Feature Store Components:
  ┌─────────────────────────────────────────────────────────┐
  │  Data Sources → Feature Pipeline → Offline Store (S3)   │
  │                                 → Online Store (Redis)   │
  │                                                          │
  │  Training:   Model pulls historical features from S3     │
  │  Inference:  Model pulls real-time features from Redis   │
  └─────────────────────────────────────────────────────────┘
```

### Offline Store
- **Purpose**: Historical features for model training
- **Technology**: Parquet files on S3, BigQuery, Snowflake
- **Key requirement**: Point-in-time joins (no future data leakage)
- **Retrieval**: Batch read for training datasets

### Online Store
- **Purpose**: Low-latency feature serving at inference time
- **Technology**: Redis, DynamoDB, Cassandra
- **Key requirement**: Sub-10ms read latency
- **Retrieval**: Key-value lookup by entity ID

### Feature Registry
- Metadata catalog: feature name, description, owner, data type, freshness SLA
- Lineage tracking: which pipelines produce which features
- Version control: feature schema versioning for backward compatibility

## Feature Definition (Feast Example)

```python
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float64, Int64, String
from datetime import timedelta

# Define entity (the key your features are indexed by)
user = Entity(name="user", join_keys=["user_id"])

# Define feature view
user_features = FeatureView(
    name="user_transaction_features",
    entities=[user],
    ttl=timedelta(days=30),  # Feature freshness TTL
    schema=[
        Field(name="transaction_count_7d", dtype=Int64),
        Field(name="avg_transaction_value_30d", dtype=Float64),
        Field(name="days_since_last_purchase", dtype=Int64),
        Field(name="preferred_category", dtype=String),
    ],
    source=FileSource(
        path="s3://feature-store/user_features/",
        timestamp_field="event_timestamp"
    ),
    tags={"team": "ml-platform", "domain": "user"}
)
```

## Point-in-Time Correct Training Data

```python
# Create training dataset WITHOUT data leakage
# The feature store only returns features available BEFORE each label timestamp

from feast import FeatureStore

store = FeatureStore(repo_path=".")

# Entity dataframe: each row = an event with its timestamp
entity_df = pd.DataFrame({
    "user_id": ["u1", "u2", "u3"],
    "event_timestamp": ["2026-01-15", "2026-01-16", "2026-01-17"],
    "label": [1, 0, 1]  # target variable
})

# Retrieve features as they existed at each event_timestamp
training_df = store.get_historical_features(
    entity_df=entity_df,
    features=["user_transaction_features:transaction_count_7d",
              "user_transaction_features:avg_transaction_value_30d"]
).to_df()
```

## Real-Time Feature Serving

```python
# At inference time — fetch latest features from online store (Redis)
feature_vector = store.get_online_features(
    features=["user_transaction_features:transaction_count_7d",
              "user_transaction_features:avg_transaction_value_30d"],
    entity_rows=[{"user_id": "u123"}]
).to_dict()

# Combine with request-time features (e.g., current cart value)
features = {**feature_vector, "current_cart_value": 150.0}
prediction = model.predict([features])
```

## Feature Pipeline Design

### Batch Features (Computed on Schedule)
```python
# Spark/dbt/SQL job runs hourly/daily
def compute_user_transaction_features(df: pd.DataFrame, as_of: datetime) -> pd.DataFrame:
    # Window the data to only use events BEFORE as_of timestamp
    historical = df[df["event_time"] <= as_of]
    return historical.groupby("user_id").agg(
        transaction_count_7d=("amount", lambda x: x.tail(7).count()),
        avg_transaction_value_30d=("amount", lambda x: x.tail(30).mean())
    ).reset_index()
```

### Streaming Features (Computed in Real-Time)
```python
# Kafka consumer → feature computation → write to online store
# Use Flink, Spark Streaming, or custom consumer

def process_transaction_event(event: dict):
    user_id = event["user_id"]
    # Update running aggregates in Redis
    redis.hincrby(f"user:{user_id}", "txn_count_7d", 1)
    redis.expire(f"user:{user_id}", 86400 * 7)  # 7-day TTL
```

## Data Quality Monitoring

```python
# Feature health checks — run before each training run
def validate_feature_quality(feature_df: pd.DataFrame) -> dict:
    return {
        "missing_rate": feature_df.isnull().mean().to_dict(),
        "zero_variance_features": [col for col in feature_df.columns
                                   if feature_df[col].std() == 0],
        "distribution_drift": compute_psi(feature_df),  # Population Stability Index
        "freshness": (datetime.now() - feature_df["event_timestamp"].max()).seconds
    }
```

## Feature Store Governance

| Category | Best Practice |
|----------|--------------|
| Naming | `{entity}_{aggregation}_{window}` (e.g., `user_sum_spend_30d`) |
| Ownership | Every feature has a team owner responsible for SLA |
| Documentation | Description, example values, business context required |
| Deprecation | 30-day notice before removing features; version bumps for schema changes |
| Access control | Read/write permissions by team and sensitivity level |

## Deployment Checklist

- [ ] Offline store configured with point-in-time join support
- [ ] Online store configured with < 10ms read SLA
- [ ] Feature pipelines deployed with monitoring and alerting
- [ ] Freshness SLA defined per feature view
- [ ] Data quality checks running before each training job
- [ ] Feature registry populated with documentation
- [ ] Training-serving skew monitoring enabled
- [ ] Rollback procedure for broken feature pipelines
