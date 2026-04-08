---
name: A/B Testing for ML Models
description: Statistically rigorous framework for comparing ML model variants in production
version: "1.0.0"
author: ROOT
tags: [mlops, ab-testing, experimentation, statistics, model-comparison]
platforms: [all]
difficulty: intermediate
---

# A/B Testing for ML Models

Rigorously compare model variants to make confident promotion decisions,
avoiding both false positives (promoting worse models) and false negatives (rejecting better ones).

## Experimental Design

### Step 1: Define Success Metrics
Before launching any test, commit to:
- **Primary metric**: Single metric that drives the decision (e.g., revenue, conversion rate)
- **Guardrail metrics**: Metrics that must NOT regress (e.g., latency, error rate)
- **Secondary metrics**: Informational only — don't drive decisions

### Step 2: Power Analysis (Sample Size)
```python
from scipy import stats
import numpy as np

def required_sample_size(baseline_rate, min_detectable_effect, alpha=0.05, power=0.80):
    """
    Calculate minimum sample size per variant.
    baseline_rate: current conversion rate (e.g., 0.10 for 10%)
    min_detectable_effect: smallest meaningful improvement (e.g., 0.02 for 2pp)
    """
    z_alpha = stats.norm.ppf(1 - alpha/2)  # Two-tailed
    z_beta = stats.norm.ppf(power)

    p1 = baseline_rate
    p2 = baseline_rate + min_detectable_effect
    p_bar = (p1 + p2) / 2

    n = (z_alpha * np.sqrt(2 * p_bar * (1 - p_bar)) +
         z_beta * np.sqrt(p1*(1-p1) + p2*(1-p2)))**2 / (p1-p2)**2
    return int(np.ceil(n))

# Example: 10% baseline, detect 2pp improvement, 80% power
n = required_sample_size(0.10, 0.02)
print(f"Minimum {n} samples per variant needed")
```

### Step 3: Traffic Splitting
```python
# Deterministic hash-based assignment (consistent user experience)
import hashlib

def assign_variant(user_id: str, experiment_id: str, traffic_pct: float = 0.5) -> str:
    hash_val = int(hashlib.md5(f"{user_id}:{experiment_id}".encode()).hexdigest(), 16)
    normalized = (hash_val % 10000) / 10000.0
    if normalized < traffic_pct:
        return "treatment"
    return "control"
```

## Running the Experiment

### Traffic Ramp Schedule
```
Day 1-2:    1% treatment — watch for severe regressions
Day 3-5:    5% treatment — check latency and errors
Day 6-10:  10% treatment — accumulate early signal
Day 11-20: 50% treatment — reach target sample size
```

### Minimum Run Duration
- **Minimum 2 weeks**: Capture weekly seasonality effects
- **Minimum sample size**: Per power analysis above
- **Never stop early for positive results** — peeking inflates false positive rate

### Guardrail Monitoring (Real-Time)
```python
# Auto-stop conditions:
GUARDRAILS = {
    "p99_latency_ms": {"threshold": 200, "direction": "max"},  # must not exceed 200ms
    "error_rate": {"threshold": 0.02, "direction": "max"},     # must not exceed 2%
    "crash_rate": {"threshold": 0.001, "direction": "max"},    # must not exceed 0.1%
}
# Check hourly; auto-rollback if any guardrail breached
```

## Statistical Analysis

### Standard Hypothesis Test
```python
from scipy.stats import chi2_contingency, ttest_ind

# For conversion rates (binary outcomes):
def analyze_experiment(control_conversions, control_n, treatment_conversions, treatment_n):
    contingency = [[control_conversions, control_n - control_conversions],
                   [treatment_conversions, treatment_n - treatment_conversions]]
    chi2, p_value, _, _ = chi2_contingency(contingency)

    control_rate = control_conversions / control_n
    treatment_rate = treatment_conversions / treatment_n
    lift = (treatment_rate - control_rate) / control_rate * 100

    return {
        "control_rate": control_rate,
        "treatment_rate": treatment_rate,
        "lift_pct": lift,
        "p_value": p_value,
        "significant": p_value < 0.05
    }
```

### Bayesian Analysis (Alternative)
```python
from scipy.stats import beta

# Bayesian A/B for binary outcomes
def bayesian_ab(control_successes, control_failures, treatment_successes, treatment_failures, simulations=100000):
    control_samples = beta.rvs(control_successes + 1, control_failures + 1, size=simulations)
    treatment_samples = beta.rvs(treatment_successes + 1, treatment_failures + 1, size=simulations)
    prob_treatment_better = (treatment_samples > control_samples).mean()
    expected_lift = (treatment_samples - control_samples).mean()
    return {"prob_treatment_better": prob_treatment_better, "expected_lift": expected_lift}
```

## Decision Framework

```
p_value < 0.05 AND primary metric improved AND no guardrail regressions → PROMOTE
p_value < 0.05 AND primary metric regressed → REJECT (rollback)
p_value >= 0.05 AND sample size met → NO WINNER (keep control or iterate)
Guardrail breached (any) → AUTO-ROLLBACK immediately
```

## Multi-Armed Bandit (Alternative to Pure A/B)

Use when you want to minimize regret during the experiment:
- Thompson Sampling allocates more traffic to better-performing variants in real-time
- Good for revenue-sensitive contexts where classic A/B wastes traffic on the loser
- Not suitable when: sample sizes are fixed, need clean causal inference, regulatory audit required

## Common Mistakes

1. **Peeking**: Checking results before target sample size → inflated false positive rate
2. **Multiple comparisons**: Testing 5 variants without correction → 23% false positive chance
   - Apply Bonferroni correction: α_adjusted = 0.05 / number_of_variants
3. **Novelty effect**: Users behave differently when first exposed to new feature → run 2+ weeks
4. **Survivor bias**: Only analyzing users who completed the flow biases results
5. **Network effects**: In social products, users affect each other → use cluster randomization

## Experiment Logging Schema

```json
{
  "experiment_id": "model_v2_vs_v1",
  "start_date": "2026-04-01",
  "end_date": "2026-04-15",
  "hypothesis": "New model v2 increases conversion by 2%",
  "primary_metric": "conversion_rate",
  "target_sample": 50000,
  "traffic_split": {"control": 0.5, "treatment": 0.5},
  "result": {"p_value": 0.021, "lift": 2.4, "decision": "PROMOTE"}
}
```
