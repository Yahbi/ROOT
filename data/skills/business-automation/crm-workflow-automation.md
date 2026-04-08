---
name: CRM Workflow Automation
description: Automate sales pipeline management, follow-ups, and deal progression using CRM workflow rules
version: "1.0.0"
author: ROOT
tags: [business-automation, CRM, HubSpot, Salesforce, workflow, sales-automation]
platforms: [all]
difficulty: intermediate
---

# CRM Workflow Automation

Eliminate manual CRM data entry and follow-up reminders by automating pipeline
management, deal progression, and handoff processes.

## Core Automation Principles

1. **Automate data entry** — Sales reps should sell, not type
2. **Automate reminders** — No deal falls through the cracks
3. **Automate handoffs** — Marketing to Sales, Sales to CS — zero friction
4. **Automate reporting** — Weekly pipeline reports without manual effort
5. **Never automate judgment** — Only humans decide to close or escalate

## Deal Stage Automation

### Automatic Stage Progression Triggers

```python
STAGE_TRIGGERS = {
    "Lead → Qualified": [
        {"event": "demo_scheduled", "auto_progress": True},
        {"event": "budget_confirmed", "score_required": 60}
    ],
    "Qualified → Proposal": [
        {"event": "discovery_call_completed", "next_action": "send_proposal_template"},
        {"event": "stakeholders_identified", "create_task": "Identify decision makers"}
    ],
    "Proposal → Negotiation": [
        {"event": "proposal_opened", "min_opens": 3, "alert": "high_intent"},
        {"event": "contract_requested", "auto_progress": True}
    ],
    "Negotiation → Closed Won": [
        {"event": "contract_signed", "auto_progress": True,
         "trigger": "create_onboarding_project"},
        {"event": "payment_received", "update_field": "close_date"}
    ],
    "Any → Closed Lost": [
        {"event": "unsubscribed", "auto_progress": True},
        {"event": "no_response_days": 21, "create_task": "Final outreach attempt"}
    ]
}
```

### HubSpot Workflow Implementation

```python
import hubspot
from hubspot.automation.actions import ApiException

def create_deal_stage_workflow(client, deal_stage: str, actions: list) -> dict:
    """Create an automated workflow triggered by deal stage change."""
    workflow_config = {
        "name": f"Auto: {deal_stage} Actions",
        "type": "CONTACT_DATE_CENTERED",
        "enabled": True,
        "enrollmentCriteria": {
            "filterBranches": [{
                "filterBranchType": "AND",
                "filters": [{
                    "property": "dealstage",
                    "operation": {"operationType": "ENUMERATION",
                                  "values": [deal_stage]}
                }]
            }]
        },
        "actions": actions
    }
    return client.automation.v4.actions_api.create(workflow_config)

# Example workflow actions
DEMO_BOOKED_ACTIONS = [
    {
        "type": "SET_CONTACT_PROPERTY",
        "fields": [{"name": "lifecyclestage", "value": "salesqualifiedlead"}]
    },
    {
        "type": "CREATE_TASK",
        "fields": [{"name": "subject", "value": "Prep for demo - review company info"},
                   {"name": "hs_task_priority", "value": "HIGH"},
                   {"name": "hs_task_type", "value": "CALL"}]
    },
    {
        "type": "SEND_EMAIL",
        "fields": [{"name": "emailId", "value": "DEMO_CONFIRMATION_TEMPLATE_ID"}]
    }
]
```

## Automated Follow-Up System

### Stale Deal Detection

```python
def detect_stale_deals(crm_client) -> list[dict]:
    """Find deals with no activity in the defined stale period."""
    STALE_THRESHOLDS = {
        "Lead": 3,           # Days without activity
        "Qualified": 5,
        "Proposal Sent": 7,
        "Negotiation": 3,
    }

    stale_deals = []
    for stage, threshold_days in STALE_THRESHOLDS.items():
        deals = crm_client.get_deals_by_stage(stage)
        for deal in deals:
            days_inactive = (datetime.now() - deal["last_activity_date"]).days
            if days_inactive >= threshold_days:
                stale_deals.append({
                    "deal_id": deal["id"],
                    "deal_name": deal["name"],
                    "stage": stage,
                    "days_inactive": days_inactive,
                    "owner": deal["owner_email"],
                    "priority": "HIGH" if days_inactive > threshold_days * 2 else "MEDIUM"
                })
    return stale_deals

def create_stale_deal_tasks(stale_deals: list, crm_client):
    """Create follow-up tasks for all stale deals."""
    for deal in stale_deals:
        crm_client.create_task(
            deal_id=deal["deal_id"],
            owner=deal["owner"],
            subject=f"[STALE {deal['days_inactive']}d] Follow up with {deal['deal_name']}",
            priority=deal["priority"],
            due_date=datetime.now() + timedelta(hours=4)
        )
```

## Sales-to-Success Handoff

```python
def trigger_cs_handoff(deal: dict, crm_client, project_client):
    """Automate customer success handoff when deal closes."""
    # 1. Create CS onboarding project
    project = project_client.create_project(
        template="Enterprise Onboarding Template",
        name=f"Onboarding: {deal['company_name']}",
        custom_fields={
            "account_value": deal["amount"],
            "close_date": deal["close_date"],
            "product": deal["products_sold"],
            "primary_contact": deal["contact_name"],
        }
    )

    # 2. Assign CS manager based on deal size
    if deal["amount"] >= 50000:
        cs_manager = crm_client.get_enterprise_cs_manager()
    else:
        cs_manager = crm_client.get_available_cs_manager()

    # 3. Schedule kickoff call
    calendar_link = generate_kickoff_calendar_invite(
        cs_manager=cs_manager,
        customer=deal,
        within_days=3
    )

    # 4. Send handoff notification
    send_internal_notification(
        to=cs_manager["email"],
        subject=f"New Customer Handoff: {deal['company_name']} (${deal['amount']:,})",
        body=f"""
Sales has closed {deal['company_name']}!

Deal Summary:
- ARR: ${deal['amount']:,}
- Products: {deal['products_sold']}
- AE: {deal['ae_name']}

Onboarding project: {project['url']}
Schedule kickoff: {calendar_link}

Key notes from sales: {deal['notes']}
"""
    )
    return {"project_id": project["id"], "cs_manager": cs_manager["name"]}
```

## Pipeline Analytics Automation

```python
def generate_weekly_pipeline_report(crm_client) -> dict:
    """Auto-generate pipeline health report every Monday morning."""
    pipeline = crm_client.get_all_deals()

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_pipeline_value": sum(d["amount"] for d in pipeline),
        "deals_by_stage": {},
        "weighted_forecast": 0,
        "at_risk_deals": [],
        "hot_deals": [],
    }

    STAGE_WEIGHTS = {
        "Lead": 0.05, "Qualified": 0.15, "Proposal": 0.30,
        "Negotiation": 0.60, "Verbal Commit": 0.85
    }

    for stage, weight in STAGE_WEIGHTS.items():
        stage_deals = [d for d in pipeline if d["stage"] == stage]
        stage_value = sum(d["amount"] for d in stage_deals)
        report["deals_by_stage"][stage] = {
            "count": len(stage_deals), "value": stage_value, "weight": weight,
            "weighted_value": stage_value * weight
        }
        report["weighted_forecast"] += stage_value * weight

    # Identify at-risk (stale) and hot (recent activity) deals
    for deal in pipeline:
        days_inactive = (datetime.now() - deal["last_activity"]).days
        if days_inactive > 10:
            report["at_risk_deals"].append(deal)
        elif days_inactive < 2 and deal["amount"] > 10000:
            report["hot_deals"].append(deal)

    return report
```

## Zapier/Make Automation Recipes

Common cross-system automation flows:

```
1. New Calendly booking → Create HubSpot contact + deal + task
2. Email opened 3+ times → Alert owner in Slack
3. Deal closed won → Create invoice in QuickBooks + project in Asana
4. NPS score < 7 → Alert CS manager + create follow-up task
5. Lead form submitted → Enrich with Clearbit → Score → Route
6. Contract signed in DocuSign → Update CRM stage + trigger onboarding
7. Deal stuck 14+ days → Slack reminder to owner with deal context
```
