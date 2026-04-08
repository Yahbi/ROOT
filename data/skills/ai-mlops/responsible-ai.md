---
name: Responsible AI and Model Fairness
description: Implement fairness testing, bias detection, and responsible AI practices in production ML systems
version: "1.0.0"
author: ROOT
tags: [mlops, responsible-ai, fairness, bias, ethics, compliance]
platforms: [all]
difficulty: intermediate
---

# Responsible AI and Model Fairness

Ensure ML systems are fair, explainable, and safe before and after deployment.
Bias in models causes real harm — build fairness checks into every stage.

## Fairness Metrics

### Group Fairness Metrics

```python
import pandas as pd
import numpy as np
from sklearn.metrics import confusion_matrix

def compute_fairness_metrics(y_true, y_pred, sensitive_attr, group_a, group_b):
    """
    Compute fairness metrics between two demographic groups.
    sensitive_attr: column name of the protected attribute
    group_a: e.g., "male", group_b: e.g., "female"
    """
    results = {}

    for group, label in [(group_a, "A"), (group_b, "B")]:
        mask = sensitive_attr == group
        y_t, y_p = y_true[mask], y_pred[mask]
        tn, fp, fn, tp = confusion_matrix(y_t, y_p).ravel()

        results[label] = {
            "positive_rate": (tp + fp) / len(y_t),      # Demographic parity
            "true_positive_rate": tp / (tp + fn),         # Equal opportunity
            "false_positive_rate": fp / (fp + tn),        # Equalized odds component
            "accuracy": (tp + tn) / len(y_t),
            "sample_size": len(y_t)
        }

    # Fairness ratios (target: all ratios between 0.8 and 1.25 — 80% rule)
    return {
        "demographic_parity_ratio": results["B"]["positive_rate"] / results["A"]["positive_rate"],
        "equal_opportunity_ratio": results["B"]["true_positive_rate"] / results["A"]["true_positive_rate"],
        "disparate_impact": results["B"]["positive_rate"] / results["A"]["positive_rate"],
        "groups": results
    }
```

### Fairness Thresholds

| Metric | Acceptable Range | Regulatory Reference |
|--------|-----------------|---------------------|
| Disparate Impact (80% rule) | 0.8 - 1.25 | EEOC guidelines |
| Equal Opportunity | 0.85 - 1.15 | NIST AI RMF |
| Predictive Parity | 0.80 - 1.20 | COMPAS audit |
| Calibration parity | 0.90 - 1.10 | Best practice |

## Bias Detection Framework

### Pre-Training: Data Bias

```python
def audit_dataset_bias(df: pd.DataFrame, sensitive_cols: list, label_col: str) -> dict:
    issues = []

    for col in sensitive_cols:
        # Check label distribution per group
        label_dist = df.groupby(col)[label_col].mean()
        ratio = label_dist.max() / label_dist.min()

        if ratio > 1.5:
            issues.append({
                "type": "label_imbalance",
                "column": col,
                "ratio": ratio,
                "distribution": label_dist.to_dict(),
                "severity": "high" if ratio > 3.0 else "medium"
            })

        # Check sample size parity
        group_sizes = df[col].value_counts()
        size_ratio = group_sizes.max() / group_sizes.min()
        if size_ratio > 5:
            issues.append({
                "type": "sample_imbalance",
                "column": col,
                "ratio": size_ratio,
                "severity": "medium"
            })

    return {"issues": issues, "overall_risk": "high" if len(issues) > 2 else "low"}
```

### Post-Training: Prediction Bias

```python
def audit_model_predictions(model, X_test, y_test, sensitive_col):
    """Run fairness audit on model predictions."""
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    fairness_report = {}
    for group in X_test[sensitive_col].unique():
        mask = X_test[sensitive_col] == group
        group_y_true = y_test[mask]
        group_y_pred = y_pred[mask]
        group_y_prob = y_prob[mask]

        from sklearn.metrics import roc_auc_score, accuracy_score
        fairness_report[group] = {
            "auc": roc_auc_score(group_y_true, group_y_prob),
            "accuracy": accuracy_score(group_y_true, group_y_pred),
            "positive_prediction_rate": group_y_pred.mean(),
            "n_samples": mask.sum()
        }

    return fairness_report
```

## Explainability

### SHAP Values for Feature Attribution

```python
import shap

# Model-agnostic explanations
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# Global feature importance
shap.summary_plot(shap_values, X_test, feature_names=feature_columns)

# Local explanation for a single prediction
def explain_prediction(instance: pd.DataFrame) -> dict:
    sv = explainer.shap_values(instance)
    contributions = dict(zip(feature_columns, sv[0]))
    top_factors = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    return {
        "prediction": model.predict_proba(instance)[0, 1],
        "top_contributing_factors": top_factors,
        "base_value": explainer.expected_value
    }

# For LLMs — provide natural language explanation
def explain_to_customer(prediction_result: dict) -> str:
    return (f"Your application was {'approved' if prediction_result['approved'] else 'declined'} "
            f"primarily because: {prediction_result['top_factors'][0][0].replace('_', ' ')}")
```

### LIME for Black-Box Models

```python
from lime.lime_tabular import LimeTabularExplainer

explainer = LimeTabularExplainer(
    training_data=X_train.values,
    feature_names=feature_columns,
    class_names=["Not Fraud", "Fraud"],
    mode="classification"
)

def get_lime_explanation(instance):
    exp = explainer.explain_instance(
        instance.values[0],
        model.predict_proba,
        num_features=10
    )
    return exp.as_list()
```

## Model Cards

```markdown
# Model Card: Fraud Detection Model v3.2

## Model Details
- Architecture: Gradient Boosting Classifier (XGBoost 2.0)
- Training date: 2026-04-01
- Version: 3.2.1
- Owner: ML Platform Team

## Intended Use
- Intended: Flag potentially fraudulent credit card transactions in real-time
- NOT intended for: Credit decisions, loan applications, employment screening

## Training Data
- 18 months of transaction data (Jan 2025 - Jun 2026)
- 2.3 million transactions; 0.3% fraud rate
- Geographic scope: United States only

## Performance
| Metric | Overall | Male | Female | Age < 30 | Age 30-60 | Age > 60 |
|--------|---------|------|--------|----------|-----------|----------|
| AUC | 0.97 | 0.97 | 0.96 | 0.95 | 0.97 | 0.94 |
| FPR | 0.01 | 0.01 | 0.012 | 0.015 | 0.009 | 0.018 |

## Fairness Assessment
- Disparate impact (gender): 0.92 — PASS (within 0.8-1.25 threshold)
- Age group AUC parity: Age 60+ shows slightly lower AUC — flag for review

## Known Limitations
- Trained on US data only — poor performance on international transactions
- May underperform during novel fraud patterns not seen in training
- Age 60+ group has slightly higher false positive rate

## Ethical Considerations
- Decisions are advisory — human review required for account suspension
- No appeal process currently automated — escalation path needed

## Monitoring
- Daily PSI checks on 47 input features
- Weekly fairness metric computation
- Automatic retraining trigger if AUC drops below 0.94
```

## Production Compliance Checklist

- [ ] Fairness metrics computed across all protected groups
- [ ] Disparate impact within 80% rule for high-stakes decisions
- [ ] Model card written and approved by legal/compliance
- [ ] Explainability available for adverse decisions (EU AI Act, US ECOA)
- [ ] Human review workflow for borderline predictions
- [ ] Audit log of all predictions stored for 7 years (financial services)
- [ ] Regular bias monitoring on production predictions
- [ ] Incident response plan for bias discovery post-deployment
