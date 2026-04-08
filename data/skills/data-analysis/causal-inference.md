---
name: Causal Inference
description: Difference-in-differences, regression discontinuity, instrumental variables, and propensity score matching
version: "1.0.0"
author: ROOT
tags: [data-analysis, causal-inference, econometrics, experiments, statistics]
platforms: [all]
---

# Causal Inference

Establish causal relationships from observational data using quasi-experimental designs when randomized experiments are infeasible.

## The Fundamental Problem

- **Counterfactual**: We observe `Y_treated` but never `Y_control` for the same unit at the same time
- **Selection bias**: Treated and control groups differ systematically; naive comparison is biased
- **Confounders**: Variables that affect both treatment assignment and outcome
- **Goal**: Estimate Average Treatment Effect `ATE = E[Y(1) - Y(0)]` or ATT (on the treated)
- **Identification strategies**: Create conditions that approximate random assignment from observational data

## Difference-in-Differences (DiD)

- **Setup**: Treatment and control groups observed before and after an intervention
- **Estimator**: `DiD = (Y_treat_post - Y_treat_pre) - (Y_control_post - Y_control_pre)`
- **Key assumption**: Parallel trends — absent treatment, both groups would have followed same trajectory
- **Testing parallel trends**: Plot pre-treatment trends; formal test: interaction of group x pre-period time trends
- **Regression**: `Y = beta_0 + beta_1*Treat + beta_2*Post + beta_3*(Treat*Post) + epsilon`; beta_3 is the DiD estimate
- **Staggered adoption**: When treatment rolls out at different times, use Callaway-Sant'Anna or Sun-Abraham estimators (not TWFE)
- **Cluster standard errors**: At the treatment unit level; failure to cluster dramatically understates SEs

## Regression Discontinuity Design (RDD)

- **Setup**: Treatment assigned by a cutoff on a running variable (test score, income threshold, date)
- **Sharp RDD**: Treatment jumps from 0 to 1 at cutoff; `ATE = lim(Y|X→c+) - lim(Y|X→c-)`
- **Fuzzy RDD**: Treatment probability jumps at cutoff but not from 0 to 1; use cutoff as instrument (IV)
- **Bandwidth selection**: Use Imbens-Kalyanaraman or Calonico-Cattaneo-Titiunik optimal bandwidth
- **Local polynomial**: Fit separate polynomials on each side of cutoff; linear preferred over higher-order
- **Validity checks**: Test for manipulation (McCrary density test); check continuity of covariates at cutoff
- **Limitation**: Identifies only Local Average Treatment Effect at the cutoff; not generalizable

## Instrumental Variables (IV)

- **Purpose**: Address endogeneity (omitted variable bias, simultaneity, measurement error)
- **Requirements**: Instrument Z must be (1) relevant: corr(Z, X) ≠ 0, and (2) exclusive: Z affects Y only through X
- **2SLS procedure**: Stage 1: `X = alpha + gamma*Z + u`; Stage 2: `Y = beta_0 + beta_1*X_hat + epsilon`
- **First-stage F-statistic**: F > 10 (Stock-Yogo threshold); weak instruments bias IV toward OLS
- **Over-identification**: With multiple instruments, use Sargan/Hansen J-test to check exclusion restriction
- **LATE**: IV estimates Local Average Treatment Effect for compliers (those whose treatment status changes with Z)
- **Common instruments**: Distance to facility, historical/geographical features, policy changes, genetic variants

## Propensity Score Matching (PSM)

- **Propensity score**: `e(X) = P(Treatment=1 | X)` estimated by logistic regression or gradient boosting
- **Matching**: Pair treated units with control units having similar propensity scores
- **Methods**: Nearest-neighbor (1:1 or 1:k), caliper matching (max distance 0.2 SD of logit PS), kernel matching
- **Balance check**: After matching, standardized mean differences < 0.1 for all covariates
- **Overlap assumption**: Common support required; trim observations with PS < 0.05 or > 0.95
- **Doubly robust**: Combine PSM with regression adjustment; consistent if either the PS or outcome model is correct
- **Limitation**: Only controls for observed confounders; unobserved confounders still bias results

## Sensitivity Analysis

- **Rosenbaum bounds**: How much hidden bias would be needed to explain away the result? Report Gamma value
- **E-value**: Minimum strength of unmeasured confounding to fully explain observed association
- **Placebo tests**: Apply treatment to pre-treatment period or untreated group; should find no effect
- **Dose-response**: If causal, stronger treatment → stronger effect; test monotonic relationship
- **Negative controls**: Find outcomes that treatment should not affect; significant effect = confounding evidence

## Practical Checklist

1. **Define causal question**: What is the treatment? What is the counterfactual?
2. **Draw DAG**: Directed Acyclic Graph of causal relationships; identify confounders and mediators
3. **Choose method**: DiD for policy changes, RDD for cutoff-based treatments, IV for endogeneity, PSM for baseline
4. **Check assumptions**: Parallel trends (DiD), no manipulation (RDD), instrument validity (IV), overlap (PSM)
5. **Estimate**: Run analysis with robust standard errors; report point estimate and confidence interval
6. **Sensitivity**: Run Rosenbaum bounds or E-value; how fragile is the result?
7. **Interpret**: Specify the estimand (ATE, ATT, LATE); do not over-generalize beyond identification strategy

## Risk Management

- **No substitute for RCT**: Observational causal inference is always conditional on untestable assumptions
- **Pre-registration**: Commit to methodology before seeing results; prevents specification search
- **Multiple testing**: Adjust for multiple outcomes (Bonferroni, BHY); report all pre-specified analyses
- **Effect size realism**: Observational studies tend to overestimate effects vs RCTs; discount by 20-40%
