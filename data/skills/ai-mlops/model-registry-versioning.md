---
name: Model Registry and Versioning
description: Manage ML model lifecycle with versioning, staging, and governance using MLflow and similar tools
version: "1.0.0"
author: ROOT
tags: [mlops, model-registry, versioning, mlflow, governance, lifecycle]
platforms: [all]
difficulty: intermediate
---

# Model Registry and Versioning

Centralized hub for managing all ML model versions, transitions between environments,
and deployment governance. Ensures reproducibility and auditability.

## Model Lifecycle Stages

```
None → Staging → Production → Archived

None:       Newly registered, under evaluation
Staging:    Approved for testing, A/B testing candidate
Production: Serving live traffic — current champion
Archived:   Retired — kept for audit/rollback purposes
```

## MLflow Model Registry Setup

```python
import mlflow
from mlflow.tracking import MlflowClient

# Configure MLflow tracking server
mlflow.set_tracking_uri("http://mlflow-server:5000")
mlflow.set_experiment("fraud-detection")

client = MlflowClient()
```

## Registering a Model

```python
# During training — log and register in one step
with mlflow.start_run(run_name=f"train_{datetime.now().isoformat()}") as run:
    # ... training code ...

    # Log parameters and metrics
    mlflow.log_params({
        "model_type": "gradient_boosting",
        "n_estimators": 500,
        "learning_rate": 0.01,
        "max_depth": 6,
        "feature_count": len(feature_columns)
    })
    mlflow.log_metrics({
        "train_auc": train_auc,
        "val_auc": val_auc,
        "val_f1": val_f1,
        "val_precision": val_precision,
        "val_recall": val_recall,
    })

    # Log feature importance
    mlflow.log_artifact("feature_importance.png")
    mlflow.log_artifact("confusion_matrix.png")
    mlflow.log_dict({"feature_columns": feature_columns}, "feature_columns.json")

    # Register model
    model_uri = f"runs:/{run.info.run_id}/model"
    registered = mlflow.register_model(model_uri, "FraudDetector")
    print(f"Model version: {registered.version}")
```

## Model Staging Workflow

```python
def promote_to_staging(model_name: str, run_id: str, reason: str):
    """Move a model version to staging after evaluation approval."""
    # Find the version for this run
    versions = client.search_model_versions(f"name='{model_name}'")
    version = next(v for v in versions if v.run_id == run_id)

    # Transition to staging
    client.transition_model_version_stage(
        name=model_name,
        version=version.version,
        stage="Staging",
        archive_existing_versions=False  # Keep current staging for comparison
    )

    # Add description
    client.update_model_version(
        name=model_name,
        version=version.version,
        description=f"Promoted to Staging: {reason}"
    )

    # Set tags for governance
    client.set_model_version_tag(model_name, version.version, "approved_by", "ml-team")
    client.set_model_version_tag(model_name, version.version, "eval_auc", str(val_auc))
    client.set_model_version_tag(model_name, version.version, "promotion_date", str(date.today()))

def promote_to_production(model_name: str, version: str, approved_by: str):
    """Promote staging model to production — requires human approval."""
    client.transition_model_version_stage(
        name=model_name,
        version=version,
        stage="Production",
        archive_existing_versions=True  # Archive previous production version
    )
    client.set_model_version_tag(model_name, version, "prod_approved_by", approved_by)
    client.set_model_version_tag(model_name, version, "prod_date", str(datetime.now()))
```

## Loading Models from Registry

```python
# Load the current production model
def load_production_model(model_name: str):
    model = mlflow.sklearn.load_model(f"models:/{model_name}/Production")
    return model

# Load a specific version for comparison
def load_version(model_name: str, version: int):
    model = mlflow.sklearn.load_model(f"models:/{model_name}/{version}")
    return model

# Load with metadata
def load_with_metadata(model_name: str):
    version_info = client.get_latest_versions(model_name, stages=["Production"])[0]
    model = mlflow.sklearn.load_model(f"models:/{model_name}/Production")
    run = client.get_run(version_info.run_id)
    return model, run.data.params, run.data.metrics
```

## Automated Promotion Pipeline

```python
def automated_promotion_check(new_run_id: str, model_name: str) -> dict:
    """Automated quality gate before promotion."""
    new_metrics = client.get_run(new_run_id).data.metrics
    prod_versions = client.get_latest_versions(model_name, stages=["Production"])

    if not prod_versions:
        # No production model — promote if it meets minimum bar
        if new_metrics["val_auc"] >= 0.90:
            return {"decision": "promote", "reason": "First production model, meets minimum AUC"}
        return {"decision": "reject", "reason": f"AUC {new_metrics['val_auc']:.4f} below minimum 0.90"}

    prod_metrics = client.get_run(prod_versions[0].run_id).data.metrics
    improvement = new_metrics["val_auc"] - prod_metrics["val_auc"]

    if improvement > 0.01:  # 1% AUC improvement threshold
        return {"decision": "promote_to_staging",
                "reason": f"AUC improved {improvement:.4f} ({prod_metrics['val_auc']:.4f} → {new_metrics['val_auc']:.4f})"}
    elif improvement < -0.02:
        return {"decision": "reject",
                "reason": f"AUC regressed {improvement:.4f}"}
    else:
        return {"decision": "hold",
                "reason": f"Insufficient improvement: {improvement:.4f} (need 0.01)"}
```

## Model Lineage and Reproducibility

```python
# Tag every run with data version for full reproducibility
with mlflow.start_run() as run:
    mlflow.set_tags({
        "data_version": "2026-04-01",
        "data_source": "s3://data-lake/fraud/2026-04-01/",
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "training_host": socket.gethostname(),
        "python_version": sys.version,
        "scikit_version": sklearn.__version__,
    })
```

## Rollback Procedure

```python
def emergency_rollback(model_name: str):
    """Roll back to the previous production version."""
    all_versions = client.search_model_versions(f"name='{model_name}'")
    archived = [v for v in all_versions if v.current_stage == "Archived"]

    if not archived:
        raise ValueError("No archived versions to roll back to")

    # Get most recently archived (was production before current)
    previous = max(archived, key=lambda v: v.last_updated_timestamp)

    # Roll back
    client.transition_model_version_stage(model_name, previous.version, "Production",
                                          archive_existing_versions=True)
    return previous.version
```

## Governance Checklist

Before promoting any model to production:
- [ ] Validation AUC meets minimum threshold
- [ ] No regression on fairness metrics (gender, age, race parity)
- [ ] Latency tested under expected production load
- [ ] Shadow mode run against recent production traffic
- [ ] Rollback procedure documented and tested
- [ ] Model card updated (training data, known limitations, intended use)
- [ ] Business owner approval documented as tag
