---
name: Domain-Driven Design
description: Bounded contexts, aggregates, domain events, anti-corruption layer
version: "1.0.0"
author: ROOT
tags: [architecture, DDD, bounded-context, aggregates, domain-events, anti-corruption]
platforms: [all]
---

# Domain-Driven Design

Structure software around business domains to manage complexity in systems with rich business logic.

## Bounded Contexts

### Identification
A bounded context is a boundary within which a domain model has a specific, consistent meaning.

```
E-Commerce System:
  ├── Order Context     → Order = items + shipping + payment status
  ├── Inventory Context → Order = stock reservation + warehouse location
  ├── Shipping Context  → Order = package + tracking + delivery address
  └── Billing Context   → Order = invoice + payment method + tax calculation
```

### Rules
- Same word can mean different things in different contexts ("Order" above)
- Each context owns its data and logic (no shared database between contexts)
- Communication between contexts happens via well-defined interfaces (APIs, events)
- Team ownership: one team per bounded context (Conway's Law alignment)

### Context Mapping
| Relationship | Description | Example |
|-------------|-------------|---------|
| Partnership | Two contexts cooperate and evolve together | Order + Inventory |
| Customer-Supplier | Upstream serves downstream's needs | Platform → Plugin |
| Conformist | Downstream adopts upstream's model as-is | Integrating 3rd-party API |
| Anti-Corruption Layer | Downstream translates upstream's model | Legacy system integration |
| Shared Kernel | Two contexts share a small common model | Shared value objects |
| Published Language | Context exposes a standardized schema | Public API, events |

## Aggregates

### Design Rules
- An aggregate is a cluster of entities treated as a single unit for data changes
- Every aggregate has one root entity (the only entity external code can reference)
- Transactions should not span multiple aggregates
- Keep aggregates small: prefer more small aggregates over fewer large ones

### Example
```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class OrderLine:
    product_id: str
    quantity: int
    unit_price: float

@dataclass
class Order:  # Aggregate root
    order_id: str
    customer_id: str
    lines: list[OrderLine] = field(default_factory=list)
    status: str = "draft"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_line(self, product_id: str, quantity: int, price: float):
        if self.status != "draft":
            raise ValueError("Cannot modify a submitted order")
        self.lines.append(OrderLine(product_id, quantity, price))

    def submit(self) -> list[dict]:
        if not self.lines:
            raise ValueError("Cannot submit an empty order")
        self.status = "submitted"
        return [{"type": "OrderSubmitted", "order_id": self.order_id,
                 "total": sum(l.quantity * l.unit_price for l in self.lines)}]
```

### Aggregate Sizing Heuristic
- If two entities must be consistent within a single transaction, they belong in the same aggregate
- If eventual consistency is acceptable, use separate aggregates connected by domain events
- Large aggregates cause contention (many users editing same aggregate = lock conflicts)

## Domain Events

### Event Design
```python
@dataclass(frozen=True)
class OrderSubmitted:
    event_id: str           # Unique, for idempotency
    order_id: str
    customer_id: str
    total_amount: float
    occurred_at: datetime
    line_count: int

    # Events are facts: past tense, immutable, no behavior
```

### Event Flow Between Contexts
```
Order Context                    Inventory Context
  │                                  │
  │── OrderSubmitted event ──────────→ Reserve stock
  │                                  │── StockReserved event ──→
  │                                  │
  │── OrderCancelled event ──────────→ Release stock
```

### Event Best Practices
- Name events in past tense (something that happened): `OrderSubmitted`, `PaymentFailed`
- Include enough data for consumers to act without calling back to the producer
- Version events: `OrderSubmittedV2` with backward-compatible changes
- Store events durably before publishing (outbox pattern prevents lost events)

## Anti-Corruption Layer (ACL)

### Purpose
Translate between your clean domain model and an external system's messy or incompatible model.

```python
class LegacyOrderAdapter:
    """ACL: translates between our Order model and legacy ERP system."""

    def __init__(self, legacy_client):
        self.client = legacy_client

    def create_order(self, order: Order) -> str:
        # Translate our clean model to legacy format
        legacy_payload = {
            "CUST_NO": order.customer_id,
            "ORD_DT": order.created_at.strftime("%Y%m%d"),
            "LINES": [
                {"ITEM_CD": l.product_id, "QTY": l.quantity, "PRC": l.unit_price}
                for l in order.lines
            ]
        }
        result = self.client.post("/api/v1/orders", legacy_payload)
        return result["ORDER_NO"]  # Translate back to our domain

    def get_order_status(self, legacy_order_no: str) -> str:
        raw = self.client.get(f"/api/v1/orders/{legacy_order_no}")
        # Map legacy status codes to our domain language
        status_map = {"10": "draft", "20": "submitted", "30": "shipped", "99": "cancelled"}
        return status_map.get(raw["STAT_CD"], "unknown")
```

### When to Use ACL
- Integrating with legacy systems that have incompatible data models
- Consuming third-party APIs whose model does not match your domain
- Migrating from monolith to microservices (ACL wraps the monolith)
- Protecting your model from upstream changes (ACL absorbs the impact)

## Strategic Design Process

1. **Event Storming**: Workshop to discover domain events, commands, and aggregates
2. **Context Mapping**: Identify bounded contexts and their relationships
3. **Core Domain Identification**: Which contexts provide competitive advantage? Invest most here
4. **Supporting/Generic Subdomains**: Use off-the-shelf solutions or simpler implementations
5. **Ubiquitous Language**: Ensure code uses the same terms as domain experts (no translation layer in developers' heads)
