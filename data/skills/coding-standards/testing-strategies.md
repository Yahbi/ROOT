---
name: Testing Strategies
description: Unit, integration, E2E testing, mocking, TDD, and coverage best practices
version: "1.0.0"
author: ROOT
tags: [coding-standards, testing, TDD, mocking, unit-test, integration]
platforms: [all]
---

# Testing Strategies

Build confidence in your code through layered testing at the right granularity.

## Test Pyramid

### Layers
| Layer | Count | Speed | Scope | Confidence |
|-------|-------|-------|-------|------------|
| Unit | Many (70%) | < 10ms each | Single function/class | Correct logic |
| Integration | Some (20%) | 100ms-1s each | Multiple components | Components work together |
| E2E | Few (10%) | 1-30s each | Full system | User workflows work |

### Why This Shape
- Unit tests: fast feedback, cheap to write, easy to debug failures
- Integration tests: catch interface mismatches, test real dependencies
- E2E tests: validate critical user journeys, expensive to maintain
- Invert the pyramid (many E2E, few unit) = slow, flaky, hard to debug

## Unit Testing Best Practices

### Test Structure (AAA Pattern)
```python
def test_calculate_position_size():
    # Arrange
    account_balance = 100_000
    risk_percent = 0.02
    stop_loss_distance = 5.0

    # Act
    size = calculate_position_size(account_balance, risk_percent, stop_loss_distance)

    # Assert
    assert size == 400  # $2000 risk / $5 stop = 400 shares
```

### What to Test
- Happy path: expected inputs produce expected outputs
- Edge cases: empty inputs, zero values, boundary conditions
- Error cases: invalid inputs raise appropriate exceptions
- State changes: verify side effects (database writes, API calls)

### What NOT to Test
- Private implementation details (test behavior, not structure)
- Third-party library internals (trust their tests)
- Trivial code (getters, setters with no logic)

## Mocking

### When to Mock
- External APIs (HTTP services, databases, file systems)
- Non-deterministic behavior (time, random, UUIDs)
- Slow or expensive operations (ML model inference, email sending)
- Dependencies that don't exist yet

### When NOT to Mock
- Your own code (test the real implementation when possible)
- Data structures and simple utilities
- Everything — over-mocking creates tests that pass but code that breaks

### Mock Patterns (Python)
```python
from unittest.mock import AsyncMock, patch

@patch("backend.services.llm.call_api", new_callable=AsyncMock)
async def test_brain_handles_llm_failure(mock_api):
    mock_api.side_effect = LLMUnavailableError("API down")
    result = await brain.process("test query")
    assert result.source == "offline_brain"
```

## Test-Driven Development (TDD)

### Red-Green-Refactor Cycle
1. **Red**: Write a failing test for the desired behavior
2. **Green**: Write the minimum code to make the test pass
3. **Refactor**: Improve the code while keeping tests green
4. Repeat for each new behavior

### When TDD Works Best
- Clear requirements (you know what "correct" looks like)
- Complex business logic (edge cases are easy to miss)
- Bug fixes (write test that reproduces the bug first, then fix)

## Coverage

### Guidelines
- Target: 80% line coverage (diminishing returns above 90%)
- Coverage measures lines executed, not correctness — 100% coverage ≠ no bugs
- Focus on critical path coverage, not vanity metrics
- Uncovered lines should be intentional (error handlers, defensive code)

### Measuring
```bash
pytest --cov=backend --cov-report=html -v
# Open htmlcov/index.html to see line-by-line coverage
```

## Test Quality Checklist

- [ ] Tests run fast (full suite < 5 minutes)
- [ ] Tests are independent (no shared state, any order works)
- [ ] Test names describe the behavior being tested
- [ ] Failures produce clear error messages (expected vs actual)
- [ ] No flaky tests (if one exists, fix or delete it immediately)
- [ ] CI runs tests on every PR, blocks merge on failure
