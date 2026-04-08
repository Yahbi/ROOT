---
name: Customer Support Automation
description: Automate tier-1 support with AI triage, FAQ deflection, and intelligent routing
version: "1.0.0"
author: ROOT
tags: [business-automation, customer-support, AI, chatbot, ticketing, deflection]
platforms: [all]
difficulty: intermediate
---

# Customer Support Automation

Reduce support costs and improve response times by automating common inquiries
while preserving high-quality human support for complex issues.

## Support Automation Tiers

```
Tier 0 (Self-Service):  FAQ, knowledge base, chatbot — 0 human involvement
Tier 1 (AI-Assisted):   AI draft + human review — < 5 min response
Tier 2 (Human Expert):  Complex/escalated issues — < 4 hour response
Tier 3 (Engineering):   Bugs, incidents — < 1 day response
```

## AI Triage System

### Intent Classification

```python
from anthropic import Anthropic

client = Anthropic()

SUPPORT_INTENTS = [
    "billing_question", "technical_issue", "feature_request",
    "account_access", "cancellation", "refund_request",
    "general_how_to", "bug_report", "complaint", "other"
]

def classify_support_ticket(ticket_text: str) -> dict:
    """Classify intent, urgency, and required expertise."""
    response = client.messages.create(
        model="claude-haiku-20240307",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""Classify this support ticket. Return JSON only.

Ticket: {ticket_text}

Return: {{
  "intent": one of {SUPPORT_INTENTS},
  "urgency": "low|medium|high|critical",
  "sentiment": "frustrated|neutral|positive",
  "can_auto_resolve": true|false,
  "confidence": 0.0-1.0,
  "routing": "self_service|tier_1|tier_2|tier_3"
}}"""
        }]
    )
    return json.loads(response.content[0].text)
```

### Auto-Resolution for FAQ

```python
def attempt_auto_resolution(ticket: dict, knowledge_base_client) -> dict:
    """Try to resolve ticket automatically using knowledge base."""
    # 1. Semantic search in knowledge base
    similar_articles = knowledge_base_client.search(
        query=ticket["text"],
        top_k=3,
        filters={"category": ticket["intent"]}
    )

    if not similar_articles or similar_articles[0]["score"] < 0.85:
        return {"resolved": False, "reason": "No confident knowledge base match"}

    # 2. Generate tailored response
    context = "\n\n".join([a["content"] for a in similar_articles])
    response = client.messages.create(
        model="claude-haiku-20240307",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""You are a helpful support agent for {COMPANY_NAME}.
Answer the customer's question using ONLY the provided knowledge base articles.
If you cannot fully answer, say so and offer to escalate.

Knowledge Base:
{context}

Customer Question: {ticket['text']}

Write a helpful, friendly, professional response:"""
        }]
    )

    return {
        "resolved": True,
        "response": response.content[0].text,
        "source_articles": [a["id"] for a in similar_articles],
        "confidence": similar_articles[0]["score"]
    }
```

## Ticketing System Integration

### Zendesk Automation

```python
import requests

class ZendeskAutomation:
    def __init__(self, subdomain: str, email: str, api_token: str):
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.auth = (f"{email}/token", api_token)

    def create_ticket_with_draft(self, ticket_data: dict, ai_draft: str) -> dict:
        """Create ticket and attach AI-generated draft response."""
        ticket = requests.post(
            f"{self.base_url}/tickets",
            json={
                "ticket": {
                    "subject": ticket_data["subject"],
                    "comment": {"body": ticket_data["body"]},
                    "requester_id": ticket_data["requester_id"],
                    "priority": ticket_data["urgency"],
                    "tags": [ticket_data["intent"]],
                    "custom_fields": [
                        {"id": AI_DRAFT_FIELD_ID, "value": ai_draft},
                        {"id": INTENT_FIELD_ID, "value": ticket_data["intent"]},
                        {"id": AUTO_RESOLVED_FIELD_ID, "value": ticket_data["auto_resolved"]}
                    ]
                }
            },
            auth=self.auth
        ).json()

        return ticket["ticket"]

    def route_ticket(self, ticket_id: int, routing: str, group_mapping: dict):
        """Route ticket to appropriate team based on classification."""
        group_id = group_mapping.get(routing)
        if group_id:
            requests.put(
                f"{self.base_url}/tickets/{ticket_id}",
                json={"ticket": {"group_id": group_id}},
                auth=self.auth
            )
```

## Response Template Library

```python
RESPONSE_TEMPLATES = {
    "password_reset": """
Hi {customer_name},

You can reset your password at: {reset_link}

Steps:
1. Click the link above
2. Enter your email address
3. Check your email for a reset link
4. Create a new password

The reset link expires in 24 hours. If you need additional help, reply to this email.

Best,
{agent_name} | {company_name} Support
""",

    "refund_approved": """
Hi {customer_name},

Great news — we've approved your refund of {amount} to {payment_method}.

Refunds typically appear within 5-10 business days depending on your bank.

Reference number: {refund_id}

Is there anything else I can help with?
""",

    "escalation_acknowledgment": """
Hi {customer_name},

Thank you for your patience. I've escalated your case to our {team_name} team
who can best help with {issue_type}.

You'll hear from a specialist within {sla_hours} hours.

Your ticket reference is: {ticket_id}
"""
}
```

## CSAT and Feedback Automation

```python
def send_csat_survey(ticket_id: str, customer_email: str, resolution_type: str):
    """Send CSAT survey 1 hour after ticket resolution."""
    # Don't send CSAT to churned/cancelled customers
    if is_churned_customer(customer_email):
        return

    schedule_email(
        to=customer_email,
        send_at=datetime.now() + timedelta(hours=1),
        template="csat_survey",
        variables={
            "ticket_id": ticket_id,
            "survey_link": generate_csat_link(ticket_id)
        }
    )

def process_low_csat(ticket_id: str, score: int, comment: str):
    """Automatically escalate and flag low CSAT scores."""
    if score <= 2:
        # Critical: alert support manager immediately
        alert_manager(
            ticket_id=ticket_id,
            score=score,
            comment=comment,
            action="Immediate recovery outreach required"
        )
        create_recovery_task(ticket_id)
    elif score == 3:
        # Flag for review in next team meeting
        flag_for_review(ticket_id, score, comment)
```

## Deflection Metrics

Track weekly to optimize:
- **Deflection rate**: % tickets resolved without human agent
- **Target**: 40-60% for B2B SaaS, 60-80% for B2C
- **CSAT by tier**: Self-service vs. human agent satisfaction scores
- **Handle time**: Average time per ticket by tier
- **Escalation rate**: % of auto-resolutions that required human follow-up
- **False resolution rate**: Customer reopens ticket within 48h (bad auto-resolution)
