---
name: Statistical Testing
description: Hypothesis tests, p-values, Bayesian inference, and A/B testing methods
version: "1.0.0"
author: ROOT
tags: [data-analysis, statistics, hypothesis-testing, bayesian, AB-testing]
platforms: [all]
---

# Statistical Testing

Apply the right statistical test to answer questions with confidence.

## Hypothesis Testing Framework

### Steps
1. **State hypotheses**: H0 (null, no effect) and H1 (alternative, there is an effect)
2. **Choose significance level**: alpha = 0.05 (standard), 0.01 (conservative)
3. **Select test**: Based on data type and question (see table below)
4. **Calculate test statistic and p-value**
5. **Decide**: If p-value < alpha, reject H0 (evidence of effect)
6. **Report**: Effect size + confidence interval (not just p-value)

### Test Selection Guide
| Question | Data Type | Test |
|----------|----------|------|
| Two group means differ? | Continuous, normal | t-test (independent or paired) |
| Two group means differ? | Continuous, non-normal | Mann-Whitney U |
| More than 2 group means? | Continuous, normal | ANOVA (one-way) |
| Two proportions differ? | Binary (yes/no) | Chi-squared or Z-test for proportions |
| Relationship between variables? | Both continuous | Pearson correlation |
| Relationship between variables? | Ordinal or non-normal | Spearman rank correlation |

## P-Value Interpretation

### What P-Value Means
- Probability of observing results this extreme if the null hypothesis is true
- p = 0.03 means: "If there's truly no effect, we'd see data this extreme 3% of the time"
- p-value is NOT the probability that the null hypothesis is true

### Common Mistakes
- p < 0.05 does not mean the effect is large or practically meaningful
- p > 0.05 does not mean there is no effect (might just be underpowered)
- Multiple comparisons inflate false positive rate — apply Bonferroni correction
- Always report effect size alongside p-value (Cohen's d, odds ratio, etc.)

## A/B Testing

### Sample Size Calculation
- Inputs needed: baseline metric, minimum detectable effect (MDE), significance (alpha), power (1-beta)
- Standard: alpha=0.05, power=0.80, MDE=5% relative improvement
- Use online calculator or scipy.stats.power for computation
- Running an underpowered test wastes time — calculate sample size first

### Running the Test
1. Randomly assign users to control (A) and treatment (B)
2. Ensure randomization is correct (check covariate balance)
3. Define primary metric before starting (no changing metrics mid-test)
4. Run until predetermined sample size reached (no peeking and stopping early)
5. Analyze with appropriate test (t-test for means, chi-squared for proportions)

### Sequential Testing
- If you must peek: use sequential analysis (alpha spending function)
- Group sequential design allows interim looks while controlling false positive rate
- Bayesian methods naturally support continuous monitoring without inflation

## Bayesian Inference

### Advantages over Frequentist
- Direct probability statements: "85% chance B is better than A"
- No fixed sample size required — update beliefs as data arrives
- Incorporates prior knowledge (useful with domain expertise)
- More intuitive results for stakeholders

### Basic Framework
1. **Prior**: What do you believe before seeing data? (often weakly informative)
2. **Likelihood**: How likely is the observed data given different parameter values?
3. **Posterior**: Updated belief after seeing data = Prior * Likelihood (normalized)
4. Report: Posterior probability that B > A, credible interval for effect size

## Reporting Results

### Template
"We observed a [X%] improvement in [metric] (95% CI: [lower, upper]), which was 
[statistically significant / not significant] at alpha=0.05 (p=[value]). 
The effect size was [Cohen's d / odds ratio]. Based on [N] observations over [time period]."
