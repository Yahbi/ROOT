---
name: Regression Analysis
description: OLS, Ridge, Lasso regression with multicollinearity and heteroscedasticity diagnostics
version: "1.0.0"
author: ROOT
tags: [data-analysis, regression, statistics, OLS, regularization]
platforms: [all]
---

# Regression Analysis

Apply linear regression techniques with proper diagnostics to model relationships, make predictions, and extract causal insights.

## Ordinary Least Squares (OLS)

- **Model**: `Y = X * beta + epsilon` where beta minimizes `SUM((Y_i - X_i * beta)^2)`
- **Closed form**: `beta_hat = (X'X)^{-1} X'Y`; use QR decomposition in practice for numerical stability
- **Assumptions (BLUE)**: Linearity, independence, homoscedasticity, normality of residuals, no multicollinearity
- **Interpretation**: `beta_j` = expected change in Y for 1-unit change in X_j, holding others constant
- **R-squared**: `R^2 = 1 - SS_res/SS_tot`; proportion of variance explained; always report adjusted R^2
- **F-test**: Joint significance of all predictors; `F = (R^2/k) / ((1-R^2)/(n-k-1))`; reject H0 if p < 0.05

## Ridge Regression (L2 Regularization)

- **Objective**: Minimize `SUM(residuals^2) + lambda * SUM(beta_j^2)`
- **Solution**: `beta_ridge = (X'X + lambda*I)^{-1} X'Y`; shrinks coefficients toward zero
- **When to use**: High multicollinearity (VIF > 10); more predictors than observations; reduce overfitting
- **Lambda selection**: Cross-validation (5-fold or 10-fold); plot CV error vs lambda; choose lambda at minimum
- **Effect**: All coefficients retained but shrunk; does not perform variable selection
- **Standardize first**: Ridge penalizes by magnitude; standardize X to mean=0, std=1 before fitting

## Lasso Regression (L1 Regularization)

- **Objective**: Minimize `SUM(residuals^2) + lambda * SUM(|beta_j|)`
- **Key property**: Sets some coefficients exactly to zero; performs automatic variable selection
- **When to use**: Many features with suspected sparsity; feature selection needed; interpretability priority
- **Elastic Net**: `alpha * L1 + (1-alpha) * L2`; combines Lasso selection with Ridge stability; alpha=0.5 is good default
- **Lambda path**: Use coordinate descent along lambda sequence; glmnet / sklearn implement efficiently
- **Group Lasso**: Selects entire groups of correlated features together; useful for categorical variables

## Multicollinearity Diagnostics

- **VIF (Variance Inflation Factor)**: `VIF_j = 1 / (1 - R_j^2)` where R_j^2 = regressing X_j on all other X's
- **Thresholds**: VIF < 5 acceptable; VIF 5-10 concerning; VIF > 10 severe multicollinearity
- **Condition number**: `kappa = sqrt(max_eigenvalue / min_eigenvalue)` of X'X; kappa > 30 = problematic
- **Correlation matrix**: Pairwise |r| > 0.8 between predictors = potential collinearity
- **Remedies**: Remove one of correlated pair, use PCA, switch to Ridge/Lasso, combine into composite variable
- **Impact**: Inflated standard errors → unreliable t-tests; coefficients unstable across samples

## Heteroscedasticity Diagnostics

- **Visual**: Plot residuals vs fitted values; fan/cone shape = heteroscedasticity
- **Breusch-Pagan test**: Regress squared residuals on X; significant F-stat = heteroscedasticity (H0: homoscedastic)
- **White test**: More general; includes squares and cross-products of X; detects nonlinear patterns
- **Goldfeld-Quandt test**: Split data by suspected source; compare residual variances between groups
- **Remedies**: Heteroscedasticity-consistent (HC) standard errors (White/robust SE); weighted least squares (WLS)
- **HC variants**: HC0 (White), HC1 (small-sample correction), HC3 (jackknife-based, preferred for small n)

## Model Selection and Validation

- **Adjusted R^2**: Penalizes for number of predictors; `R^2_adj = 1 - (1-R^2)(n-1)/(n-k-1)`
- **AIC/BIC**: `AIC = n*ln(SS_res/n) + 2k`; `BIC = n*ln(SS_res/n) + k*ln(n)`; lower = better; BIC penalizes more
- **Cross-validation**: k-fold CV RMSE is gold standard for predictive accuracy; avoids overfitting
- **Residual diagnostics**: Check normality (Q-Q plot), independence (Durbin-Watson), influential points (Cook's distance)
- **Cook's distance**: `D_i > 4/n` flags influential observations; investigate and decide to keep or remove
- **Out-of-sample R^2**: True predictive test; if much lower than in-sample, model is overfit

## Risk Management

- **Overfitting**: More predictors ≠ better model; use holdout set, never evaluate on training data alone
- **Extrapolation**: Regression predictions unreliable outside the range of training data; flag out-of-range predictions
- **Causal claims**: OLS estimates associations, not causation (unless experimental design); be precise in language
- **Outlier sensitivity**: A single extreme observation can dramatically shift OLS estimates; always check leverage plots
- **Time series data**: OLS assumes independence; serial correlation violates this — use Newey-West SE or time series models
