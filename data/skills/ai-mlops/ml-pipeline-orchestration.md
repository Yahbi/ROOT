---
name: ML Pipeline Orchestration
description: Build, schedule, and monitor end-to-end ML training and inference pipelines with Airflow, Prefect, or Kubeflow
version: "1.0.0"
author: ROOT
tags: [mlops, pipeline, orchestration, airflow, prefect, kubeflow, automation]
platforms: [all]
difficulty: intermediate
---

# ML Pipeline Orchestration

Automate the full ML lifecycle from data ingestion through model deployment using
workflow orchestration tools that provide scheduling, retry, and observability.

## Pipeline Architecture

```
Data Ingestion → Feature Engineering → Model Training → Evaluation → Deploy/Reject
     │                  │                    │               │
   (daily)          (on change)          (on trigger)   (automated)
```

## Airflow ML Pipeline

### DAG Structure

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.s3_key_sensor import S3KeySensor
from datetime import datetime, timedelta

default_args = {
    "owner": "ml-team",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": ["ml-team@company.com"],
}

with DAG(
    dag_id="fraud_model_retrain",
    default_args=default_args,
    schedule_interval="0 2 * * 1",  # Every Monday at 2am
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ml", "fraud", "production"],
) as dag:

    # Wait for new training data to arrive
    wait_for_data = S3KeySensor(
        task_id="wait_for_training_data",
        bucket_key="s3://data-lake/fraud/training/{{ ds }}/",
        timeout=3600,
        poke_interval=300,
    )

    validate_data = PythonOperator(
        task_id="validate_data_quality",
        python_callable=run_data_validation,
        op_kwargs={"date": "{{ ds }}"}
    )

    compute_features = PythonOperator(
        task_id="compute_features",
        python_callable=run_feature_engineering,
    )

    train_model = PythonOperator(
        task_id="train_model",
        python_callable=run_training,
        executor_config={"resources": {"request_memory": "16Gi", "request_cpu": "4"}}
    )

    evaluate_model = PythonOperator(
        task_id="evaluate_model",
        python_callable=run_evaluation,
    )

    deploy_model = PythonOperator(
        task_id="deploy_if_better",
        python_callable=conditional_deploy,
    )

    wait_for_data >> validate_data >> compute_features >> train_model >> evaluate_model >> deploy_model
```

## Prefect ML Pipeline (Modern Alternative)

```python
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact
import mlflow

@task(retries=3, retry_delay_seconds=60, log_prints=True)
def ingest_data(date: str) -> pd.DataFrame:
    df = load_from_warehouse(date)
    print(f"Loaded {len(df)} rows for {date}")
    return df

@task
def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    assert df.isnull().mean().max() < 0.05, "Too many null values"
    assert len(df) > 1000, "Insufficient training data"
    return df

@task
def train_model(df: pd.DataFrame) -> str:
    with mlflow.start_run() as run:
        X, y = prepare_features(df)
        model = train_gradient_boosting(X, y)
        metrics = evaluate_model(model, X_val, y_val)
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(model, "model")
        return run.info.run_id

@flow(name="fraud-model-retrain", log_prints=True)
def retrain_pipeline(date: str):
    raw_data = ingest_data(date)
    clean_data = validate_data(raw_data)
    run_id = train_model(clean_data)

    # Create result artifact in Prefect UI
    create_markdown_artifact(
        key="training-results",
        markdown=f"Training completed. MLflow run: {run_id}"
    )
    return run_id

if __name__ == "__main__":
    retrain_pipeline(date="2026-04-08")
```

## Kubeflow Pipelines (Kubernetes-Native)

```python
import kfp
from kfp import dsl

@dsl.component(
    base_image="python:3.11",
    packages_to_install=["scikit-learn", "pandas", "mlflow"]
)
def train_model_component(
    data_path: str,
    model_output_path: kfp.dsl.OutputPath()
):
    import pandas as pd
    from sklearn.ensemble import GradientBoostingClassifier
    df = pd.read_parquet(data_path)
    # ... training logic
    model.save(model_output_path)

@dsl.pipeline(name="ML Training Pipeline")
def ml_pipeline(data_path: str):
    train_task = train_model_component(data_path=data_path)
    train_task.set_memory_request("8G")
    train_task.set_cpu_request("4")
    train_task.set_gpu_limit("1")

    evaluate_task = evaluate_model_component(
        model_path=train_task.outputs["model_output_path"]
    )
    evaluate_task.after(train_task)
```

## Pipeline Best Practices

### Data Versioning
```python
# Use DVC or Delta Lake for dataset versioning
# Never overwrite training data — always version by date/run_id
import dvc.api

data_url = dvc.api.get_url("data/train.csv", rev="v1.2.0")
```

### Artifact Tracking
```python
# Every training run logs artifacts to MLflow
with mlflow.start_run(run_name=f"train_{today}"):
    mlflow.log_params({"learning_rate": 0.01, "max_depth": 6, "n_estimators": 500})
    mlflow.log_metrics({"accuracy": 0.94, "f1": 0.92, "auc": 0.97})
    mlflow.log_artifact("feature_importance.png")
    mlflow.sklearn.log_model(model, "model", registered_model_name="FraudDetector")
```

### Conditional Deployment
```python
def conditional_deploy(new_run_id: str, champion_run_id: str, threshold: float = 0.02):
    """Only promote new model if it beats champion by threshold"""
    new_auc = get_metric(new_run_id, "auc")
    champion_auc = get_metric(champion_run_id, "auc")

    if new_auc > champion_auc + threshold:
        promote_to_production(new_run_id)
        notify_team(f"New model promoted: AUC {new_auc:.4f} vs {champion_auc:.4f}")
    else:
        log_rejection(f"New model not better: {new_auc:.4f} vs {champion_auc:.4f}")
```

## Pipeline Monitoring

```python
PIPELINE_SLOS = {
    "max_runtime_hours": 4,
    "data_freshness_hours": 25,  # Should run within 25h of scheduled time
    "minimum_training_rows": 50000,
    "minimum_eval_auc": 0.90,    # Reject if model is worse than this floor
}

# Alert channels: PagerDuty (P0), Slack (P1), email (P2)
```

## Tooling Comparison

| Tool | Best For | Complexity |
|------|---------|-----------|
| Airflow | Batch-heavy, complex DAGs | Medium |
| Prefect | Python-native, simpler setup | Low |
| Kubeflow | Kubernetes-first, GPU jobs | High |
| Dagster | Data asset management | Medium |
| Metaflow | Data scientists (not DevOps) | Low |
| GitHub Actions | Simple CI/CD-triggered training | Very Low |
