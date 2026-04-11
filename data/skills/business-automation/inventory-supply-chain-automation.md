---
name: Inventory and Supply Chain Automation
description: Automate inventory tracking, reorder triggers, supplier communications, and demand forecasting
version: "1.0.0"
author: ROOT
tags: [business-automation, inventory, supply-chain, forecasting, procurement]
platforms: [all]
difficulty: intermediate
---

# Inventory and Supply Chain Automation

Eliminate stockouts and overstock with automated inventory tracking, intelligent
reorder triggers, and supplier communication workflows.

## Inventory Monitoring System

### Real-Time Stock Level Tracking

```python
import sqlite3
from datetime import datetime, timedelta

class InventoryTracker:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.setup_schema()

    def setup_schema(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                sku TEXT PRIMARY KEY,
                name TEXT,
                quantity INTEGER,
                reorder_point INTEGER,
                reorder_quantity INTEGER,
                lead_time_days INTEGER,
                unit_cost REAL,
                supplier_id TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS inventory_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT,
                movement_type TEXT,  -- 'sale', 'receipt', 'adjustment', 'return'
                quantity INTEGER,
                reference TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.commit()

    def record_movement(self, sku: str, movement_type: str, quantity: int, reference: str):
        """Record inventory movement and update current stock."""
        qty_delta = -quantity if movement_type == "sale" else quantity
        self.db.execute(
            "UPDATE inventory SET quantity = quantity + ?, last_updated = ? WHERE sku = ?",
            (qty_delta, datetime.now(), sku)
        )
        self.db.execute(
            "INSERT INTO inventory_movements (sku, movement_type, quantity, reference) VALUES (?,?,?,?)",
            (sku, movement_type, quantity, reference)
        )
        self.db.commit()
        self.check_reorder_trigger(sku)

    def check_reorder_trigger(self, sku: str):
        """Check if reorder point has been crossed."""
        item = self.db.execute(
            "SELECT * FROM inventory WHERE sku = ?", (sku,)
        ).fetchone()

        if item and item["quantity"] <= item["reorder_point"]:
            self.trigger_reorder(item)

    def trigger_reorder(self, item: dict):
        """Create purchase order when stock hits reorder point."""
        po = create_purchase_order(
            sku=item["sku"],
            quantity=item["reorder_quantity"],
            supplier_id=item["supplier_id"],
            urgency="high" if item["quantity"] <= item["reorder_point"] * 0.5 else "normal"
        )
        notify_purchasing_team(item, po)
        log_reorder_event(item["sku"], po["id"])
```

## Demand Forecasting

```python
import numpy as np
from scipy.stats import norm

def forecast_demand(sku: str, historical_sales: list, forecast_days: int = 30) -> dict:
    """Simple demand forecast using exponential smoothing."""
    if len(historical_sales) < 7:
        avg_daily = sum(historical_sales) / len(historical_sales)
        return {"forecast_daily": avg_daily, "confidence": "low"}

    # Exponential smoothing (alpha = 0.3)
    alpha = 0.3
    smoothed = [historical_sales[0]]
    for sale in historical_sales[1:]:
        smoothed.append(alpha * sale + (1 - alpha) * smoothed[-1])

    forecast_daily = smoothed[-1]
    forecast_total = forecast_daily * forecast_days

    # Calculate safety stock (1.65 std dev for 95% service level)
    daily_std = np.std(historical_sales[-30:]) if len(historical_sales) >= 30 else np.std(historical_sales)
    lead_time = get_supplier_lead_time(sku)
    safety_stock = 1.65 * daily_std * np.sqrt(lead_time)

    return {
        "forecast_daily": round(forecast_daily, 1),
        "forecast_30d": round(forecast_total, 0),
        "safety_stock": round(safety_stock, 0),
        "recommended_reorder_point": round(forecast_daily * lead_time + safety_stock, 0),
        "confidence": "high" if len(historical_sales) >= 90 else "medium"
    }
```

## Supplier Communication Automation

### Automated Purchase Orders

```python
def create_purchase_order(sku: str, quantity: int, supplier_id: str,
                          urgency: str = "normal") -> dict:
    """Create and send PO to supplier automatically."""
    supplier = get_supplier(supplier_id)
    item = get_inventory_item(sku)

    po_number = generate_po_number()
    expected_delivery = datetime.now() + timedelta(days=item["lead_time_days"])
    if urgency == "high":
        expected_delivery = datetime.now() + timedelta(days=max(1, item["lead_time_days"] - 2))

    po = {
        "po_number": po_number,
        "supplier": supplier,
        "items": [{
            "sku": sku,
            "name": item["name"],
            "quantity": quantity,
            "unit_price": item["unit_cost"],
            "total": quantity * item["unit_cost"]
        }],
        "total_value": quantity * item["unit_cost"],
        "expected_delivery": expected_delivery,
        "urgency": urgency,
        "created_at": datetime.now()
    }

    save_po_to_db(po)

    # Send to supplier
    if supplier["integration_type"] == "email":
        send_po_email(supplier, po)
    elif supplier["integration_type"] == "api":
        submit_po_via_api(supplier, po)
    elif supplier["integration_type"] == "edi":
        submit_po_via_edi(supplier, po)

    return po

def send_po_email(supplier: dict, po: dict):
    """Email PO to supplier with PDF attachment."""
    pdf_path = generate_po_pdf(po)
    send_email(
        to=supplier["procurement_email"],
        subject=f"Purchase Order #{po['po_number']} — {po['items'][0]['name']}",
        body=f"""Dear {supplier['contact_name']},

Please find attached Purchase Order #{po['po_number']}.

Items:
- {po['items'][0]['name']}: {po['items'][0]['quantity']} units @ ${po['items'][0]['unit_price']:.2f}
Total Value: ${po['total_value']:,.2f}

Required delivery by: {po['expected_delivery'].strftime('%B %d, %Y')}
{'URGENT - Please expedite this order.' if po['urgency'] == 'high' else ''}

Please confirm receipt and estimated delivery date by reply email.
""",
        attachment=pdf_path
    )
```

## Stockout and Overstock Alerts

```python
def daily_inventory_health_check(inventory_tracker: InventoryTracker) -> dict:
    """Daily sweep of inventory for stockouts and overstock."""
    all_items = inventory_tracker.get_all_items()
    issues = {"stockouts": [], "near_stockout": [], "overstock": []}

    for item in all_items:
        forecast = forecast_demand(item["sku"], get_recent_sales(item["sku"]))
        days_of_stock = item["quantity"] / max(forecast["forecast_daily"], 0.1)

        if item["quantity"] == 0:
            issues["stockouts"].append({**item, "days_of_stock": 0})
            send_stockout_alert(item)
        elif days_of_stock < 7:
            issues["near_stockout"].append({**item, "days_of_stock": days_of_stock})
        elif days_of_stock > 180:  # 6 months of stock
            excess_units = item["quantity"] - (forecast["forecast_daily"] * 90)
            issues["overstock"].append({**item, "excess_units": excess_units,
                                        "excess_value": excess_units * item["unit_cost"]})

    # Send daily digest
    if any(issues.values()):
        send_inventory_digest(issues)

    return issues
```

## ABC Analysis for Prioritization

```python
def abc_analysis(sales_data: pd.DataFrame) -> pd.DataFrame:
    """Classify inventory by revenue contribution (80/15/5 rule)."""
    item_revenue = sales_data.groupby("sku")["revenue"].sum().sort_values(ascending=False)
    total_revenue = item_revenue.sum()

    cumulative_pct = (item_revenue.cumsum() / total_revenue * 100)

    def classify(pct: float) -> str:
        if pct <= 80:
            return "A"  # 80% of revenue — highest priority
        elif pct <= 95:
            return "B"  # 15% of revenue — medium priority
        else:
            return "C"  # 5% of revenue — low priority, simplify

    classification = cumulative_pct.apply(classify)
    return pd.DataFrame({
        "sku": item_revenue.index,
        "annual_revenue": item_revenue.values,
        "cumulative_pct": cumulative_pct.values,
        "classification": classification.values
    })

# A items: tight stock control, frequent ordering, automated alerts
# B items: periodic review, moderate reorder points
# C items: bulk orders, simple min/max rules, consider dropshipping
```

## Metrics Dashboard

Track weekly:
- **Stockout rate**: % SKUs at zero inventory (target: < 1%)
- **Inventory turnover**: COGS / average inventory (target: 8-12x for retail)
- **Days Sales of Inventory (DSI)**: (inventory / COGS) * 365
- **Fill rate**: % orders shipped complete on first attempt (target: > 98%)
- **Carrying cost**: 20-30% of inventory value annually
- **Dead stock value**: inventory with no movement in 6+ months
