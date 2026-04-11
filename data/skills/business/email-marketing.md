---
name: Email Marketing
description: Email sequences, deliverability, A/B testing, and segmentation strategies
version: "1.0.0"
author: ROOT
tags: [business, email, marketing, sequences, deliverability]
platforms: [all]
---

# Email Marketing

Build email campaigns that reach the inbox, engage subscribers, and drive conversions.

## Email Sequence Design

### Welcome Sequence (5-7 emails over 14 days)
1. **Immediate**: Welcome + deliver promised lead magnet + set expectations
2. **Day 2**: Your origin story or mission — build connection
3. **Day 4**: Best content piece or quick win tutorial
4. **Day 7**: Case study or social proof
5. **Day 10**: Introduce product/offer with soft CTA
6. **Day 14**: Direct offer with clear value proposition and urgency

### Nurture Sequence (ongoing)
- Weekly or bi-weekly educational content
- 80/20 rule: 80% value, 20% promotional
- Segment by engagement: highly engaged get more offers, low engaged get re-engagement

### Re-engagement Sequence
- Trigger: no opens for 60-90 days
- Email 1: "We miss you" + best recent content
- Email 2: Special offer or exclusive content
- Email 3: "Should we remove you?" (creates urgency to re-engage)
- If no response after 3 emails: move to suppression list

## Deliverability

### Technical Setup
- **SPF**: DNS TXT record authorizing your sending servers
- **DKIM**: Cryptographic signature proving email authenticity
- **DMARC**: Policy for handling failed SPF/DKIM checks (start with p=none, move to p=reject)
- **Dedicated IP**: For volume > 50K emails/month (warm it up gradually over 4 weeks)

### Sender Reputation
- Keep bounce rate < 2% (clean list quarterly)
- Keep spam complaint rate < 0.1% (easy unsubscribe, honor preferences)
- Maintain consistent sending volume (don't spike 10x overnight)
- Remove unengaged subscribers after 90 days of no opens

## Segmentation

### Segmentation Criteria
| Dimension | Segments | Use Case |
|-----------|----------|----------|
| Engagement | Active, passive, dormant | Frequency and offer type |
| Funnel stage | Subscriber, trial, customer | Content and CTA relevance |
| Source | Organic, paid, referral | Messaging tone |
| Behavior | Feature used, page visited | Product-specific content |
| Demographics | Industry, role, company size | Pain point targeting |

## A/B Testing

### What to Test (in priority order)
1. **Subject line**: Biggest impact on open rate (test 2 variants, 20% sample)
2. **Send time**: Test different days and times over 4+ weeks
3. **CTA**: Button text, color, placement
4. **Content length**: Short vs detailed
5. **Personalization**: First name, company name, dynamic content

### Testing Rules
- Test one variable at a time
- Minimum sample: 1,000 per variant (or 200 for smaller lists)
- Statistical significance: 95% confidence before declaring a winner
- Document every test result — build a playbook of what works for your audience

## Metrics

| Metric | Good | Great | Red Flag |
|--------|------|-------|----------|
| Open rate | 20-30% | > 35% | < 15% |
| Click rate | 2-5% | > 7% | < 1% |
| Unsubscribe rate | < 0.3% | < 0.1% | > 0.5% |
| Conversion rate | 1-3% | > 5% | < 0.5% |
