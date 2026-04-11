---
name: Bayesian Analysis
description: Prior selection, MCMC sampling, conjugate priors, and credible interval construction
version: "1.0.0"
author: ROOT
tags: [data-analysis, bayesian, statistics, MCMC, inference]
platforms: [all]
---

# Bayesian Analysis

Update beliefs about parameters using observed data via Bayes' theorem, producing full posterior distributions rather than point estimates.

## Bayes' Theorem Foundation

- **Formula**: `P(theta|data) = P(data|theta) * P(theta) / P(data)`
- **Posterior** = Likelihood x Prior / Evidence (normalizing constant)
- **Key insight**: Posterior combines prior knowledge with data; with more data, likelihood dominates
- **vs Frequentist**: Bayesian quantifies uncertainty about parameters; frequentist about repeated sampling
- **Predictive distribution**: `P(y_new|data) = integral P(y_new|theta) * P(theta|data) d_theta`

## Prior Selection

### Informative Priors
- **Expert elicitation**: Interview domain experts; encode as distribution (e.g., "effect is probably 2-5" → Normal(3.5, 1))
- **Historical data**: Use posterior from previous study as prior for new study (Bayesian updating)
- **Regularizing priors**: Normal(0, sigma) centers coefficients near zero; Bayesian Ridge/Lasso equivalent
- **Truncated priors**: Use when parameter has known bounds (e.g., variance > 0 → Half-Normal)

### Non-Informative / Weakly Informative Priors
- **Flat prior**: Uniform over parameter space; equivalent to MLE; not truly non-informative in all parameterizations
- **Jeffreys prior**: `P(theta) ~ sqrt(det(Fisher_information))`; invariant to reparameterization
- **Weakly informative**: Normal(0, 10) for standardized coefficients; constrains without dominating data
- **Recommended default**: Half-Cauchy(0, 2.5) for variance parameters; Normal(0, 2.5) for coefficients (Gelman)

## Conjugate Priors (Closed-Form Solutions)

| Likelihood | Conjugate Prior | Posterior |
|------------|----------------|-----------|
| Normal (known var) | Normal | Normal |
| Normal (known mean) | Inverse-Gamma | Inverse-Gamma |
| Binomial | Beta | Beta |
| Poisson | Gamma | Gamma |
| Multinomial | Dirichlet | Dirichlet |
| Exponential | Gamma | Gamma |

- **Beta-Binomial example**: Prior Beta(a,b) + data (k successes, n-k failures) → Posterior Beta(a+k, b+n-k)
- **Advantage**: No sampling needed; instant posterior computation; useful for online learning
- **Limitation**: Restricted to specific likelihood-prior pairs; complex models need MCMC

## MCMC Sampling Methods

### Metropolis-Hastings
- **Algorithm**: Propose theta* from proposal distribution; accept with probability `min(1, P(theta*|D)/P(theta|D))`
- **Tuning**: Proposal variance matters; acceptance rate ~23% optimal for multivariate; 44% for univariate
- **Limitation**: Slow in high dimensions; sensitive to proposal distribution choice

### Hamiltonian Monte Carlo (HMC)
- **Advantage**: Uses gradient information; efficient in high dimensions; fewer samples needed
- **NUTS (No U-Turn Sampler)**: Adaptive HMC that auto-tunes trajectory length; default in Stan and PyMC
- **Required**: Differentiable log-posterior; cannot handle discrete parameters directly

### Practical MCMC
- **Chains**: Run 4 independent chains; check convergence via Rhat < 1.01 and ESS > 400
- **Warmup/burnin**: Discard first 50% of samples; sampler needs time to find high-density region
- **Thinning**: Generally unnecessary with modern samplers; only thin if storage is a constraint
- **Diagnostics**: Trace plots (mixing), autocorrelation plots (ESS), divergences (model misspecification)

## Credible Intervals

- **Definition**: 95% credible interval = range containing 95% of posterior probability mass
- **vs Confidence interval**: Credible interval has direct probability interpretation; CI does not
- **Equal-tailed**: 2.5th and 97.5th percentiles of posterior; most common
- **Highest Density Interval (HDI)**: Shortest interval containing 95% of mass; preferred for skewed posteriors
- **ROPE (Region of Practical Equivalence)**: Define range of "practically zero" effect; if 95% HDI within ROPE, effect is negligible

## Software and Implementation

| Tool | Language | Strengths |
|------|----------|-----------|
| Stan / CmdStan | R/Python/Julia | Gold standard; NUTS sampler; fastest for complex models |
| PyMC | Python | User-friendly; good for beginners; excellent diagnostics |
| JAGS | R | Gibbs sampling; good for conjugate models; older but stable |
| Turing.jl | Julia | Composable; fast; modern PPL |
| NumPyro | Python | JAX-based; GPU acceleration; very fast HMC |

## Risk Management

- **Prior sensitivity**: Always run sensitivity analysis — if posterior changes dramatically with prior, data is insufficient
- **Computational cost**: MCMC is expensive; budget 10-60 minutes for complex models; use variational inference for quick approximation
- **Model checking**: Posterior predictive checks — simulate data from posterior; if simulated data doesn't match observed, model is wrong
- **Overfitting protection**: Bayesian naturally regularizes via priors; but still use LOO-CV (PSIS-LOO) to compare models
- **Communication**: Report full posterior, not just point estimates; decision-makers need to see uncertainty
