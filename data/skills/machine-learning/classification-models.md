---
name: Classification Models
description: XGBoost, random forest, SVM, and ensemble methods for classification tasks
version: "1.0.0"
author: ROOT
tags: [machine-learning, classification, XGBoost, ensemble, SVM]
platforms: [all]
---

# Classification Models

Select, train, and evaluate classification models for binary and multi-class problems.

## Model Selection Guide

| Model | Best For | Handles Non-Linear | Interpretable | Training Speed |
|-------|---------|-------------------|---------------|----------------|
| Logistic Regression | Baseline, linear boundaries | No | High | Fast |
| Random Forest | Tabular data, noisy features | Yes | Medium | Medium |
| XGBoost/LightGBM | Tabular data, competitions | Yes | Medium | Medium |
| SVM (RBF kernel) | Small datasets, high-dim | Yes | Low | Slow (>100K rows) |
| Neural Network | Large datasets, complex patterns | Yes | Low | Slow |

## Gradient Boosted Trees (XGBoost / LightGBM)

### Key Hyperparameters
```
learning_rate: 0.01-0.1 (lower = more trees needed, better generalization)
max_depth: 3-8 (deeper = more complex, higher overfit risk)
n_estimators: 100-5000 (use early stopping, not fixed)
min_child_weight: 1-10 (higher = more conservative)
subsample: 0.7-0.9 (row sampling per tree)
colsample_bytree: 0.7-0.9 (feature sampling per tree)
```

### Tuning Strategy
1. Fix learning_rate=0.1, tune max_depth and min_child_weight
2. Tune subsample and colsample_bytree
3. Add regularization (reg_alpha, reg_lambda) if overfitting
4. Lower learning_rate to 0.01, increase n_estimators with early stopping

## Ensemble Methods

### Stacking
- Train 3-5 diverse base models (XGBoost, RF, SVM, logistic regression)
- Use out-of-fold predictions as features for a meta-learner
- Meta-learner is typically logistic regression or simple average
- Improves accuracy by 1-3% in practice

### Voting
- Hard voting: majority class wins
- Soft voting: average predicted probabilities, then threshold
- Soft voting almost always outperforms hard voting

## Handling Imbalanced Classes

| Technique | When to Use | Impact |
|-----------|------------|--------|
| Class weights | Always try first | Adjusts loss function |
| SMOTE | Moderate imbalance (1:10) | Synthetic minority samples |
| Undersampling | Large dataset, extreme imbalance | Reduces majority class |
| Threshold tuning | Probability calibration available | Adjusts decision boundary |

### Threshold Optimization
- Default threshold (0.5) is rarely optimal for imbalanced data
- Plot precision-recall curve, select threshold based on business requirements
- Use F-beta score: beta > 1 weights recall, beta < 1 weights precision

## Evaluation

### Metrics for Classification
- **Accuracy**: Only useful when classes are balanced
- **Precision/Recall/F1**: Standard for imbalanced problems
- **AUC-ROC**: Overall ranking ability across all thresholds
- **AUC-PR**: Better than ROC for highly imbalanced data
- **Log loss**: Penalizes confident wrong predictions

### Cross-Validation
- Use stratified K-fold (K=5) to maintain class balance in each fold
- For time-dependent data, use time-series split instead
- Report mean and standard deviation across folds
