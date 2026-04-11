---
name: Email Automation
description: Design automated email sequences, behavioral triggers, and lifecycle campaigns for growth and retention
category: business
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [business, email-automation, drip-campaigns, lifecycle, nurture, marketing-automation]
platforms: [all]
---

# Email Automation

Build systematic email workflows that convert prospects, onboard users, and retain customers at scale without manual effort.

## Email Automation Fundamentals

### Types of Automated Emails
| Type | Trigger | Goal | Typical Conversion |
|------|---------|------|-------------------|
| Welcome sequence | New signup | Activate and educate | 25-40% activation |
| Onboarding drip | Account created | Feature adoption | Drive key actions |
| Behavioral trigger | In-app action (or inaction) | Convert or re-engage | Highest CTR (5-15%) |
| Abandoned cart | Cart created, no purchase | Recover revenue | 5-15% recovery |
| Trial expiry | X days before trial ends | Upgrade to paid | 10-20% conversion |
| Win-back | 30/60/90 days inactive | Reactivate churned users | 3-8% reactivation |
| Post-purchase | After first purchase | Onboard, upsell, review | 25-35% open rate |

### Platform Selection
| Platform | Best For | Price Range |
|----------|----------|-------------|
| Customer.io | Behavioral + event-driven | $150+/month |
| Klaviyo | E-commerce, high personalization | $20-$500+/month |
| ActiveCampaign | SMB with CRM integration | $29-$149+/month |
| HubSpot | Full marketing + CRM suite | $45-$800+/month |
| Mailchimp | Simple campaigns + journeys | Free-$350+/month |
| Drip | E-commerce automation | $39+/month |

## Welcome Sequence (5-7 Days)

### Structure
```
Day 0: Immediate — Welcome + confirm email / get started
Day 1: Value — Your biggest benefit or quick win guide
Day 3: Social proof — Case study or testimonial
Day 5: Education — Advanced tip or feature highlight
Day 7: CTA — Book a call, start trial, make first purchase
```

### Welcome Email (Day 0) Template
```
Subject: Welcome to [Product] — here's what to do first

Hi {{first_name}},

You're in. [One-sentence value statement about what they just joined].

Here's your first step (takes 2 minutes):
→ [Specific, concrete action with link]

Why this matters: [What completing this action unlocks for them].

We built [Product] because [authentic founding story / customer problem].
Over the next few days, I'll share [what they'll learn in the sequence].

Any questions? Reply directly to this email — I read every one.

[Founder/Team name]

P.S. [Low-friction secondary CTA — join community, follow on Twitter, etc.]
```

## Behavioral Trigger Automation

### Trigger Architecture
```python
# Event-driven triggers in Customer.io
events = {
    "user_signed_up":          {"segment": "new_users", "sequence": "welcome_v2"},
    "feature_not_used_3d":     {"segment": "at_risk", "sequence": "feature_nudge"},
    "trial_day_7":             {"segment": "trial_midpoint", "sequence": "trial_push"},
    "trial_day_13":            {"segment": "trial_expiring", "sequence": "urgency"},
    "invoice_paid":            {"segment": "paying_users", "sequence": "success_onboard"},
    "subscription_cancelled":  {"segment": "churned", "sequence": "exit_recovery"},
}

def trigger_automation(event_name: str, user: dict, properties: dict):
    config = events.get(event_name)
    if config:
        add_to_segment(user["id"], config["segment"])
        enroll_in_sequence(user["id"], config["sequence"], properties)
```

### In-App Activity Triggers
```
User completed setup → Send "Your setup is complete" + next milestone guide
User logged in < 3 times in 14 days → Send re-engagement with help offer
User viewed upgrade page but didn't upgrade → Send "Have questions about upgrading?" email
User added team member → Send "Congratulations on growing your team" + team features guide
User ran their first report → Send "Your first report — share it" + export guide
```

## Trial-to-Paid Conversion Sequence

### 14-Day Trial Cadence
```
Day 0 (signup):    Welcome + immediate value / quick start guide
Day 1:             Check-in — did you complete [key action]?
Day 3:             Feature spotlight: [highest-value feature]
Day 7 (midpoint):  Progress check — here's what you've accomplished
Day 10:            Case study: how [similar customer] achieved [result]
Day 12:            FAQ: answers to most common upgrade questions
Day 13:            "2 days left" — urgency + discount offer (optional)
Day 14 (last day): Final notice — what happens when trial ends + CTA
Day 15:            Win-back: "Your trial ended — still interested?"
```

### Subject Line Formula for Trial Emails
- Day 0: "Your [Product] account is ready — start here"
- Day 7: "You're halfway through your trial — here's your progress"
- Day 13: "48 hours left on your trial"
- Day 14: "Your trial ends tonight"

## Segmentation Strategy

### Behavioral Segments
```python
segments = {
    "power_users": "login_count_7d >= 5 AND feature_usage_score >= 80",
    "at_risk":     "login_count_14d == 0 AND days_since_signup > 7",
    "champions":   "plan = 'enterprise' AND nps_score >= 9",
    "new_users":   "days_since_signup <= 7",
    "warm_leads":  "email_opens_30d >= 3 AND has_purchased = false",
}
```

### Personalization Variables
- First name (always)
- Company name, role (B2B)
- Product/plan they're using
- Last action taken in the app
- Number of team members / seats
- Days since signup or last login
- Specific features they have/haven't used

## Email Deliverability

### Technical Requirements
```
SPF record:     v=spf1 include:sendgrid.net include:mailgun.org ~all
DKIM:           Configure 2048-bit key per sending domain
DMARC:          v=DMARC1; p=quarantine; rua=mailto:dmarc@company.com; pct=100
BIMI:           Upload brand logo — increases trust + open rates in Gmail
Custom domain:  Send from @yourcompany.com, not @mailchimp.com
```

### Warm-Up Schedule for New Domain
```
Week 1: 200/day → 500/day
Week 2: 1,000/day → 2,000/day
Week 3: 5,000/day → 10,000/day
Week 4: 25,000/day → full volume
```
- Start with most engaged subscribers (recent opens/clicks)
- Maintain < 0.1% spam complaint rate; < 2% bounce rate
- Monitor inbox placement with tools: GlockApps, Mail-Tester

### List Hygiene
- Remove hard bounces immediately
- Remove soft bounce addresses after 3 consecutive bounces
- Sunset non-openers: suppress after 90 days of no opens
- Clean list monthly with email verification (NeverBounce, ZeroBounce)

## Metrics & Optimization

### Benchmarks by Email Type
| Email Type | Open Rate | Click Rate | Unsubscribe |
|-----------|-----------|-----------|-------------|
| Welcome | 50-80% | 15-30% | < 0.5% |
| Triggered behavioral | 30-50% | 10-20% | < 0.3% |
| Promotional blast | 15-25% | 2-5% | < 0.5% |
| Win-back | 10-20% | 3-8% | Higher (OK) |
| Transactional | 60-80% | 10-15% | < 0.1% |

### A/B Testing Framework
- Test one variable at a time: subject line, sender name, send time, CTA, body copy
- Minimum sample: 1,000 per variant for statistical significance
- Run for at least 4 hours; never stop early based on early results
- Use 80/20 split (80% to winner after test period)
- Track downstream metrics, not just opens: clicks, conversions, revenue

### Revenue Attribution
```python
def calculate_email_revenue(campaign_id: str, lookback_days: int = 7) -> dict:
    """Attribute revenue to email campaigns via UTM + session tracking."""
    conversions = db.query("""
        SELECT
            e.campaign_id,
            COUNT(DISTINCT o.order_id) AS orders,
            SUM(o.revenue) AS attributed_revenue,
            SUM(o.revenue) / COUNT(DISTINCT e.recipient_id) AS revenue_per_recipient
        FROM email_sends e
        JOIN orders o ON o.user_id = e.recipient_id
            AND o.created_at BETWEEN e.sent_at AND e.sent_at + INTERVAL '%s days'
            AND o.utm_campaign = e.campaign_id
        WHERE e.campaign_id = %s
        GROUP BY 1
    """, (lookback_days, campaign_id))
    return conversions
```
