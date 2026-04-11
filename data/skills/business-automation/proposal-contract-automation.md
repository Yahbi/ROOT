---
name: Proposal and Contract Automation
description: Automate proposal generation, e-signature workflows, and contract management
version: "1.0.0"
author: ROOT
tags: [business-automation, proposals, contracts, e-signature, DocuSign, PandaDoc]
platforms: [all]
difficulty: beginner
---

# Proposal and Contract Automation

Reduce proposal turnaround from days to minutes and eliminate manual contract
tracking with automated e-signature workflows.

## Proposal Generation System

### AI-Powered Proposal Builder

```python
from anthropic import Anthropic
from jinja2 import Template

client = Anthropic()

def generate_proposal(opportunity: dict) -> str:
    """Generate customized proposal from CRM opportunity data."""
    # 1. Generate customized executive summary
    exec_summary = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Write a compelling executive summary for a sales proposal.

Company: {opportunity['company_name']}
Industry: {opportunity['industry']}
Challenge they described: {opportunity['pain_points']}
Our proposed solution: {opportunity['products']}
Expected ROI: {opportunity['roi_estimate']}
Budget range: {opportunity['budget']}

Write 2-3 paragraphs that demonstrate understanding of their business and position
our solution as the clear choice. Professional tone, specific to their situation.
"""
        }]
    ).content[0].text

    # 2. Merge into proposal template
    template = Template(PROPOSAL_TEMPLATE)
    proposal_html = template.render(
        company_name=opportunity["company_name"],
        contact_name=opportunity["contact_name"],
        exec_summary=exec_summary,
        pricing_table=build_pricing_table(opportunity["products"], opportunity["quantity"]),
        case_studies=get_relevant_case_studies(opportunity["industry"]),
        valid_until=(datetime.now() + timedelta(days=30)).strftime("%B %d, %Y"),
    )

    return proposal_html
```

### Pricing Table Generator

```python
PRODUCT_CATALOG = {
    "starter": {"monthly": 99, "annual": 79, "users": 5, "features": ["Core", "Email"]},
    "growth": {"monthly": 299, "annual": 239, "users": 25, "features": ["Core", "Email", "API"]},
    "enterprise": {"monthly": 999, "annual": 799, "users": "Unlimited", "features": ["All"]},
}

def build_pricing_table(products: list, quantity: int, billing: str = "annual") -> dict:
    """Build pricing table with volume discounts."""
    volume_discount = 0.10 if quantity >= 100 else 0.05 if quantity >= 50 else 0

    line_items = []
    total = 0
    for product_name in products:
        product = PRODUCT_CATALOG[product_name]
        unit_price = product[billing]
        discounted_price = unit_price * (1 - volume_discount)
        line_total = discounted_price * quantity
        total += line_total
        line_items.append({
            "name": product_name.title(),
            "quantity": quantity,
            "unit_price": unit_price,
            "discount": f"{volume_discount*100:.0f}%",
            "discounted_price": discounted_price,
            "total": line_total
        })

    return {
        "line_items": line_items,
        "subtotal": total,
        "billing_period": billing,
        "total_savings": sum(p["monthly"] - p[billing] for p in
                            [PRODUCT_CATALOG[n] for n in products]) * quantity * 12
    }
```

## PandaDoc Integration

```python
import requests

class PandaDocClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.pandadoc.com/public/v1"
        self.headers = {
            "Authorization": f"API-Key {api_key}",
            "Content-Type": "application/json"
        }

    def create_from_template(self, template_id: str, opportunity: dict) -> dict:
        """Create document from template with CRM data."""
        payload = {
            "name": f"Proposal - {opportunity['company_name']} - {datetime.now().strftime('%Y-%m')}",
            "template_uuid": template_id,
            "recipients": [
                {
                    "email": opportunity["contact_email"],
                    "first_name": opportunity["contact_first_name"],
                    "last_name": opportunity["contact_last_name"],
                    "role": "client",
                },
                {
                    "email": opportunity["ae_email"],
                    "first_name": opportunity["ae_name"].split()[0],
                    "role": "sales_rep",
                }
            ],
            "tokens": [
                {"name": "Company.Name", "value": opportunity["company_name"]},
                {"name": "Deal.Value", "value": f"${opportunity['amount']:,}"},
                {"name": "Contract.StartDate", "value": opportunity["start_date"]},
                {"name": "Proposal.ValidUntil", "value": opportunity["valid_until"]},
            ],
            "fields": opportunity.get("custom_fields", {}),
            "metadata": {"deal_id": opportunity["crm_deal_id"]}
        }
        response = requests.post(f"{self.base_url}/documents", json=payload,
                                 headers=self.headers)
        return response.json()

    def send_for_signature(self, document_id: str, message: str = "") -> dict:
        """Send document for e-signature."""
        return requests.post(
            f"{self.base_url}/documents/{document_id}/send",
            json={"message": message, "silent": False},
            headers=self.headers
        ).json()

    def get_document_status(self, document_id: str) -> dict:
        """Poll document status for completion tracking."""
        return requests.get(
            f"{self.base_url}/documents/{document_id}",
            headers=self.headers
        ).json()
```

## Contract Lifecycle Management

### Status Tracking and Automation

```python
CONTRACT_WORKFLOW = {
    "draft": {
        "next_states": ["sent"],
        "actions": ["review_internally", "get_legal_approval"]
    },
    "sent": {
        "next_states": ["viewed", "signed", "declined"],
        "sla_hours": 72,
        "on_timeout": "send_reminder"
    },
    "viewed": {
        "next_states": ["signed", "declined"],
        "sla_hours": 48,
        "on_timeout": "alert_ae"
    },
    "signed": {
        "next_states": ["active"],
        "actions": ["update_crm", "trigger_onboarding", "create_invoice"]
    },
    "declined": {
        "actions": ["alert_ae", "create_follow_up_task", "log_rejection_reason"]
    }
}

def handle_signature_webhook(event: dict):
    """Process PandaDoc/DocuSign webhook events."""
    doc_id = event["document_id"]
    new_status = event["status"]

    contract = get_contract_from_db(doc_id)
    workflow_step = CONTRACT_WORKFLOW.get(new_status, {})

    for action in workflow_step.get("actions", []):
        execute_contract_action(action, contract)

    if new_status == "signed":
        # Trigger full post-close automation
        trigger_post_close_automation(contract)

def trigger_post_close_automation(contract: dict):
    """All actions triggered immediately upon signature."""
    # 1. Update CRM deal stage
    update_deal_stage(contract["crm_deal_id"], "Closed Won")

    # 2. Create invoice
    create_invoice(
        customer=contract["customer"],
        amount=contract["value"],
        due_date=contract["payment_terms"]
    )

    # 3. Trigger onboarding
    trigger_cs_handoff(contract["crm_deal_id"])

    # 4. Send welcome email
    send_welcome_email(contract["customer_email"], contract["products"])

    # 5. Notify team in Slack
    post_slack_celebration(contract["company_name"], contract["value"])
```

## Renewal Automation

```python
def schedule_renewal_campaign(contract: dict):
    """Schedule renewal outreach 90, 60, 30 days before expiry."""
    expiry = contract["end_date"]

    for days_before, template in [
        (90, "renewal_early_notification"),
        (60, "renewal_proposal"),
        (30, "renewal_urgency"),
        (14, "renewal_final"),
    ]:
        send_date = expiry - timedelta(days=days_before)
        if send_date > datetime.now():
            schedule_email(
                to=contract["customer_email"],
                send_at=send_date,
                template=template,
                variables={"contract_id": contract["id"], "expiry": expiry}
            )

    # Auto-create renewal task for AE at 90 days
    create_crm_task(
        owner=contract["ae_email"],
        subject=f"Renewal: {contract['company_name']} expires {expiry.strftime('%b %d')}",
        due_date=expiry - timedelta(days=90)
    )
```
