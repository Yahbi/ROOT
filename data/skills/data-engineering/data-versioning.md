---
name: Data Versioning and Reproducibility
description: Version datasets, track data lineage, and ensure ML experiment reproducibility with DVC and Delta Lake
version: "1.0.0"
author: ROOT
tags: [data-engineering, versioning, DVC, reproducibility, lineage, datasets]
platforms: [all]
difficulty: intermediate
---

# Data Versioning and Reproducibility

Ensure that ML experiments are fully reproducible by versioning datasets, code,
and configurations together. Know exactly what data trained each model.

## Why Data Versioning Matters

Without data versioning:
- "Which data trained model v2.3?" — unknown
- A dataset change breaks a model silently
- Cannot reproduce a past experiment
- Data bugs discovered months later cannot be traced to affected models

## DVC (Data Version Control)

### Setup

```bash
# Initialize DVC in your git repo
git init
dvc init

# Configure remote storage (S3 example)
dvc remote add -d myremote s3://my-ml-data/dvc-store
dvc remote modify myremote region us-east-1

# Track a dataset
dvc add data/train.csv
# Creates: data/train.csv.dvc (tracked in git) + data/.gitignore

git add data/train.csv.dvc data/.gitignore
git commit -m "Add training dataset v1.0"
dvc push  # Upload data to S3
```

### Versioning Workflow

```bash
# Update dataset
python scripts/collect_new_data.py  # Generates data/train.csv

# Version the new dataset
dvc add data/train.csv
git add data/train.csv.dvc
git commit -m "Update training dataset: added 30 days of new orders"
git tag "data-v1.1"
dvc push

# Reproduce experiment with exact version of data
git checkout data-v1.0
dvc checkout  # Restores data/train.csv to v1.0 version
python train.py  # Fully reproducible
```

### DVC Pipeline Tracking

```yaml
# dvc.yaml — define reproducible pipeline stages
stages:
  extract:
    cmd: python scripts/extract_data.py --date ${date}
    deps:
      - scripts/extract_data.py
    params:
      - params.yaml:
        - extract.date_from
        - extract.date_to
    outs:
      - data/raw/orders.parquet

  feature_engineering:
    cmd: python scripts/build_features.py
    deps:
      - scripts/build_features.py
      - data/raw/orders.parquet
    outs:
      - data/features/train.parquet
      - data/features/test.parquet

  train:
    cmd: python scripts/train.py
    deps:
      - scripts/train.py
      - data/features/train.parquet
    params:
      - params.yaml:
        - model.learning_rate
        - model.max_depth
        - model.n_estimators
    outs:
      - models/fraud_detector.pkl
    metrics:
      - metrics.json:
          cache: false  # Track metrics in git without caching
```

```bash
# Run full pipeline (only re-runs changed stages)
dvc repro

# Show what changed between runs
dvc diff HEAD~1
dvc metrics diff HEAD~1
```

## Delta Lake Time Travel

```python
from delta import DeltaTable
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .getOrCreate()

# Read data as it was at a specific point in time
historical_df = spark.read \
    .format("delta") \
    .option("timestampAsOf", "2026-01-01T00:00:00") \
    .load("s3://datalake/gold/fact_orders/")

# Read a specific version
version_df = spark.read \
    .format("delta") \
    .option("versionAsOf", 15) \
    .load("s3://datalake/gold/fact_orders/")

# Show history
delta_table = DeltaTable.forPath(spark, "s3://datalake/gold/fact_orders/")
delta_table.history(20).show()
# Shows: version, timestamp, operation, operationMetrics, userMetadata
```

## Dataset Registry

```python
import json
from datetime import datetime

class DatasetRegistry:
    """Track all datasets used in experiments with full metadata."""

    def __init__(self, registry_path: str = "data/registry.json"):
        self.registry_path = registry_path
        self.registry = self._load()

    def _load(self) -> dict:
        try:
            with open(self.registry_path) as f:
                return json.load(f)
        except FileNotFoundError:
            return {"datasets": {}}

    def register_dataset(self, name: str, version: str, metadata: dict) -> str:
        """Register a dataset version with full provenance."""
        dataset_id = f"{name}@{version}"

        self.registry["datasets"][dataset_id] = {
            "name": name,
            "version": version,
            "created_at": datetime.now().isoformat(),
            "row_count": metadata["row_count"],
            "date_range": metadata.get("date_range"),
            "source": metadata.get("source"),
            "schema_hash": metadata.get("schema_hash"),
            "content_hash": metadata.get("content_hash"),  # MD5 of file
            "s3_path": metadata.get("s3_path"),
            "dvc_md5": metadata.get("dvc_md5"),
            "git_commit": metadata.get("git_commit"),
            "description": metadata.get("description"),
        }
        self._save()
        return dataset_id

    def get_dataset(self, name: str, version: str) -> dict:
        return self.registry["datasets"].get(f"{name}@{version}")

    def list_versions(self, name: str) -> list:
        return [k for k in self.registry["datasets"] if k.startswith(f"{name}@")]
```

## Experiment Reproducibility Checklist

```python
class ExperimentContext:
    """Capture all information needed to reproduce a training run."""

    def __init__(self, experiment_name: str):
        self.experiment_name = experiment_name
        self.context = {}

    def capture(self, dataset_versions: dict, hyperparams: dict, model_config: dict) -> dict:
        import subprocess, platform

        self.context = {
            "experiment_name": self.experiment_name,
            "timestamp": datetime.now().isoformat(),
            # Data
            "datasets": dataset_versions,  # {"train": "orders@v1.2", "test": "orders@v1.2-test"}
            # Code
            "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
            "git_branch": subprocess.check_output(["git", "branch", "--show-current"]).decode().strip(),
            "git_dirty": bool(subprocess.check_output(["git", "diff", "--name-only"])),
            # Environment
            "python_version": platform.python_version(),
            "pip_freeze": subprocess.check_output(["pip", "freeze"]).decode(),
            # Config
            "hyperparameters": hyperparams,
            "model_config": model_config,
        }
        return self.context

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.context, f, indent=2)

    @classmethod
    def reproduce(cls, context_path: str) -> str:
        """Print instructions to reproduce this experiment."""
        with open(context_path) as f:
            ctx = json.load(f)

        instructions = [
            f"git checkout {ctx['git_commit']}",
            f"dvc checkout  # Restore datasets",
            f"pip install -r requirements.txt",
            f"python train.py --config {json.dumps(ctx['hyperparameters'])}"
        ]
        return "\n".join(instructions)
```

## Data Contract Between Teams

```yaml
# data-contracts/orders_daily.yaml
name: orders_daily
producer: data-engineering
consumers: [ml-team, analytics, finance]
version: "2.1.0"
sla:
  freshness_hours: 4
  availability: 99.5%

schema:
  order_id: {type: string, nullable: false, unique: true}
  customer_id: {type: string, nullable: false}
  total_amount: {type: float, nullable: false, min: 0}
  status: {type: string, enum: [pending, completed, cancelled, refunded]}
  created_at: {type: timestamp, nullable: false}

breaking_changes:
  - Removing columns requires 30-day notice
  - Renaming columns requires 30-day deprecation period
  - Schema changes communicated to all consumers via Slack #data-contracts

changelog:
  "2.1.0": "Added promo_code column (non-breaking)"
  "2.0.0": "Renamed amount to total_amount (breaking — 30 days notice given)"
```
