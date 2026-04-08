---
name: Technical Debt
description: Debt classification, payoff prioritization, refactoring strategies, metrics
version: "1.0.0"
author: ROOT
tags: [leadership, technical-debt, refactoring, code-quality, prioritization]
platforms: [all]
---

# Technical Debt

Manage technical debt systematically instead of letting it accumulate into a crisis.

## Debt Classification

### Types of Technical Debt
| Type | Description | Example |
|------|-------------|---------|
| **Deliberate-prudent** | Conscious shortcut with a plan to fix | "Ship now, refactor next sprint" |
| **Deliberate-reckless** | Known shortcuts with no fix plan | "We don't have time for tests" |
| **Inadvertent-prudent** | Learned better approach after shipping | "Now that we know the domain, this model is wrong" |
| **Inadvertent-reckless** | Bad design due to lack of knowledge | Junior developer's first distributed system |

### Common Debt Sources
- **Code debt**: Duplicated logic, unclear naming, missing abstractions, no tests
- **Architecture debt**: Wrong database choice, monolith that should be services, tight coupling
- **Infrastructure debt**: Manual deployments, no monitoring, fragile CI/CD, outdated dependencies
- **Documentation debt**: Missing onboarding docs, outdated API docs, no runbooks
- **Test debt**: Low coverage, flaky tests, no integration tests, slow test suite

## Debt Assessment

### Inventory Method
```markdown
# Technical Debt Register

| ID | Area | Description | Impact (1-5) | Effort (S/M/L/XL) | Interest Rate |
|----|------|-------------|-------------|-------------------|---------------|
| TD-001 | Auth | Passwords stored with MD5 | 5 (security) | M (2 sprints) | Critical |
| TD-002 | API | No pagination on list endpoints | 3 (performance) | S (2 days) | Growing |
| TD-003 | Tests | No integration tests for payments | 4 (reliability) | L (1 month) | Stable |
| TD-004 | Deploy | Manual deploy process | 3 (productivity) | M (2 weeks) | Growing |
```

### Interest Rate Concept
- **Growing interest**: Gets worse over time (more code built on bad foundation, more devs affected)
- **Stable interest**: Stays the same (isolated bad code that rarely changes)
- **Declining interest**: System being replaced anyway (legacy code with sunset date)
- Prioritize growing-interest debt because delay increases total cost

## Prioritization

### Cost-of-Delay Framework
```
Priority Score = (Impact × Interest Rate) / Effort

Impact: How much does this slow down the team? (1-5)
Interest Rate: How fast is the cost growing? (1=stable, 3=fast)
Effort: Story points or t-shirt size converted to number

Example:
  TD-001 (MD5 passwords): (5 × 3) / 4 = 3.75  → Fix first
  TD-004 (manual deploy): (3 × 2) / 6 = 1.00  → Schedule
  TD-003 (no tests):      (4 × 1) / 8 = 0.50  → Backlog
```

### When to Pay Down Debt
- **Fix it now**: Security vulnerabilities, data integrity risks, blocking other work
- **Allocate budget**: Reserve 15-20% of each sprint for debt reduction (not negotiable)
- **Boy Scout Rule**: Leave code cleaner than you found it (small improvements alongside features)
- **Strangler Fig**: When touching old code for features, refactor the touched area

## Refactoring Strategies

### Safe Refactoring Approach
1. **Characterization tests**: Write tests that capture current behavior before changing anything
2. **Small steps**: One refactoring per commit (rename, extract, inline — never multiple)
3. **Feature flag**: Deploy refactored code behind a flag, validate, then switch
4. **Parallel run**: Run old and new code simultaneously, compare outputs, switch when confident

### Common Refactoring Patterns
| Pattern | When | Technique |
|---------|------|-----------|
| Extract module | Class/file > 500 lines | Identify cohesive groups, move to new module |
| Replace conditional with polymorphism | Long if/elif chains on type | Create class hierarchy or strategy pattern |
| Introduce domain types | Primitive obsession (strings for everything) | Create value objects (Email, Money, UserId) |
| Strangler fig | Rewriting large component | New code handles new cases, old code shrinks over time |
| Database migration | Schema no longer fits domain | Expand-contract: add new columns, migrate data, remove old |

## Metrics

### Tracking Debt Over Time
| Metric | Tool | Target |
|--------|------|--------|
| Code complexity (cyclomatic) | radon, SonarQube | < 10 per function |
| Test coverage | pytest-cov, coverage.py | > 80% (not 100%) |
| Dependency freshness | Dependabot, Renovate | No deps > 6 months behind |
| Deploy frequency | CI/CD metrics | Daily or more |
| Lead time for changes | DORA metrics | < 1 day (elite) |
| Flaky test rate | CI dashboard | < 1% of test runs |

### Communicating Debt to Non-Technical Stakeholders
- Frame as velocity impact: "This debt adds 2 days to every feature in this area"
- Frame as risk: "Without this fix, a security breach could cost $X"
- Frame as opportunity cost: "Paying this debt lets us ship Feature Y 3 weeks faster"
- Never use the word "refactoring" with business stakeholders (say "modernization" or "risk reduction")
