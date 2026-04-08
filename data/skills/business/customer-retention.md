---
name: Customer Retention
description: Frameworks, metrics, and playbooks for reducing churn and increasing customer lifetime value
category: business
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [business, retention, churn, customer-success, LTV, NPS, engagement]
platforms: [all]
---

# Customer Retention

Systematically identify at-risk customers, drive product adoption, and build loyalty that reduces churn and increases lifetime value.

## Retention Fundamentals

### Key Metrics
| Metric | Formula | Target (SaaS) |
|--------|---------|--------------|
| **Monthly Churn Rate** | Churned customers / Start-of-month customers | < 2% (SMB), < 0.5% (Enterprise) |
| **Annual Churn Rate** | 1 - (1 - monthly_churn)^12 | < 5% (Enterprise), < 20% (SMB) |
| **Net Revenue Retention (NRR)** | (MRR end - churned + expansion) / MRR start | > 110% = growth engine |
| **Customer Lifetime Value (LTV)** | ARPU / monthly_churn_rate | Ideally LTV / CAC > 3 |
| **Payback Period** | CAC / ARPU | < 12 months |
| **NPS (Net Promoter Score)** | % Promoters - % Detractors | > 40 is good, > 70 is excellent |

### The Retention Hierarchy
```
1. Adoption       → Customer uses core features and gets value
2. Satisfaction   → Customer is happy with the product and support
3. Expansion      → Customer buys more (seats, features, plans)
4. Advocacy       → Customer refers others and provides testimonials
```

## Churn Prediction Model

### Health Score Framework
```python
def calculate_health_score(customer: dict) -> dict:
    """Composite health score from 0-100."""
    scores = {
        # Usage signals (40% weight)
        "login_frequency": score_logins(customer["logins_last_30d"]),         # 0-100
        "feature_adoption": customer["features_used"] / MAX_FEATURES * 100,    # 0-100
        "active_users": min(customer["active_users"] / customer["paid_seats"], 1) * 100,

        # Engagement signals (20% weight)
        "email_engagement": score_email_opens(customer["email_open_rate_90d"]),
        "support_tickets": score_tickets(customer["open_support_tickets"]),

        # Business signals (20% weight)
        "payment_history": 100 if customer["failed_payments_3m"] == 0 else 40,
        "contract_months_remaining": score_contract_length(customer["months_remaining"]),

        # Relationship signals (20% weight)
        "nps_score": (customer.get("nps_score", 7) / 10) * 100,
        "sponsor_engagement": 100 if customer["exec_sponsor_contact_30d"] else 30,
    }

    weights = {
        "login_frequency": 0.15, "feature_adoption": 0.15, "active_users": 0.10,
        "email_engagement": 0.10, "support_tickets": 0.10,
        "payment_history": 0.10, "contract_months_remaining": 0.10,
        "nps_score": 0.10, "sponsor_engagement": 0.10,
    }

    composite = sum(scores[k] * weights[k] for k in scores)
    status = "green" if composite >= 70 else "yellow" if composite >= 45 else "red"

    return {"score": round(composite, 1), "status": status, "breakdown": scores}
```

### Churn Risk Signals
| Signal | Risk Level | Action |
|--------|-----------|--------|
| Login frequency dropped > 50% in 30d | HIGH | CSM outreach within 24h |
| Support ticket open > 7 days unresolved | HIGH | Escalate to senior support |
| Key user left the organization | HIGH | Identify new champion, executive outreach |
| Feature adoption < 20% after 60 days | MEDIUM | Targeted onboarding session |
| No logins in 14 days (trial/early-stage) | HIGH | Win-back sequence |
| NPS score 0-6 (Detractor) | HIGH | Recovery call within 48h |
| Contract renewal 90 days out + low health | CRITICAL | QBR + renewal strategy |

## Onboarding Playbook

### Time-to-Value Framework
```
Day 0:   Account created → Welcome + setup guide
Day 1:   CSM intro call (Enterprise) or automated onboarding email sequence
Day 3:   "Aha moment" achieved? → First key action completed
Day 7:   Check-in: walkthrough of 3 core features relevant to their use case
Day 14:  Milestone review — have they gotten initial value?
Day 30:  30-day review call (Enterprise) or automated success email
Day 60:  Feature expansion: introduce advanced features they haven't tried
Day 90:  QBR prep: gather outcomes data for renewal conversation
```

### Onboarding Completion Tracking
```sql
SELECT
    customer_id,
    company_name,
    signup_date,
    DATEDIFF('day', signup_date, aha_moment_date) AS days_to_aha,
    CASE WHEN aha_moment_date IS NOT NULL THEN 'completed' ELSE 'incomplete' END AS aha_status,
    onboarding_step_completed,
    MAX_ONBOARDING_STEP AS total_steps,
    onboarding_step_completed / MAX_ONBOARDING_STEP * 100 AS completion_pct
FROM customer_onboarding
WHERE signup_date >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY completion_pct ASC;   -- Bottom of list = highest risk
```

## Customer Success Playbooks

### High-Touch (Enterprise) Playbook
```yaml
segment: enterprise
criteria: ARR > $50,000
csm_ratio: 1:10  # 1 CSM per 10 accounts
touchpoints:
  - kickoff_call: week_1
  - implementation_review: week_2
  - monthly_check_in: monthly
  - quarterly_business_review: quarterly
  - executive_sponsor_call: bi_annually
  - renewal_strategy_call: 90_days_before_renewal
health_score_threshold:
  yellow: weekly_csm_outreach
  red: csm_escalation_within_24h + manager_notification
```

### QBR (Quarterly Business Review) Template
```markdown
# QBR: [Customer Name] — Q[X] [Year]

## ROI Summary
- Metric 1: [Baseline] → [Current] (X% improvement)
- Metric 2: [Baseline] → [Current]
- Estimated value delivered: $XXX,XXX

## Usage Summary
- Active users: X of Y licensed seats (Z% adoption)
- Top features used: [list]
- Features not yet utilized: [list with value proposition]

## Wins This Quarter
- [Specific outcome or project they completed using the product]

## Areas for Improvement
- [Honest assessment of where they're struggling]
- [Support tickets, unresolved issues]

## Goals for Next Quarter
- [Their business goals we can help with]
- [Product features we'll implement together]

## Expansion Opportunities
- [Additional use cases, seats, or products relevant to their goals]

## Renewal Discussion
- Renewal date: [Date]
- Current ARR: $XX,XXX
- Proposed renewal: $XX,XXX (with expansion)
```

## NPS Program

### Collection Strategy
- **Transactional NPS**: Immediately after key interactions (onboarding completion, support resolution)
- **Relationship NPS**: Every 6 months to all customers at the account level
- Target: 80%+ response rate (in-app survey achieves higher rates than email)

### Follow-Up by Score
```python
async def handle_nps_response(customer_id: str, score: int, comment: str):
    if score <= 6:    # Detractor
        await create_csm_task(customer_id, "NPS Detractor follow-up call within 48h",
                               priority="HIGH", context=comment)
        await flag_as_churn_risk(customer_id, reason=f"NPS Detractor: {score}")

    elif score <= 8:  # Passive
        await enroll_in_sequence(customer_id, "nps_passive_nurture")
        await update_health_signal(customer_id, "nps_passive")

    else:             # Promoter (9-10)
        await request_review(customer_id)     # Ask for G2/Capterra review
        await request_case_study(customer_id) # High LTV promoters → case study ask
        await send_referral_program_invite(customer_id)
```

## Expansion Revenue Playbook

### Expansion Triggers
- Usage approaching plan limits (seats, API calls, storage)
- New team/department using product (suggest multi-team plan)
- Customer achieved ROI milestone (now ready to expand use case)
- New product feature that matches their stated goals
- Annual renewal (natural upsell moment)

### Expansion Email Template
```
Subject: You're getting close to your [seats/API/storage] limit

Hi [Name],

You're at 85% of your [seat] limit — which is a great sign that your team
is getting a lot of value from [Product].

When you hit 100%, [consequence: new users won't be able to access / API calls
will be throttled].

You can upgrade in 2 minutes: [Link to upgrade page]

[Optional: If you upgrade before the end of the month, I can apply a [X%]
loyalty discount.]

If you'd like to talk through what's right for your team, reply to this and
we'll set up 15 minutes.

[Name]
[Customer Success]
```

## Retention Analytics Dashboard

| Metric | Weekly | Monthly | Quarterly |
|--------|--------|---------|-----------|
| Churn rate | Track | Report | Trend |
| At-risk accounts (yellow + red) | Track | Cohort analysis | |
| Onboarding completion rate | Track | | |
| NPS score | | Track | Trend |
| NRR | | Track | Trend |
| Expansion MRR vs churn MRR | | Track | |
| Time-to-value (days to aha moment) | | Cohort analysis | |
