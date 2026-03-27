---
name: immutable-patterns
description: Always create new objects instead of mutating existing ones
version: 1.0.0
author: ROOT
tags: [immutability, coding, quality, patterns]
platforms: [darwin, linux, win32]
---

# Immutable Patterns

From ECC coding-style rules — CRITICAL requirement.

## When to Use
- Always. This is a default behavior, not optional.

## Core Rule
NEVER mutate existing objects. Always create new copies with changes.

## Python
```python
# WRONG
user["name"] = "new_name"
items.append(new_item)

# CORRECT
updated_user = {**user, "name": "new_name"}
updated_items = [*items, new_item]

# Pydantic
updated = model.model_copy(update={"field": new_value})
```

## Why
- Prevents hidden side effects
- Makes debugging easier (state is traceable)
- Enables safe concurrency
- Functions become predictable (same input → same output)

## Exceptions
- Performance-critical inner loops (document the mutation)
- Builder patterns during construction (freeze before returning)
- SQLite connections and file handles (inherently stateful)
