---
name: Survival Analysis
description: Kaplan-Meier estimation, Cox proportional hazards, churn prediction, and time-to-event modeling
version: "1.0.0"
author: ROOT
tags: [data-analysis, survival-analysis, statistics, churn, time-to-event]
platforms: [all]
---

# Survival Analysis

Model time-to-event data with censoring, enabling prediction of when events (churn, failure, conversion) will occur.

## Core Concepts

- **Survival function**: `S(t) = P(T > t)` — probability of surviving beyond time t; monotonically decreasing from 1 to 0
- **Hazard function**: `h(t) = lim[P(t < T < t+dt | T > t) / dt]` — instantaneous risk of event at time t given survival to t
- **Cumulative hazard**: `H(t) = -ln(S(t))` — integral of hazard; `S(t) = exp(-H(t))`
- **Censoring**: Right-censored (most common) = event hasn't occurred by end of observation; must not discard these observations
- **Truncation**: Left-truncation = subject only observable after a certain time; creates delayed entry bias

## Kaplan-Meier Estimator

- **Formula**: `S_hat(t) = PRODUCT((n_i - d_i) / n_i)` for all event times t_i <= t
  - n_i = number at risk just before time t_i; d_i = number of events at t_i
- **Confidence bands**: Greenwood formula: `Var(S(t)) = S(t)^2 * SUM(d_i / (n_i * (n_i - d_i)))`
- **Median survival**: Time where S(t) = 0.5; often more meaningful than mean for skewed distributions
- **Log-rank test**: Compare survival curves between groups; `chi^2 = (O - E)^2 / E`; p < 0.05 = significant difference
- **Stratified log-rank**: Control for confounders while comparing groups; stratify by confounder categories
- **Visualization**: Plot survival curves with 95% CI bands; include number-at-risk table below x-axis

## Cox Proportional Hazards Model

- **Model**: `h(t|X) = h_0(t) * exp(beta_1*X_1 + beta_2*X_2 + ...)`
- **Key assumption**: Proportional hazards — hazard ratio `exp(beta)` is constant over time
- **Hazard ratio**: `HR = exp(beta)`; HR > 1 = increased risk; HR < 1 = protective; HR = 1 = no effect
- **Partial likelihood**: Estimates beta without specifying h_0(t); semi-parametric flexibility
- **Tied events**: Use Efron approximation (default in most software); Breslow is simpler but biased with many ties
- **PH testing**: Schoenfeld residual test; plot scaled residuals vs time — flat line = PH holds; slope = violation
- **PH violation remedy**: Stratify by the offending variable, include time*covariate interaction, or use accelerated failure time model

## Churn Prediction Application

### Feature Engineering for Churn
- **Recency**: Days since last activity; strongest single predictor of churn
- **Frequency**: Actions per period (logins, purchases, feature usage); declining trend = risk
- **Monetary**: Revenue per customer; low-value customers churn more but matter less financially
- **Engagement score**: Composite of product usage depth, feature adoption, session duration
- **Support tickets**: Rising ticket count or negative sentiment in tickets predicts churn within 30-60 days
- **Contract features**: Time-to-renewal, payment method (annual < monthly churn), plan tier

### Modeling Pipeline
1. **Define event**: Churn = no activity for 30+ days, or explicit cancellation
2. **Construct survival dataset**: Entry date, event/censoring date, time-varying covariates
3. **Fit Cox model**: Identify significant risk factors; report hazard ratios with 95% CI
4. **Predict individual risk**: `S_i(t) = S_0(t)^exp(X_i * beta)` — personalized survival curves
5. **Rank by risk**: Sort customers by predicted 30/60/90-day churn probability; target interventions
6. **Evaluate**: Concordance index (C-index) > 0.7 is good; > 0.8 is excellent; time-dependent AUC

## Advanced Methods

### Competing Risks
- **Problem**: Multiple possible events (churn vs upgrade vs downgrade); treating non-target events as censored biases estimates
- **Fine-Gray model**: Models subdistribution hazard; cumulative incidence function respects competing events
- **Cause-specific hazard**: Separate Cox model per event type; censors other events; estimates different quantity

### Time-Varying Covariates
- **Problem**: Covariate values change during follow-up (usage patterns, plan changes)
- **Implementation**: Split observation into sub-intervals; update covariate values at each change point
- **Extended Cox model**: `h(t|X(t)) = h_0(t) * exp(beta * X(t))`; handles dynamic features naturally

### Random Survival Forests
- **Advantage**: Non-parametric; handles interactions and nonlinearities automatically; no PH assumption needed
- **Ensemble**: Grows survival trees using log-rank splitting criterion; aggregates with cumulative hazard
- **Variable importance**: Permutation-based; identifies predictive features without model specification

## Tools and Libraries

| Tool | Language | Best For |
|------|----------|----------|
| lifelines | Python | Kaplan-Meier, Cox PH, AFT; great API and documentation |
| scikit-survival | Python | Machine learning + survival; RSF, gradient boosting |
| survival (R) | R | Gold standard; comprehensive methods, diagnostics |
| statsmodels | Python | Duration models, competing risks |

## Risk Management

- **Censoring informative?**: If censoring is related to outcome (e.g., sick patients leave study), estimates are biased
- **Immortal time bias**: Misclassifying pre-treatment time as treated inflates survival; align time origins correctly
- **Sample size**: Cox model needs ~10-15 events per covariate for stable estimates; avoid overfitting
- **Extrapolation**: Survival predictions beyond observed follow-up are unreliable; report extrapolation uncertainty
- **Competing risks**: Ignoring competing events overestimates event probability; always check if alternatives exist
