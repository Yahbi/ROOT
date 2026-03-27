---
name: tdd-workflow
description: Test-Driven Development — write tests first, then implement
version: 1.0.0
author: ROOT
tags: [tdd, testing, quality, development]
platforms: [darwin, linux, win32]
---

# Test-Driven Development

From ECC testing rules — MANDATORY workflow.

## When to Use
- Every new feature, bug fix, or refactoring task

## The Cycle

### 1. RED — Write Failing Test
```python
def test_memory_search_returns_relevant():
    engine = MemoryEngine(":memory:")
    engine.start()
    engine.store(MemoryEntry(content="Python is great", ...))
    results = engine.search(MemoryQuery(query="Python"))
    assert len(results) == 1
    assert "Python" in results[0].content
```

### 2. GREEN — Minimal Implementation
Write the minimum code to make the test pass. No more.

### 3. REFACTOR — Improve While Green
Clean up, extract helpers, improve naming — but tests must stay green.

## Coverage Requirements
- 80% minimum for all code
- 100% for: auth, security, financial, core business logic
- Required test types: unit + integration + E2E

## Edge Cases (mandatory)
- null/None input
- Empty arrays/strings
- Invalid types
- Boundary values (0, -1, MAX_INT)
- Error paths (network failures, DB errors)
- Large data (10k+ items)
