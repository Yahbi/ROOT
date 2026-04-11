---
name: CI/CD Pipeline
description: GitHub Actions workflows, testing, linting, and automated deployment
version: "1.0.0"
author: ROOT
tags: [devops, ci-cd, github-actions, testing, deployment, automation]
platforms: [all]
---

# CI/CD Pipeline

Automate testing, building, and deployment with reliable continuous integration and delivery.

## GitHub Actions Pipeline Structure

### Recommended Workflow Stages
1. **Lint**: Code formatting and style checks (fastest, catch issues first)
2. **Test**: Unit tests, integration tests (parallelized by test type)
3. **Build**: Docker image, package artifact
4. **Deploy staging**: Automatic on merge to main
5. **Deploy production**: Manual approval or tag-triggered

### Example Workflow
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff
      - run: ruff check . && ruff format --check .

  test:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest --cov=backend --cov-report=xml -v
      - uses: codecov/codecov-action@v4

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - run: # deploy commands
```

## Testing Strategy in CI

### Test Pyramid
| Level | Count | Speed | When to Run |
|-------|-------|-------|------------|
| Unit tests | Many (70%) | Fast (< 5 min) | Every push |
| Integration tests | Some (20%) | Medium (5-15 min) | Every push |
| E2E tests | Few (10%) | Slow (15-30 min) | Main branch only |

### Optimizations
- Cache dependencies: `actions/cache` for pip, npm, Docker layers
- Parallel test execution: split test suite across multiple runners
- Skip CI for docs-only changes: `paths-ignore: ['**.md', 'docs/**']`
- Fail fast: if lint fails, don't run tests

## Deployment Strategies

### Blue-Green Deployment
- Run two identical environments (blue = current, green = new)
- Deploy to green, run smoke tests, switch traffic
- Instant rollback: switch traffic back to blue

### Rolling Deployment
- Update instances one at a time (or in small batches)
- Health check each instance before proceeding
- Slower than blue-green but requires less infrastructure

### Canary Deployment
- Route 5% of traffic to new version
- Monitor error rates and latency for 15-30 minutes
- Gradually increase to 25% → 50% → 100% if metrics are healthy
- Auto-rollback if error rate exceeds baseline + 2%

## Pipeline Best Practices

- **Keep pipelines fast**: Target < 10 minutes for PR checks (developers won't wait longer)
- **Reproducible builds**: Pin all dependency versions, use lock files
- **Secret management**: Use GitHub Secrets or Vault, never hardcode in workflow files
- **Branch protection**: Require passing CI + review before merge to main
- **Notifications**: Alert on pipeline failures (Slack, email) — don't let failures go unnoticed
- **Artifact retention**: Keep build artifacts and test reports for 30 days for debugging
