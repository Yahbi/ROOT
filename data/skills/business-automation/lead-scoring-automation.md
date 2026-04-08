---
name: Lead Scoring and Automation
description: Automatically score, qualify, and route inbound leads using behavioral signals and ML models
version: "1.0.0"
author: ROOT
tags: [business-automation, lead-scoring, CRM, sales, marketing-automation]
platforms: [all]
difficulty: intermediate
---

# Lead Scoring and Automation

Replace manual lead review with automated scoring to focus sales time on
highest-probability opportunities.

## Lead Scoring Framework

### Explicit Signals (Demographic Fit)

| Signal | Score | Why |
|--------|-------|-----|
| Company size 100-1000 employees | +20 | Ideal customer profile |
| Job title: VP/C-suite/Director | +25 | Decision maker |
| Target industry match | +15 | Relevant use case |
| Company size < 10 or > 5000 | -10 | Outside ICP |
| Personal email (@gmail, @yahoo) | -20 | Low intent |
| Job title: intern/student | -15 | Not decision maker |

### Behavioral Signals (Intent)

| Action | Score | Decay |
|--------|-------|-------|
| Requested demo | +50 | No decay |
| Pricing page visit | +30 | 50% after 7 days |
| Case study download | +20 | 50% after 14 days |
| Feature page visit (3+) | +15 | 50% after 7 days |
| Webinar attended | +25 | 50% after 30 days |
| Email opened | +5 | 75% after 3 days |
| Email link clicked | +10 | 50% after 7 days |
| Unsubscribed | -100 | Permanent |

## Score Thresholds and Actions

```python
LEAD_SCORE_ROUTING = {
    (80, 100): {
        "grade": "A",
        "action": "immediate_sales_alert",
        "sla": "Contact within 1 hour",
        "assignment": "senior_sales_rep"
    },
    (60, 79): {
        "grade": "B",
        "action": "sales_queue",
        "sla": "Contact within 24 hours",
        "assignment": "sales_rep"
    },
    (40, 59): {
        "grade": "C",
        "action": "nurture_sequence",
        "sla": "Enter email sequence",
        "assignment": "marketing_automation"
    },
    (0, 39): {
        "grade": "D",
        "action": "long_nurture",
        "sla": "Monthly newsletter only",
        "assignment": "none"
    }
}
```

## Implementation: HubSpot Workflow

```python
# HubSpot API lead scoring update
import hubspot
from hubspot.crm.contacts import ApiException

def update_lead_score(contact_id: str, score_delta: int, reason: str):
    client = hubspot.Client.create(access_token=HUBSPOT_TOKEN)

    # Get current score
    contact = client.crm.contacts.basic_api.get_by_id(
        contact_id=contact_id,
        properties=["lead_score", "email", "company"]
    )
    current_score = int(contact.properties.get("lead_score", 0))
    new_score = max(0, min(100, current_score + score_delta))

    # Update score
    client.crm.contacts.basic_api.update(
        contact_id=contact_id,
        simple_public_object_input={"properties": {
            "lead_score": str(new_score),
            "last_score_reason": reason,
            "last_score_date": datetime.now().isoformat()
        }}
    )

    # Trigger routing if threshold crossed
    if current_score < 80 <= new_score:
        trigger_sales_alert(contact_id, new_score)

    return new_score
```

## Behavioral Tracking Pipeline

```python
# Event tracking for lead behavior scoring
class LeadBehaviorTracker:
    def __init__(self, crm_client, redis_client):
        self.crm = crm_client
        self.redis = redis_client

    def track_event(self, email: str, event_type: str, metadata: dict = None):
        lead_id = self.crm.find_lead_by_email(email)
        if not lead_id:
            return

        score_delta = self.get_event_score(event_type)
        if score_delta != 0:
            self.update_lead_score(lead_id, score_delta, event_type)
            self.log_event(lead_id, event_type, score_delta, metadata)

    def get_event_score(self, event_type: str) -> int:
        SCORES = {
            "demo_requested": 50,
            "pricing_page": 30,
            "case_study_download": 20,
            "feature_page_view": 5,
            "email_opened": 3,
            "email_clicked": 8,
            "webinar_registered": 15,
            "webinar_attended": 25,
        }
        return SCORES.get(event_type, 0)
```

## Email Nurture Sequences

### Drip Campaign Automation

```python
# Trigger nurture sequence based on lead score and behavior
NURTURE_SEQUENCES = {
    "demo_no_show": {
        "triggers": ["demo_booked", "demo_not_attended"],
        "sequence": [
            {"delay_hours": 2, "template": "demo_reschedule"},
            {"delay_hours": 48, "template": "value_proof_case_study"},
            {"delay_hours": 168, "template": "low_friction_cta"},
        ]
    },
    "content_download": {
        "triggers": ["ebook_download"],
        "sequence": [
            {"delay_hours": 0.5, "template": "content_delivery"},
            {"delay_hours": 24, "template": "related_content"},
            {"delay_hours": 72, "template": "soft_demo_cta"},
            {"delay_hours": 168, "template": "final_offer"},
        ]
    }
}

def enroll_in_sequence(lead_id: str, sequence_name: str):
    sequence = NURTURE_SEQUENCES[sequence_name]
    for step in sequence["sequence"]:
        schedule_email(
            lead_id=lead_id,
            template=step["template"],
            send_at=datetime.now() + timedelta(hours=step["delay_hours"])
        )
```

## CRM Automation Rules

```python
# Automated lead assignment and stage progression
class LeadAutomation:
    def process_new_lead(self, lead: dict) -> dict:
        """Full automation pipeline for new lead ingestion."""
        # 1. Enrich lead data
        enriched = self.enrich_from_clearbit(lead["email"])
        lead.update(enriched)

        # 2. Compute initial score
        initial_score = self.compute_demographic_score(lead)

        # 3. Create or update CRM record
        lead_id = self.crm.upsert_lead(lead)
        self.crm.update_score(lead_id, initial_score)

        # 4. Route based on score
        routing = LEAD_SCORE_ROUTING[self.get_grade(initial_score)]
        self.assign_lead(lead_id, routing)

        # 5. Start nurture sequence if not in sales queue
        if routing["action"] != "immediate_sales_alert":
            self.enroll_in_nurture(lead_id, initial_score)

        return {"lead_id": lead_id, "score": initial_score, "action": routing["action"]}
```

## Analytics and Optimization

Track weekly:
- Lead-to-MQL conversion rate by source
- MQL-to-SQL conversion rate by score grade
- Average lead score at deal close
- Score model accuracy (predicted vs. actual conversion)
- Sequence email open/click rates
- Time from lead to first sales contact

Review and recalibrate scores quarterly by comparing to actual conversion data.
