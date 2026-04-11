---
name: CRM Workflows
description: Design and automate CRM pipelines, contact management, deal stages, and sales workflows
category: business
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [business, crm, sales, workflows, hubspot, salesforce, pipeline, automation]
platforms: [all]
---

# CRM Workflows

Build systematic CRM processes that capture every lead, move deals efficiently through the pipeline, and enable accurate forecasting.

## CRM Architecture

### Core Objects
| Object | What It Represents | Key Fields |
|--------|-------------------|-----------|
| **Contact** | Individual person | Name, email, phone, job title, lifecycle stage |
| **Company** | Organization | Name, domain, industry, size, ARR, account owner |
| **Deal** | Active sales opportunity | Name, amount, stage, close date, probability |
| **Activity** | Email, call, meeting, note | Type, outcome, next steps, date |
| **Ticket** | Support request | Status, priority, resolution time |

### Lifecycle Stages
```
Subscriber → Lead → MQL → SQL → Opportunity → Customer → Advocate
```
- **Subscriber**: Signed up for newsletter / content
- **Lead**: Showed intent beyond content (pricing page, demo request form visit)
- **MQL**: Scored above threshold by marketing criteria (behavior + firmographics)
- **SQL**: Qualified by sales rep (confirmed budget, authority, need, timing)
- **Opportunity**: Active deal in pipeline (demo completed, proposal sent)
- **Customer**: Closed won; active paying account
- **Advocate**: Customer who provides referrals or case studies

## Sales Pipeline Design

### Stage Definition
```yaml
pipeline_stages:
  - name: "Outreach Sent"
    probability: 5%
    expected_actions: ["First email/call sent"]
    exit_criteria: "Contact responds"
    target_days_in_stage: 7

  - name: "Discovery Call Scheduled"
    probability: 20%
    expected_actions: ["Meeting booked in calendar"]
    exit_criteria: "Call completed"
    target_days_in_stage: 3

  - name: "Discovery Completed"
    probability: 35%
    expected_actions: ["Pain points documented", "BANT qualified"]
    exit_criteria: "Demo scheduled"
    target_days_in_stage: 5

  - name: "Demo Completed"
    probability: 55%
    expected_actions: ["Demo delivered", "Stakeholders identified"]
    exit_criteria: "Proposal requested"
    target_days_in_stage: 7

  - name: "Proposal Sent"
    probability: 70%
    expected_actions: ["Proposal emailed", "Pricing discussed"]
    exit_criteria: "Decision received"
    target_days_in_stage: 14

  - name: "Negotiation"
    probability: 85%
    expected_actions: ["Legal review", "Contract sent"]
    exit_criteria: "Signed or lost"
    target_days_in_stage: 10

  - name: "Closed Won"
    probability: 100%
  - name: "Closed Lost"
    probability: 0%
```

## CRM Automation Workflows

### Lead Routing Workflow
```python
def route_lead(lead: dict) -> dict:
    """Assign new lead to the appropriate rep based on territory and capacity."""
    territory = determine_territory(lead["company_country"], lead["company_size"])
    available_reps = get_available_reps(territory, max_capacity=50)  # Max 50 open leads per rep

    # Round-robin within territory
    assigned_rep = round_robin_assign(available_reps, lead["id"])

    crm.update_contact(lead["id"], {
        "owner": assigned_rep["id"],
        "lifecycle_stage": "lead",
        "routing_reason": f"Territory: {territory}, Capacity: {assigned_rep['capacity']}",
    })

    # Notify rep via Slack + email
    notify_rep(assigned_rep, lead, channel="new_lead")

    return {"assigned_to": assigned_rep["name"], "territory": territory}
```

### Deal Stage Automation (HubSpot Workflow)
```
Trigger: Deal stage = "Discovery Completed"
Actions:
  1. Create task: "Schedule demo within 2 business days" (owner: deal owner, due: +2d)
  2. Send internal Slack notification: "#sales" channel with deal name + amount
  3. Add deal to Sequence: "Post-Discovery Follow-up"
  4. Update deal property: "Discovery Date" = today
  5. If deal amount > $50,000: create task for manager to review
```

### Lead Scoring Model
```python
scoring_rules = {
    # Demographic / Firmographic (BANT signals)
    "company_size_1000plus":     20,
    "company_size_100_999":      10,
    "decision_maker_title":      15,   # C-level, VP, Director
    "target_industry":           10,
    "target_geography":          5,

    # Behavioral (engagement signals)
    "pricing_page_visited":      25,
    "demo_requested":            40,
    "free_trial_started":        30,
    "email_opened_3plus":        5,
    "webinar_attended":          10,
    "case_study_downloaded":     8,
    "competitor_comparison_page": 15,

    # Negative signals
    "personal_email_domain":    -15,   # gmail, hotmail, etc.
    "competitor_domain":        -50,
    "student_edu_domain":       -20,
}

MQL_THRESHOLD = 50   # Contacts scoring >= 50 become MQL

def calculate_lead_score(contact: dict) -> int:
    return sum(
        points for criterion, points in scoring_rules.items()
        if contact.get(criterion)
    )
```

### Stale Deal Alert
```python
def check_stale_deals():
    """Alert on deals that haven't had activity in X days."""
    thresholds = {
        "Outreach Sent": 7,
        "Discovery Call Scheduled": 3,
        "Proposal Sent": 14,
    }

    for stage, days in thresholds.items():
        stale_deals = crm.get_deals(
            stage=stage,
            last_activity_before=datetime.now() - timedelta(days=days),
        )

        for deal in stale_deals:
            crm.create_task(
                deal_id=deal["id"],
                title=f"Deal stale for {days}+ days — follow up now",
                due_date=datetime.now() + timedelta(days=1),
                owner=deal["owner_id"],
            )
            send_slack_dm(deal["owner_id"],
                f"⚠️ Deal '{deal['name']}' has been in {stage} for {days}+ days. Please update or advance.")
```

## Contact Data Management

### Data Enrichment (Clearbit / Apollo)
```python
async def enrich_contact(email: str) -> dict:
    """Auto-enrich contact with firmographic and technographic data."""
    enriched = await clearbit.enrich(email)

    updates = {
        "company_name": enriched.get("company", {}).get("name"),
        "company_size": enriched.get("company", {}).get("metrics", {}).get("employees"),
        "industry": enriched.get("company", {}).get("category", {}).get("industry"),
        "job_title": enriched.get("person", {}).get("title"),
        "linkedin_url": enriched.get("person", {}).get("linkedin", {}).get("handle"),
        "tech_stack": enriched.get("company", {}).get("tech", []),
        "funding_raised": enriched.get("company", {}).get("metrics", {}).get("raised"),
    }

    crm.update_contact(email, updates)
    return updates
```

### Deduplication Rules
- Match on: email (exact) → then company domain + first name + last name
- On match: merge records; keep oldest `created_at`, newest activity data
- Winner field selection: prefer non-empty, prefer manually entered over enriched
- Run deduplication nightly with a 30-day cooldown per pair

## Pipeline Forecasting

### Weighted Pipeline Formula
```sql
SELECT
    owner_name,
    SUM(deal_amount * stage_probability / 100) AS weighted_pipeline,
    SUM(CASE WHEN close_date <= CURRENT_DATE + 30 THEN deal_amount * stage_probability / 100 ELSE 0 END) AS weighted_30d,
    COUNT(*) AS open_deals,
    SUM(deal_amount) AS raw_pipeline
FROM deals
JOIN pipeline_stages USING (stage)
WHERE status = 'open'
GROUP BY owner_name
ORDER BY weighted_pipeline DESC;
```

### Forecast Accuracy Tracking
```
Commit: Deals rep is highly confident will close this quarter (> 90% probability)
Best Case: All commit deals + most likely deals (> 70%)
Pipeline: Full open pipeline this quarter

Track: Predicted (beginning of quarter) vs Actual (end of quarter)
Target forecast accuracy: ± 10% of actual revenue
```

## CRM Health Metrics

| Metric | Target | Alert If |
|--------|--------|---------|
| Data completeness (key fields) | > 90% | < 80% |
| Deals without next activity | < 5% | > 15% |
| Stale deals (> 30 days, no movement) | < 10% | > 20% |
| Duplicate contact rate | < 2% | > 5% |
| Lead response time (MQL → first contact) | < 5 minutes | > 1 hour |
| Pipeline coverage (pipe / quota) | 3-4x | < 2x |

## CRM Audit Checklist

- [ ] All contacts have an owner assigned
- [ ] All open deals have a close date
- [ ] Deal amounts are populated for all opportunities
- [ ] Activity logged after every customer interaction
- [ ] Lost deals have a loss reason recorded
- [ ] Lead source populated for all contacts
- [ ] Lifecycle stages match actual engagement level
- [ ] Automation workflows reviewed and tested quarterly
