---
name: Type Safety
description: mypy, Pydantic, runtime validation, Protocol classes, Generic types
version: "1.0.0"
author: ROOT
tags: [coding-standards, python, type-safety, mypy, pydantic, generics]
platforms: [all]
---

# Type Safety

Catch bugs at development time through static type checking and enforce data contracts at runtime.

## Static Type Checking with mypy

### Configuration
```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
strict = true                          # Enable all strict checks
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true           # Every function must have type annotations
disallow_any_generics = true           # No bare List, Dict — use List[str], Dict[str, int]
check_untyped_defs = true
no_implicit_reexport = true

# Per-module overrides for third-party libs without stubs
[[tool.mypy.overrides]]
module = ["aiohttp.*", "alpaca_trade_api.*"]
ignore_missing_imports = true
```

### Common Type Patterns
```python
from typing import Optional, TypeAlias, Literal

# Use | syntax (Python 3.10+) over Optional
def get_user(user_id: str) -> dict[str, str] | None: ...

# TypeAlias for complex types
JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None

# Literal for constrained string values
def set_log_level(level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]) -> None: ...

# TypedDict for structured dictionaries
from typing import TypedDict

class UserResponse(TypedDict):
    id: str
    name: str
    email: str
    active: bool
```

### Gradual Adoption Strategy
1. Add `mypy` to CI with `--ignore-missing-imports` (zero errors from day 1)
2. Add type annotations to new code only (do not rewrite existing code)
3. Run `mypy --strict` on new modules, relaxed on legacy modules
4. Use `# type: ignore[error-code]` sparingly with a comment explaining why

## Pydantic for Runtime Validation

### Model Definition
```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class MemoryEntry(BaseModel, frozen=True):  # Immutable
    content: str = Field(min_length=1, max_length=10000)
    category: str = Field(pattern=r"^[a-z_]+$")
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    tags: list[str] = Field(default_factory=list, max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("tags")
    @classmethod
    def lowercase_tags(cls, v: list[str]) -> list[str]:
        return [tag.lower().strip() for tag in v]
```

### Pydantic vs dataclasses vs TypedDict
| Feature | Pydantic | dataclass | TypedDict |
|---------|----------|-----------|-----------|
| Runtime validation | Yes (automatic) | No | No |
| Serialization (JSON) | Built-in | Manual | Manual |
| Default values | Yes | Yes | Yes |
| Immutability | `frozen=True` | `frozen=True` | N/A |
| Performance | Good (v2 is Rust-based) | Best (no validation) | Best (just a dict) |
| Use case | API boundaries, config | Internal data, simple DTOs | Type hints for dicts |

### Best Practice
- Use Pydantic at system boundaries (API input/output, config files, external data)
- Use frozen dataclasses for internal domain objects
- Use TypedDict only for type-hinting dictionary shapes in existing code

## Protocol Classes (Structural Typing)

### Define Interfaces Without Inheritance
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class MessageStore(Protocol):
    async def save(self, message: str, metadata: dict) -> str: ...
    async def get(self, message_id: str) -> dict | None: ...
    async def search(self, query: str, limit: int = 10) -> list[dict]: ...

# Any class implementing these methods satisfies the Protocol
# No inheritance required (duck typing with type safety)
class SQLiteMessageStore:
    async def save(self, message: str, metadata: dict) -> str:
        ...  # Implementation
    async def get(self, message_id: str) -> dict | None:
        ...
    async def search(self, query: str, limit: int = 10) -> list[dict]:
        ...

def process(store: MessageStore) -> None:  # Accepts any conforming class
    ...
```

### When to Use Protocol vs ABC
- **Protocol**: When you want structural typing (no forced inheritance), third-party compatibility
- **ABC**: When you need shared implementation (mixins) or want to enforce subclass registration

## Generic Types

### Creating Generic Classes
```python
from typing import Generic, TypeVar

T = TypeVar("T")

class Repository(Generic[T]):
    def __init__(self, model_class: type[T]):
        self.model_class = model_class

    async def get(self, id: str) -> T | None: ...
    async def save(self, entity: T) -> T: ...
    async def list_all(self) -> list[T]: ...

# Usage: type-safe at every call site
user_repo = Repository(User)       # Repository[User]
order_repo = Repository(Order)     # Repository[Order]
user: User | None = await user_repo.get("123")  # mypy knows this is User | None
```

### Bounded TypeVar
```python
from typing import TypeVar

# Constrain T to specific types
Numeric = TypeVar("Numeric", int, float)

def clamp(value: Numeric, min_val: Numeric, max_val: Numeric) -> Numeric:
    return max(min_val, min(value, max_val))
```

## CI Integration

### Pre-Commit Type Checking
```yaml
# .pre-commit-config.yaml
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.10.0
  hooks:
    - id: mypy
      additional_dependencies: [pydantic, types-requests]
      args: [--strict]
```

- Run mypy in CI: fail the build on type errors (same as test failures)
- Use `reveal_type(expr)` during development to debug inferred types
- Integrate with IDE (VS Code: Pylance, PyCharm: built-in) for real-time feedback
