---
name: Invoicing and Payment Automation
description: Automate invoice generation, payment collection, dunning sequences, and revenue reconciliation
version: "1.0.0"
author: ROOT
tags: [business-automation, invoicing, payments, stripe, dunning, accounts-receivable]
platforms: [all]
difficulty: intermediate
---

# Invoicing and Payment Automation

Eliminate manual billing tasks and reduce DSO (Days Sales Outstanding) through
automated invoice creation, payment reminders, and failed payment recovery.

## Invoice Generation Automation

### Stripe + Python Invoice Pipeline

```python
import stripe

stripe.api_key = STRIPE_SECRET_KEY

def create_and_send_invoice(customer_id: str, line_items: list,
                             due_days: int = 30, memo: str = "") -> dict:
    """Create, finalize, and send invoice automatically."""
    # Create draft invoice
    invoice = stripe.Invoice.create(
        customer=customer_id,
        collection_method="send_invoice",
        days_until_due=due_days,
        description=memo,
        auto_advance=False,  # Don't finalize yet
        metadata={"created_by": "automation", "source": "crm"}
    )

    # Add line items
    for item in line_items:
        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice.id,
            amount=int(item["amount"] * 100),  # Stripe uses cents
            currency="usd",
            description=item["description"],
        )

    # Finalize and send
    finalized = stripe.Invoice.finalize_invoice(invoice.id)
    sent = stripe.Invoice.send_invoice(invoice.id)

    return {
        "invoice_id": invoice.id,
        "invoice_url": finalized.hosted_invoice_url,
        "pdf_url": finalized.invoice_pdf,
        "amount_due": finalized.amount_due / 100,
        "due_date": datetime.fromtimestamp(finalized.due_date)
    }

def create_recurring_subscription(customer_id: str, price_id: str,
                                   trial_days: int = 0) -> dict:
    """Set up recurring subscription with automatic billing."""
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        trial_period_days=trial_days,
        payment_settings={
            "save_default_payment_method": "on_subscription"
        },
        collection_method="charge_automatically"
    )
    return {"subscription_id": subscription.id, "status": subscription.status}
```

## Dunning Automation (Failed Payment Recovery)

Failed payments are recoverable revenue. A systematic dunning sequence recovers 40-60%
of initially failed payments.

### Dunning Sequence Design

```python
DUNNING_SEQUENCE = [
    {"day": 0,  "action": "payment_failed_email", "retry": True,
     "message": "Your payment failed — please update your card"},
    {"day": 3,  "action": "retry_payment", "template": "payment_retry_1",
     "message": "We'll retry your payment in 3 days"},
    {"day": 7,  "action": "retry_payment", "template": "payment_retry_2",
     "message": "Final retry — account at risk of suspension"},
    {"day": 10, "action": "soft_suspension", "template": "access_warning",
     "message": "Account suspended — restore access by updating billing"},
    {"day": 14, "action": "hard_suspension", "template": "churn_prevention",
     "message": "Account deactivated — reactivate anytime"},
    {"day": 21, "action": "churn_email", "template": "win_back",
     "message": "We miss you — here's a discount to come back"},
]

class DunningAutomation:
    def process_failed_payment(self, invoice_id: str, customer_id: str):
        """Start dunning sequence for failed payment."""
        customer = self.get_customer(customer_id)
        failure_date = datetime.now()

        for step in DUNNING_SEQUENCE:
            trigger_date = failure_date + timedelta(days=step["day"])
            self.schedule_dunning_step(
                customer_id=customer_id,
                invoice_id=invoice_id,
                step=step,
                trigger_date=trigger_date
            )

    def execute_dunning_step(self, step: dict, customer_id: str, invoice_id: str):
        """Execute a specific dunning step."""
        if step["action"] == "retry_payment":
            result = self.retry_stripe_payment(invoice_id)
            if result["status"] == "paid":
                self.cancel_remaining_dunning(invoice_id)
                self.send_payment_success_email(customer_id)
                return "recovered"

        elif step["action"] in ("soft_suspension", "hard_suspension"):
            self.suspend_customer_access(customer_id, step["action"])

        # Send email for all steps
        self.send_dunning_email(customer_id, step["template"])
        return "scheduled"
```

### Stripe Webhook Handler

```python
from fastapi import FastAPI, Request, HTTPException
import hmac, hashlib

app = FastAPI()

@app.post("/webhooks/stripe")
async def handle_stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        dunning.process_failed_payment(invoice["id"], invoice["customer"])

    elif event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        dunning.cancel_remaining_dunning(invoice["id"])
        revenue_tracker.record_payment(invoice)

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        handle_churn(subscription["customer"])

    return {"status": "processed"}
```

## Revenue Reconciliation

```python
def daily_revenue_reconciliation() -> dict:
    """Reconcile Stripe payments with accounting system."""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # Pull all Stripe transactions
    charges = stripe.Charge.list(
        created={"gte": int(yesterday.timestamp()),
                 "lt": int(today.timestamp())},
        limit=100
    )

    stripe_total = sum(c.amount for c in charges.auto_paging_iter()
                       if c.status == "succeeded") / 100

    # Pull accounting system total
    accounting_total = accounting_system.get_daily_revenue(yesterday)

    discrepancy = abs(stripe_total - accounting_total)

    if discrepancy > 1.00:  # > $1 discrepancy
        alert_finance_team(
            message=f"Revenue reconciliation discrepancy: Stripe=${stripe_total:.2f}, "
                    f"Accounting=${accounting_total:.2f}, Gap=${discrepancy:.2f}",
            severity="medium" if discrepancy < 100 else "high"
        )

    return {
        "date": str(yesterday),
        "stripe_revenue": stripe_total,
        "accounting_revenue": accounting_total,
        "discrepancy": discrepancy,
        "reconciled": discrepancy <= 1.00
    }
```

## Accounts Receivable Automation

```python
def overdue_invoice_management():
    """Daily AR sweep — escalate and follow up on overdue invoices."""
    overdue_invoices = stripe.Invoice.list(
        status="open",
        due_date={"lt": int(datetime.now().timestamp())}
    )

    for invoice in overdue_invoices.auto_paging_iter():
        days_overdue = (datetime.now() - datetime.fromtimestamp(invoice.due_date)).days
        customer = stripe.Customer.retrieve(invoice.customer)

        if days_overdue == 1:
            send_gentle_reminder(customer, invoice)
        elif days_overdue == 7:
            send_urgent_reminder(customer, invoice)
            create_ar_task(invoice, priority="medium")
        elif days_overdue == 14:
            escalate_to_finance(customer, invoice)
            apply_late_fee(invoice)
        elif days_overdue == 30:
            send_collections_warning(customer, invoice)
            flag_for_collections(invoice)
```

## Key Metrics to Track

```python
FINANCIAL_METRICS = {
    "dso": "Average days from invoice to payment (target < 30)",
    "collection_rate": "% invoices paid (target > 95%)",
    "dunning_recovery_rate": "% failed payments recovered (target > 50%)",
    "mrr": "Monthly recurring revenue",
    "churn_rate": "% MRR lost per month (target < 2%)",
    "expansion_mrr": "MRR from upgrades and upsells",
    "net_revenue_retention": "MRR retained including expansion (target > 110%)"
}
```
