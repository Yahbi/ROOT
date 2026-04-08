---
name: MLOps CI/CD for Model Deployment
description: Automated testing, validation, and deployment pipelines for ML models using GitHub Actions and GitLab CI
version: "1.0.0"
author: ROOT
tags: [mlops, cicd, github-actions, automation, testing, deployment]
platforms: [all]
difficulty: intermediate
---

# MLOps CI/CD for Model Deployment

Apply software engineering CI/CD practices to ML: automated testing, quality gates,
and safe deployment pipelines for models and training code.

## CI/CD Pipeline Stages

```
Code Push → Lint & Unit Test → Integration Test → Model Validation → Staging Deploy → Production Deploy
             (2 min)            (10 min)           (30 min)           (15 min)           (manual gate)
```

## GitHub Actions Workflow

```yaml
# .github/workflows/ml-ci.yml
name: ML CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 2 * * 1"  # Weekly retrain on Monday at 2am

env:
  MODEL_NAME: fraud_detector
  MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_URI }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Lint
        run: |
          flake8 src/ --max-line-length=100
          black --check src/
          mypy src/ --ignore-missing-imports

      - name: Unit tests
        run: pytest tests/unit/ -v --tb=short --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4

  validate-data:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Validate training data quality
        run: |
          python scripts/validate_data.py \
            --data-path ${{ secrets.DATA_PATH }} \
            --min-rows 10000 \
            --max-missing-pct 0.05

  train-and-evaluate:
    needs: validate-data
    runs-on: [self-hosted, gpu]  # GPU runner for training
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Train model
        run: |
          python scripts/train.py \
            --experiment-name ${{ github.run_id }} \
            --output-run-id-file run_id.txt

      - name: Evaluate against champion
        run: |
          python scripts/evaluate.py \
            --run-id $(cat run_id.txt) \
            --champion-stage Production \
            --min-improvement 0.01

      - name: Promote to staging if better
        if: success()
        run: |
          python scripts/promote.py \
            --run-id $(cat run_id.txt) \
            --target-stage Staging

  integration-test:
    needs: train-and-evaluate
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: kubectl apply -f k8s/staging/ --namespace=ml-staging

      - name: Wait for rollout
        run: kubectl rollout status deployment/fraud-detector -n ml-staging --timeout=300s

      - name: Run integration tests against staging
        run: pytest tests/integration/ --base-url=${{ secrets.STAGING_URL }} -v

      - name: Performance test
        run: |
          k6 run tests/load/performance_test.js \
            --env BASE_URL=${{ secrets.STAGING_URL }} \
            --vus 50 --duration 60s

  deploy-production:
    needs: integration-test
    runs-on: ubuntu-latest
    environment:
      name: production  # Requires manual approval in GitHub
    steps:
      - name: Deploy to production (canary)
        run: |
          kubectl set image deployment/fraud-detector \
            fraud-detector=${{ env.IMAGE_TAG }} \
            -n ml-production

      - name: Monitor canary (5 min)
        run: |
          python scripts/monitor_canary.py \
            --duration 300 \
            --error-threshold 0.02 \
            --latency-threshold 200

      - name: Full rollout
        run: kubectl rollout resume deployment/fraud-detector -n ml-production

      - name: Promote model to production stage
        run: |
          python scripts/promote.py \
            --run-id $(cat run_id.txt) \
            --target-stage Production
```

## Model Validation Scripts

```python
# scripts/evaluate.py — Quality gate before promotion
import mlflow
import argparse
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--champion-stage", default="Production")
    parser.add_argument("--min-improvement", type=float, default=0.01)
    args = parser.parse_args()

    client = mlflow.MlflowClient()
    new_run = client.get_run(args.run_id)
    new_auc = new_run.data.metrics.get("val_auc", 0)

    # Get champion metrics
    champion_versions = client.get_latest_versions("FraudDetector", stages=[args.champion_stage])
    if champion_versions:
        champ_run = client.get_run(champion_versions[0].run_id)
        champ_auc = champ_run.data.metrics.get("val_auc", 0)
        improvement = new_auc - champ_auc
    else:
        champ_auc = 0
        improvement = new_auc - 0.90  # Compare to minimum floor if no champion

    print(f"Champion AUC: {champ_auc:.4f}, New AUC: {new_auc:.4f}, Improvement: {improvement:.4f}")

    if improvement < args.min_improvement:
        print(f"FAIL: Improvement {improvement:.4f} below threshold {args.min_improvement}")
        sys.exit(1)
    print("PASS: Model meets promotion criteria")

if __name__ == "__main__":
    main()
```

## Testing Pyramid for ML

```
          /\
         /  \  Evaluation Tests (LLM-as-judge, human eval)
        /    \
       /------\  Integration Tests (API contracts, end-to-end)
      /        \
     /----------\  Model Tests (performance, drift, shadow mode)
    /            \
   /--------------\  Unit Tests (feature engineering, preprocessing)
```

### Unit Tests

```python
# tests/unit/test_features.py
def test_transaction_feature_engineering():
    df = pd.DataFrame({"amount": [100, 200, 150], "user_id": ["u1", "u1", "u1"]})
    result = compute_user_features(df)
    assert "avg_spend_30d" in result.columns
    assert result["avg_spend_30d"].iloc[0] == pytest.approx(150.0, rel=0.01)

def test_missing_values_handled():
    df = pd.DataFrame({"amount": [None, 200, None], "user_id": ["u1", "u1", "u1"]})
    result = compute_user_features(df)
    assert not result.isnull().any().any(), "Features should have no nulls after preprocessing"
```

### Integration Tests

```python
# tests/integration/test_inference_api.py
def test_inference_endpoint_returns_valid_schema(base_url):
    response = requests.post(
        f"{base_url}/predict",
        json={"amount": 150.0, "merchant": "grocery_store", "user_id": "u123"},
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=5
    )
    assert response.status_code == 200
    data = response.json()
    assert "fraud_probability" in data
    assert 0 <= data["fraud_probability"] <= 1
    assert "model_version" in data
    assert response.elapsed.total_seconds() < 0.5  # < 500ms
```

## Rollback Automation

```bash
#!/bin/bash
# scripts/emergency_rollback.sh
set -e

NAMESPACE=${1:-"ml-production"}
DEPLOYMENT=${2:-"fraud-detector"}

echo "EMERGENCY ROLLBACK: Rolling back $DEPLOYMENT in $NAMESPACE"
kubectl rollout undo deployment/$DEPLOYMENT -n $NAMESPACE
kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=120s
echo "Rollback complete"

# Also rollback model stage in MLflow
python scripts/promote.py --rollback --target-stage Production
```
