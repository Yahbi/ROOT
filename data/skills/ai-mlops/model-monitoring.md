---
name: ML Model Monitoring
description: Detect data drift, concept drift, and model degradation in production ML systems
version: "1.0.0"
author: ROOT
tags: [mlops, monitoring, drift-detection, model-health, observability]
platforms: [all]
difficulty: intermediate
---

# ML Model Monitoring

Production models degrade silently. Monitor inputs, outputs, and business metrics
to detect issues before they cause customer impact.

## Monitoring Layers

```
Layer 1: Infrastructure   → Latency, throughput, error rates, memory, CPU
Layer 2: Data Quality     → Missing values, type errors, out-of-range inputs
Layer 3: Data Drift       → Input feature distributions shifting from training
Layer 4: Concept Drift    → Relationship between features and target changing
Layer 5: Business Impact  → Revenue, conversion, user satisfaction degrading
```

## Data Drift Detection

### Population Stability Index (PSI)

```python
import numpy as np

def calculate_psi(reference: np.array, current: np.array, n_bins: int = 10) -> float:
    """
    PSI < 0.1:  No significant drift
    PSI 0.1-0.2: Moderate drift — investigate
    PSI > 0.2:  Major drift — model likely degraded
    """
    reference_pct = np.histogram(reference, bins=n_bins)[0] / len(reference)
    current_pct = np.histogram(current, bins=n_bins)[0] / len(current)

    # Avoid division by zero
    reference_pct = np.where(reference_pct == 0, 1e-4, reference_pct)
    current_pct = np.where(current_pct == 0, 1e-4, current_pct)

    psi = np.sum((current_pct - reference_pct) * np.log(current_pct / reference_pct))
    return psi
```

### Kolmogorov-Smirnov Test

```python
from scipy.stats import ks_2samp

def detect_feature_drift(train_feature: np.array, live_feature: np.array) -> dict:
    statistic, p_value = ks_2samp(train_feature, live_feature)
    return {
        "ks_statistic": statistic,
        "p_value": p_value,
        "drift_detected": p_value < 0.05,
        "severity": "high" if statistic > 0.3 else "medium" if statistic > 0.1 else "low"
    }
```

### Categorical Feature Drift (Chi-Squared)

```python
from scipy.stats import chi2_contingency

def detect_categorical_drift(train_counts: dict, live_counts: dict) -> dict:
    all_categories = set(train_counts.keys()) | set(live_counts.keys())
    train_arr = [train_counts.get(c, 0) for c in all_categories]
    live_arr = [live_counts.get(c, 0) for c in all_categories]
    chi2, p_value, _, _ = chi2_contingency([train_arr, live_arr])
    return {"chi2": chi2, "p_value": p_value, "drift_detected": p_value < 0.05}
```

## Concept Drift Detection

Concept drift = the relationship between features and target changes.
Harder to detect because it requires ground truth labels (often delayed).

### Methods

1. **Rolling window accuracy**: Track model accuracy on labeled data over time
   - Alert if accuracy drops > 5% from baseline over any 7-day window
   
2. **Prediction distribution monitoring**: 
   - Even without labels, watch if prediction distribution shifts significantly
   - Classifier outputting more "positive" predictions → may indicate concept drift
   
3. **ADWIN (Adaptive Windowing)**:
   ```python
   # Statistical test that detects when error rate has changed
   from river.drift import ADWIN
   adwin = ADWIN()
   for error in model_errors:  # error = 0 or 1 per prediction
       adwin.update(error)
       if adwin.drift_detected:
           trigger_retraining()
   ```

## Monitoring Dashboard Metrics

### Real-Time Metrics (Alert within 5 minutes)

```python
REALTIME_ALERTS = {
    "error_rate": {"threshold": 0.05, "window": "5m"},      # > 5% errors
    "p99_latency_ms": {"threshold": 500, "window": "5m"},   # > 500ms p99
    "null_prediction_rate": {"threshold": 0.01, "window": "5m"},  # > 1% null predictions
}
```

### Daily Metrics (Detect gradual drift)

```python
DAILY_CHECKS = {
    "psi_per_feature": {"alert_threshold": 0.2, "warn_threshold": 0.1},
    "prediction_mean_shift": {"alert_threshold": 0.15},   # 15% shift in mean prediction
    "prediction_variance_shift": {"alert_threshold": 0.3},
    "missing_rate_per_feature": {"alert_threshold": 0.05},  # > 5% missing
}
```

### Weekly Metrics (Model health summary)

```python
WEEKLY_METRICS = [
    "model_accuracy_on_labeled_sample",
    "feature_drift_count",       # number of features with PSI > 0.1
    "prediction_confidence_mean",
    "schema_violations_count",
    "retraining_trigger_count",
]
```

## Automated Alerting

```python
# Monitoring pipeline structure
class ModelMonitor:
    def run_daily_checks(self, model_id: str):
        features_today = self.load_production_features(model_id)
        features_train = self.load_training_features(model_id)

        drift_report = {}
        for col in features_train.columns:
            if features_train[col].dtype in ["float64", "int64"]:
                psi = calculate_psi(features_train[col], features_today[col])
                drift_report[col] = psi
                if psi > 0.2:
                    self.alert(f"CRITICAL: Feature {col} PSI={psi:.3f} for model {model_id}")
                elif psi > 0.1:
                    self.alert(f"WARNING: Feature {col} PSI={psi:.3f} for model {model_id}",
                              severity="warning")
        return drift_report
```

## Retraining Triggers

Automate retraining decisions based on monitoring signals:

| Signal | Action |
|--------|--------|
| PSI > 0.2 on 3+ features | Queue retraining job |
| Accuracy drops > 5% from baseline | Immediate retrain |
| Data drift in top 5 most important features | Priority retrain |
| Business metric degradation > 10% | Emergency retrain + escalate |
| Scheduled: every 30 days | Routine refresh |

## Logging Schema

```json
{
  "model_id": "fraud_detector_v3",
  "timestamp": "2026-04-08T12:00:00Z",
  "request_id": "req_abc123",
  "input_features": {"amount": 150.0, "merchant_category": "grocery", "...": "..."},
  "prediction": 0.12,
  "prediction_class": "not_fraud",
  "latency_ms": 45,
  "model_version": "3.2.1",
  "feature_source": "online_store"
}
```

Always log: inputs, outputs, latency, model version — enable retrospective drift analysis.

## Tooling Options

| Tool | Type | Best For |
|------|------|---------|
| Evidently AI | Open source | Data drift reports |
| WhyLabs | SaaS | Automated drift alerts |
| Fiddler | SaaS | Explainability + monitoring |
| Arize | SaaS | Enterprise model observability |
| Great Expectations | Open source | Data quality checks |
| MLflow | Open source | Experiment tracking + model registry |
