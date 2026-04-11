---
name: Anomaly Detection
description: Statistical and ML approaches to detecting anomalies and outliers
version: "1.0.0"
author: ROOT
tags: [machine-learning, anomaly-detection, outlier, fraud, monitoring]
platforms: [all]
---

# Anomaly Detection

Detect unusual patterns in data using statistical and machine learning methods.

## Method Selection

| Method | Data Type | Labeled Data? | Strengths |
|--------|----------|--------------|-----------|
| Z-score / IQR | Univariate numerical | No | Simple, interpretable |
| Isolation Forest | Tabular, medium-high dim | No | Fast, scales well |
| Local Outlier Factor | Spatial/clustered data | No | Detects local anomalies |
| Autoencoder | High-dimensional, complex | No | Learns normal patterns |
| Supervised (XGBoost) | Any | Yes (labeled anomalies) | Best accuracy when labels exist |
| DBSCAN | Spatial/temporal clusters | No | Natural cluster boundary detection |

## Statistical Methods

### Z-Score Method
- Compute z-score: `z = (x - mean) / std`
- Flag points with |z| > 3 as anomalies
- Limitation: assumes normal distribution, sensitive to outliers in mean/std
- Use modified z-score with median/MAD for robustness

### IQR Method
- Q1 = 25th percentile, Q3 = 75th percentile, IQR = Q3 - Q1
- Lower fence: Q1 - 1.5 * IQR, Upper fence: Q3 + 1.5 * IQR
- Points outside fences are anomalies
- Works well for skewed distributions

### Time Series: Rolling Statistics
- Compute rolling mean and standard deviation (window = 30-90 points)
- Flag points > 3 rolling standard deviations from rolling mean
- Handles seasonality: use seasonal decomposition first, then detect anomalies in residuals

## Machine Learning Methods

### Isolation Forest
1. Build ensemble of random trees that isolate individual points
2. Anomalies are isolated in fewer splits (shorter average path length)
3. Set contamination parameter to expected anomaly rate (1-5%)
4. Works well up to ~100 features without feature selection

### Autoencoder Approach
1. Train autoencoder on normal data only
2. Compute reconstruction error for each new data point
3. High reconstruction error = point doesn't match learned normal patterns
4. Set threshold at 95th or 99th percentile of training reconstruction errors

## Application Patterns

### Fraud Detection Pipeline
1. Feature engineering: transaction amount, frequency, time of day, location distance
2. Train model on labeled fraud/legitimate transactions
3. Score every transaction in real-time
4. Alert on scores above threshold — human review for borderline cases
5. Feedback loop: investigation outcomes retrain model monthly

### System Monitoring
1. Collect metrics: CPU, memory, latency, error rate, request volume
2. Build per-metric seasonal baselines (hour-of-day, day-of-week)
3. Alert when metric deviates > 3 sigma from seasonal baseline
4. Correlate anomalies across metrics to reduce false positives

## Evaluation

- **Precision**: What fraction of detected anomalies are real? (false alarm rate)
- **Recall**: What fraction of real anomalies are detected? (miss rate)
- **F1**: Balance between precision and recall
- For unsupervised methods: manual review of top-N anomalies to calibrate threshold
- Track false positive rate over time — alert fatigue kills anomaly detection systems
