---
name: Refactoring
description: Code smells, extract method, SOLID principles, and safe refactoring techniques
version: "1.0.0"
author: ROOT
tags: [coding-standards, refactoring, code-smells, SOLID, clean-code]
platforms: [all]
---

# Refactoring

Improve code structure without changing behavior, guided by code smells and design principles.

## Code Smells and Fixes

### Function-Level Smells
| Smell | Symptom | Refactoring |
|-------|---------|-------------|
| Long function | > 30 lines | Extract Method — pull out logical blocks |
| Long parameter list | > 4 parameters | Introduce Parameter Object or config dict |
| Duplicated code | Same logic in 2+ places | Extract shared function |
| Complex conditionals | Nested if/else 3+ levels deep | Extract conditions to named functions, use early returns |
| Magic numbers | `if status == 3` | Replace with named constants or enums |
| Dead code | Unused functions, commented-out code | Delete it (git remembers) |

### Class-Level Smells
| Smell | Symptom | Refactoring |
|-------|---------|-------------|
| God class | Class does everything (500+ lines) | Split by responsibility |
| Feature envy | Method uses another class's data more than its own | Move method to that class |
| Data clump | Same group of fields passed together | Create a class/dataclass for the group |
| Primitive obsession | Using strings for everything | Create domain types (Email, Money, etc.) |

## SOLID Principles

### S — Single Responsibility
- A class should have one reason to change
- If you need the word "and" to describe what a class does, split it
- Example: `UserService` handles users; `EmailService` handles emails — not one class for both

### O — Open/Closed
- Open for extension, closed for modification
- Add new behavior by adding new code, not modifying existing code
- Use composition, strategy pattern, or plugin architectures

### L — Liskov Substitution
- Subtypes must be substitutable for their base types
- If `Dog` extends `Animal`, anywhere `Animal` works, `Dog` should work too
- Don't override methods with incompatible behavior

### I — Interface Segregation
- Don't force classes to implement interfaces they don't use
- Many small, focused interfaces beat one large interface
- Example: `Readable` and `Writable` instead of `ReadWritable`

### D — Dependency Inversion
- Depend on abstractions, not concrete implementations
- Pass dependencies in (injection), don't create them internally
- Makes code testable (inject mocks) and flexible (swap implementations)

## Safe Refactoring Process

### Steps
1. **Verify test coverage**: Ensure tests exist for the code you're changing
2. **Make one small change**: Rename, extract method, move function — one at a time
3. **Run tests**: Verify nothing broke
4. **Commit**: Each refactoring step gets its own commit
5. **Repeat**: Continue with next small change

### Rules
- Never refactor and add features in the same commit
- If tests don't exist, write them first (characterization tests)
- Refactor in small steps — never "big bang" rewrite (high risk of introducing bugs)
- If the refactoring makes tests harder to write, reconsider the approach

## Common Refactoring Techniques

### Extract Method
```python
# Before: long function with mixed concerns
def process_order(order):
    # validation (10 lines)
    # calculation (15 lines)
    # notification (10 lines)

# After: clear, named steps
def process_order(order):
    validate_order(order)
    total = calculate_total(order)
    notify_customer(order, total)
```

### Replace Conditional with Polymorphism
```python
# Before: if/elif chain
if payment_type == "credit":
    process_credit(amount)
elif payment_type == "debit":
    process_debit(amount)

# After: strategy pattern
payment_processor = get_processor(payment_type)
payment_processor.process(amount)
```

### Introduce Early Returns
```python
# Before: deeply nested
def process(data):
    if data:
        if data.valid:
            if data.ready:
                return handle(data)

# After: guard clauses
def process(data):
    if not data: return None
    if not data.valid: return None
    if not data.ready: return None
    return handle(data)
```
