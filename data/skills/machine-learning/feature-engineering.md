---
name: Feature Engineering
description: Scaling, encoding, selection, and interaction features for ML models
version: "1.0.0"
author: ROOT
tags: [machine-learning, feature-engineering, scaling, encoding, selection]
platforms: [all]
---

# Feature Engineering

Transform raw data into informative features that improve model performance.

## Numerical Feature Processing

### Scaling Methods
| Method | When to Use | Formula |
|--------|------------|---------|
| StandardScaler | Gaussian-distributed features, linear models | (x - mean) / std |
| MinMaxScaler | Bounded features, neural networks | (x - min) / (max - min) |
| RobustScaler | Features with outliers | (x - median) / IQR |
| Log transform | Right-skewed distributions (income, prices) | log(x + 1) |
| Power transform (Box-Cox) | Heavily non-normal distributions | Automatic normalization |

### Best Practices
- Fit scaler on training data only — transform test data using train statistics
- Log-transform target variables for regression when residuals are heteroscedastic
- Clip extreme outliers before scaling (> 5 standard deviations)

## Categorical Encoding

### Methods
- **One-hot encoding**: Low cardinality (< 15 categories), tree and linear models
- **Label encoding**: Ordinal categories (low/med/high), tree models only
- **Target encoding**: High cardinality (zip codes, product IDs) — use with regularization
- **Frequency encoding**: Replace category with its occurrence count
- **Embedding**: Very high cardinality + deep learning (user IDs, words)

### Handling Unknown Categories
- Reserve an "unknown" category for values not seen during training
- Target encoding naturally handles unknowns (falls back to global mean)

## Feature Selection

### Filter Methods (fast, model-agnostic)
- Correlation with target: drop features with |correlation| < 0.05
- Mutual information: non-linear dependency measure
- Variance threshold: drop near-zero variance features

### Wrapper Methods (model-dependent)
- Recursive Feature Elimination (RFE): iteratively remove least important feature
- Forward/backward selection: add/remove features based on CV score

### Embedded Methods (built into model)
- L1 regularization (Lasso): drives unimportant weights to zero
- Tree-based importance: use XGBoost feature importance or permutation importance
- SHAP values: most reliable importance ranking, computationally expensive

## Interaction Features

### Creating Interactions
- Multiply pairs of features: `feature_A * feature_B`
- Ratio features: `price / square_footage` (price per sqft)
- Polynomial features: `x^2, x^3` for capturing non-linear effects
- Domain-specific: `revenue / employees` (revenue per employee)

### When to Create Interactions
- Linear models benefit most (cannot learn interactions automatically)
- Tree models learn interactions natively — adding explicit ones rarely helps
- Neural networks learn interactions but may benefit from hand-crafted domain features

## Feature Engineering Checklist

1. Profile data: distributions, missing rates, cardinality, outliers
2. Handle missing values: impute or create missingness indicator
3. Encode categoricals with appropriate method
4. Scale numericals with appropriate method
5. Create domain-specific features and interactions
6. Select features using importance ranking + cross-validation
7. Validate: compare model performance with and without engineered features
