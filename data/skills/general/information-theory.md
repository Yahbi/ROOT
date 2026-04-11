---
name: Information Theory
description: Entropy, mutual information, KL divergence, and channel capacity for data and signal analysis
version: "1.0.0"
author: ROOT
tags: [general, information-theory, entropy, statistics, signals]
platforms: [all]
---

# Information Theory

Quantify information content, measure distribution differences, and optimize communication channels using Shannon's mathematical framework.

## Entropy

- **Shannon entropy**: `H(X) = -SUM(p(x) * log2(p(x)))` measured in bits; quantifies average surprise/uncertainty
- **Maximum entropy**: Uniform distribution has highest entropy; `H_max = log2(n)` for n outcomes
- **Minimum entropy**: Deterministic variable has H = 0; no uncertainty, no information
- **Binary entropy**: `H(p) = -p*log2(p) - (1-p)*log2(p)` for Bernoulli; maximum at p = 0.5 (1 bit)
- **Differential entropy**: Continuous version; `h(X) = -integral(f(x) * ln(f(x)) dx)`; can be negative
- **Joint entropy**: `H(X,Y) = -SUM(p(x,y) * log2(p(x,y)))`; always `>= max(H(X), H(Y))`
- **Conditional entropy**: `H(Y|X) = H(X,Y) - H(X)`; remaining uncertainty about Y after observing X

## Mutual Information

- **Definition**: `I(X;Y) = H(X) + H(Y) - H(X,Y) = H(X) - H(X|Y)`
- **Interpretation**: Information shared between X and Y; reduction in uncertainty about X from knowing Y
- **Properties**: Symmetric `I(X;Y) = I(Y;X)`, non-negative, zero iff X and Y are independent
- **Normalized MI**: `NMI = 2*I(X;Y) / (H(X) + H(Y))`; ranges [0,1]; useful for clustering comparison
- **vs Correlation**: MI captures nonlinear dependencies that Pearson correlation misses; strictly more general
- **Feature selection**: Rank features by MI with target variable; select top-k features; captures nonlinear relevance
- **Application in trading**: MI between signal and future returns quantifies predictive power regardless of relationship form

## KL Divergence (Kullback-Leibler)

- **Formula**: `KL(P || Q) = SUM(p(x) * log(p(x) / q(x)))` for discrete; integral for continuous
- **Interpretation**: Information lost when Q is used to approximate P; "surprise penalty" of wrong model
- **Properties**: Non-negative (Gibbs' inequality); NOT symmetric (`KL(P||Q) != KL(Q||P)`); NOT a metric
- **Forward KL** `KL(P||Q)`: Q avoids placing mass where P is zero; mean-seeking; used in variational inference
- **Reverse KL** `KL(Q||P)`: Q concentrates where P has mass; mode-seeking; used in policy optimization
- **Applications**: Model comparison, anomaly detection (distribution shift), reinforcement learning (policy updates)
- **JS divergence**: `JSD(P||Q) = 0.5*KL(P||M) + 0.5*KL(Q||M)` where M = (P+Q)/2; symmetric, bounded [0, ln(2)]

## Cross-Entropy

- **Formula**: `H(P,Q) = -SUM(p(x) * log(q(x))) = H(P) + KL(P||Q)`
- **Machine learning**: Standard loss function for classification; minimizing cross-entropy = minimizing KL from true distribution
- **Binary cross-entropy**: `-[y*log(p) + (1-y)*log(1-p)]`; loss for binary classification
- **Categorical cross-entropy**: `-SUM(y_i * log(p_i))`; loss for multi-class classification
- **Relationship**: `H(P,Q) >= H(P)` always; equality iff Q = P (perfect model)

## Channel Capacity

- **Shannon capacity**: `C = max_{p(x)} I(X;Y)` bits per channel use; fundamental limit on reliable communication
- **Binary symmetric channel**: `C = 1 - H(p_error)` bits; if error rate p = 0.5, capacity = 0 (pure noise)
- **AWGN channel**: `C = 0.5 * log2(1 + SNR)` bits per symbol; Shannon-Hartley theorem
- **Practical implication**: Reliable communication is possible at any rate below capacity (with coding); impossible above
- **Rate-distortion**: `R(D) = min_{p(x_hat|x)} I(X;X_hat)` subject to `E[d(X,X_hat)] <= D`; minimum bits for lossy compression

## Applications to Finance and Data Science

### Market Efficiency
- **MI between signals and returns**: `I(signal; future_returns)` quantifies information content of trading signal
- **Transfer entropy**: Directional MI; `TE(X->Y) = I(Y_t+1; X_t | Y_t)`; detects causal information flow between assets
- **Entropy of returns**: Higher entropy = more unpredictable (efficient market); lower entropy = more structure (exploitable)

### Feature Analysis
- **Redundancy detection**: High MI between features indicates redundancy; remove one without information loss
- **Information bottleneck**: Compress input to representation that preserves maximum MI with target; principled dimensionality reduction
- **Entropy-based discretization**: Bin continuous variables to maximize MI with target; optimal bin boundaries

### Anomaly Detection
- **Distribution shift**: Monitor KL divergence between training and production data distributions; spike = concept drift
- **Threshold**: `KL > 0.1` typically indicates meaningful distribution shift; calibrate per application
- **Online monitoring**: Compute KL on sliding windows; alert when sustained shift detected

## Risk Management

- **Estimation bias**: Entropy and MI estimates from finite samples are biased upward; use Miller-Madow correction or jackknife
- **Binning sensitivity**: Discrete MI estimates depend heavily on binning choice; use k-nearest-neighbor estimators (KSG) for continuous data
- **Curse of dimensionality**: MI estimation degrades in high dimensions; mutual information between high-d vectors is unreliable
- **Overfitting**: High MI on training data may not generalize; always evaluate on held-out data
- **Interpretation**: MI gives magnitude of relationship but not direction or functional form; supplement with visualization
