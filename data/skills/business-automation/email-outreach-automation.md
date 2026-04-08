---
name: Email Outreach Automation
description: Build personalized cold outreach sequences that convert without being spammy
version: "1.0.0"
author: ROOT
tags: [business-automation, email, outreach, cold-email, sequences, sales]
platforms: [all]
difficulty: intermediate
---

# Email Outreach Automation

Scale personalized outreach while maintaining deliverability and conversion rates.
The best automation feels human — no mass blasts, no generic templates.

## Email Deliverability Foundations

### Technical Setup (Required Before Sending)

1. **SPF Record**: Authorizes your email server to send for your domain
   ```
   v=spf1 include:_spf.google.com ~all
   ```

2. **DKIM**: Cryptographic signature for email authentication
   ```
   # Enable in Google Workspace/Office 365 admin → authentication
   ```

3. **DMARC**: Policy for handling authentication failures
   ```
   v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com; pct=100
   ```

4. **Warm-up domain**: New domains need 4-8 weeks of gradual sending
   - Week 1-2: 10-20 emails/day
   - Week 3-4: 50-100 emails/day
   - Week 5-6: 200-500 emails/day
   - Month 2+: Full sending volume

### Domain Health Checklist
- [ ] SPF, DKIM, DMARC all configured
- [ ] Separate sending domain (outreach.company.com) — protect main domain
- [ ] MX records configured for reply handling
- [ ] Custom tracking domain for links (track.company.com)
- [ ] Bounce rate < 2% at all times
- [ ] Unsubscribe rate < 0.1%

## Sequence Architecture

### The 7-Touch Sequence

```
Day 1:  Initial personalized email (no pitch yet)
Day 3:  Value-add follow-up (relevant content/insight)
Day 7:  Social proof + soft CTA
Day 14: Alternative angle (different pain point)
Day 21: Break-up email ("should I close your file?")
Day 30: Long-term nurture (quarterly check-in)
Day 90: Re-activation (new angle or trigger event)
```

### Email Templates

**Email 1 — Opening (Personalized, No Pitch)**
```
Subject: [Specific observation about their company]

Hi {first_name},

Noticed {specific_observation} at {company} — impressive given {market_context}.

I work with {similar_company} and {similar_company_2} on {relevant_problem_they_solve}.

Would it make sense to connect briefly?

Best,
{your_name}
```

**Email 3 — Social Proof**
```
Subject: How {competitor_or_similar_company} achieved {specific_result}

{first_name},

Thought this might be relevant: {similar_company} used our {product/approach} to
{specific_measurable_result} in {timeframe}.

Worth a 15-minute call to see if something similar might work for {company}?

{calendar_link}
```

**Email 5 — Break-Up**
```
Subject: Closing the loop

{first_name},

I've reached out a few times and haven't heard back — completely understandable,
you're probably heads-down.

I'll stop reaching out after this. If now isn't the right time for {pain_point},
no worries — I'll check back in a few months.

If you'd like to talk, here's my calendar: {link}

Either way, best of luck with {specific_company_initiative}.
```

## Personalization at Scale

### Automated Personalization Variables

```python
# Enrich leads with personalization data
from anthropic import Anthropic

client = Anthropic()

def generate_personalized_opening(lead: dict) -> str:
    """Generate a unique, relevant opening line for each prospect."""
    prompt = f"""
Generate a natural, specific opening sentence for a cold email to:
- Name: {lead['name']}
- Company: {lead['company']}
- Title: {lead['title']}
- Recent company news: {lead.get('recent_news', 'N/A')}
- LinkedIn activity: {lead.get('linkedin_activity', 'N/A')}

Requirements:
- 1 sentence only
- Specific, not generic
- Shows genuine research
- NOT flattery (no "I loved your post...")
- NOT about us — about them

Return ONLY the sentence, no explanation.
"""
    response = client.messages.create(
        model="claude-haiku-20240307",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()

# Batch personalization
def personalize_sequence(leads: list[dict], sequence_template: dict) -> list[dict]:
    personalized_emails = []
    for lead in leads:
        opening = generate_personalized_opening(lead)
        for email in sequence_template["emails"]:
            personalized = email["body"].format(
                first_name=lead["first_name"],
                company=lead["company"],
                custom_opening=opening,
                **lead.get("custom_fields", {})
            )
            personalized_emails.append({"lead_id": lead["id"], "body": personalized})
    return personalized_emails
```

## Sending Infrastructure

### Apollo.io / Instantly.ai Integration

```python
import requests

class InstantlyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.instantly.ai/api/v1"

    def create_campaign(self, name: str, from_email: str) -> dict:
        return requests.post(
            f"{self.base_url}/campaign/create",
            json={"name": name, "email_list": [from_email]},
            headers={"Authorization": f"Bearer {self.api_key}"}
        ).json()

    def add_leads(self, campaign_id: str, leads: list[dict]) -> dict:
        return requests.post(
            f"{self.base_url}/lead/add",
            json={
                "campaign_id": campaign_id,
                "leads": [{"email": l["email"], "first_name": l["first_name"],
                           "company_name": l["company"], **l.get("variables", {})}
                          for l in leads]
            },
            headers={"Authorization": f"Bearer {self.api_key}"}
        ).json()
```

## Sending Rules and Limits

```python
SENDING_RULES = {
    "max_per_day_per_mailbox": 50,       # Stay under spam thresholds
    "min_delay_between_emails_sec": 120,  # 2 minutes minimum
    "send_window_start": "09:00",         # Local time of prospect
    "send_window_end": "17:00",
    "skip_days": ["Saturday", "Sunday"],
    "max_sequence_emails": 7,
    "min_days_between_touches": 2,
    "skip_if_open_rate_below": 0.15,    # Kill campaign if not resonating
}
```

## Performance Benchmarks

| Metric | Poor | Average | Good | Excellent |
|--------|------|---------|------|-----------|
| Open rate | < 20% | 30% | 45% | > 60% |
| Reply rate | < 2% | 5% | 10% | > 15% |
| Positive reply rate | < 1% | 2-3% | 5% | > 8% |
| Meeting booked rate | < 0.5% | 1-2% | 3% | > 5% |
| Bounce rate | > 5% | 2-5% | < 2% | < 0.5% |

## Compliance Requirements

- **CAN-SPAM (USA)**: Physical mailing address required; honor opt-out within 10 days
- **CASL (Canada)**: Explicit consent required for marketing emails
- **GDPR (EU)**: Legal basis for processing; right to erasure; data minimization
- **Add unsubscribe link** to every email — automated suppression list management
- **Log consent** and source for every contact in CRM
