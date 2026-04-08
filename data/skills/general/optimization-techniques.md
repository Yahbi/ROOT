---
name: Optimization Techniques
description: Gradient descent, convex optimization, simulated annealing, and genetic algorithms for problem solving
version: "1.0.0"
author: ROOT
tags: [general, optimization, algorithms, machine-learning, operations-research]
platforms: [all]
---

# Optimization Techniques

Select and apply the right optimization algorithm for objective functions ranging from smooth convex problems to rugged combinatorial landscapes.

## Gradient Descent Family

### Batch Gradient Descent
- **Update rule**: `theta = theta - lr * gradient(loss, theta)` using full dataset gradient
- **Learning rate**: Too high = divergence; too low = slow convergence; start with 0.01, decay schedule
- **Convergence**: Guaranteed for convex functions with appropriate learning rate; O(1/t) rate

### Stochastic Gradient Descent (SGD)
- **Update**: Use single sample or mini-batch (32-256 samples) to estimate gradient
- **Advantage**: Escapes local minima due to noise; O(n) cheaper per step than batch
- **Momentum**: `v = beta*v - lr*gradient; theta = theta + v`; accelerates through ravines; beta = 0.9 typical
- **Nesterov momentum**: Evaluate gradient at look-ahead position; better convergence rate

### Adaptive Methods
- **Adam**: `m = beta1*m + (1-beta1)*g; v = beta2*v + (1-beta2)*g^2; theta -= lr*m_hat/sqrt(v_hat+eps)`
- **Adam defaults**: lr = 0.001, beta1 = 0.9, beta2 = 0.999, eps = 1e-8; good general default
- **AdaGrad**: Per-parameter learning rate based on historical gradients; good for sparse features
- **RMSProp**: Moving average of squared gradients; fixes AdaGrad's aggressive rate decay
- **Learning rate schedules**: Cosine annealing, step decay, warm restarts; often more important than optimizer choice

## Convex Optimization

- **Convex function**: `f(lambda*x + (1-lambda)*y) <= lambda*f(x) + (1-lambda)*f(y)` for lambda in [0,1]
- **Key property**: Every local minimum is a global minimum; gradient descent guaranteed to find it
- **KKT conditions**: Necessary and sufficient for optimality in constrained convex problems
- **Linear programming**: `min c'x subject to Ax <= b, x >= 0`; solved by simplex or interior point methods
- **Quadratic programming**: `min 0.5*x'Qx + c'x subject to Ax <= b`; portfolio optimization is QP
- **Second-order cone**: Generalization of QP; handles robust optimization and norm constraints
- **Semidefinite programming**: Optimize over positive semidefinite matrices; used in optimal control and combinatorial relaxations
- **Solvers**: CVXPY (Python modeling), Gurobi (commercial, fastest), MOSEK (conic), GLPK (free LP)

## Simulated Annealing

- **Inspiration**: Metal cooling process; accept worse solutions with decreasing probability over time
- **Algorithm**: Generate neighbor; if better, accept; if worse, accept with probability `exp(-delta/T)`
- **Temperature schedule**: `T(k) = T_0 * alpha^k` with alpha = 0.95-0.99; or `T(k) = T_0 / log(1+k)` (theoretical optimum)
- **Initial temperature**: Set so that ~80% of uphill moves are accepted initially; calibrate by sampling
- **Neighbor generation**: Problem-specific; swap, insert, perturb; neighborhood size affects exploration vs exploitation
- **Reheating**: Periodically increase temperature to escape local optima; adaptive reheating based on stagnation detection
- **Best for**: Combinatorial optimization (TSP, scheduling, bin packing) where gradient is unavailable
- **Convergence**: Theoretically converges to global optimum with logarithmic cooling schedule (impractically slow)

## Genetic Algorithms

- **Components**: Population of candidate solutions; fitness function; selection; crossover; mutation
- **Encoding**: Binary string, real-valued vector, permutation, or tree (for programs)
- **Selection**: Tournament (pick best of k random individuals), roulette wheel (fitness-proportional), rank-based
- **Crossover**: Single-point, two-point, uniform (bit-level); PMX or order crossover for permutations
- **Mutation**: Bit flip (binary), Gaussian perturbation (real), swap/insert (permutation); rate 0.01-0.05
- **Elitism**: Always keep top N individuals unchanged; prevents loss of best solution
- **Population size**: 50-200 typical; larger for more complex landscapes; too small = premature convergence

### Advanced Variants
- **Differential Evolution (DE)**: `trial = x_r1 + F*(x_r2 - x_r3)`; excellent for continuous optimization; few hyperparameters
- **CMA-ES**: Covariance Matrix Adaptation Evolution Strategy; state-of-the-art for black-box continuous optimization up to ~100 dimensions
- **NSGA-II**: Multi-objective genetic algorithm; produces Pareto front of non-dominated solutions
- **Island model**: Multiple populations evolving independently with periodic migration; improves diversity

## Algorithm Selection Guide

| Problem Type | Recommended | Backup |
|-------------|-------------|--------|
| Smooth convex | Interior point / Newton | L-BFGS |
| Smooth non-convex (small dim) | L-BFGS, CMA-ES | Adam with restarts |
| Smooth non-convex (high dim) | Adam, SGD+momentum | AdaGrad |
| Combinatorial (small) | Exact solver (Gurobi) | Branch and bound |
| Combinatorial (large) | Simulated annealing | Genetic algorithm |
| Black-box expensive | Bayesian optimization | CMA-ES |
| Multi-objective | NSGA-II | Weighted sum scalarization |

## Risk Management

- **Local optima**: Non-convex problems have many; use multiple restarts (10-20) with different initial conditions
- **Hyperparameter sensitivity**: All methods sensitive to their settings; grid search or Bayesian optimization for tuning
- **Computational budget**: Set wall-clock time limit; return best solution found within budget
- **Validation**: Verify optimized solution satisfies all constraints; numerical solvers can produce infeasible points near boundaries
- **Overfitting risk**: Optimizing too many parameters on limited data = overfitting; use regularization or cross-validation
- **Scalability**: Exact methods fail at scale; heuristics sacrifice optimality for tractability; know the tradeoff
