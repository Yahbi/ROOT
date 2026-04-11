---
name: SaaS Metrics
description: MRR, ARR, churn, LTV, CAC, and NRR tracking for SaaS businesses
version: "1.0.0"
author: ROOT
tags: [business, saas, metrics, MRR, churn, LTV, CAC]
platforms: [all]
---

# SaaS Metrics

Track and optimize the key metrics that determine SaaS business health and valuation.

## Revenue Metrics

### Monthly Recurring Revenue (MRR)
- **New MRR**: Revenue from new customers this month
- **Expansion MRR**: Revenue increase from existing customers (upgrades, add-ons)
- **Contraction MRR**: Revenue decrease from existing customers (downgrades)
- **Churned MRR**: Revenue lost from cancelled customers
- **Net New MRR** = New + Expansion - Contraction - Churned

### Annual Recurring Revenue (ARR)
- ARR = MRR * 12 (for consistent monthly revenue)
- Use ARR for annual contracts, MRR for monthly billing
- ARR growth rate is the primary valuation driver: >100% = elite, 50-100% = strong, <30% = struggling

## Customer Metrics

### Churn Rates
| Metric | Formula | Good Benchmark |
|--------|---------|----------------|
| Logo churn | Customers lost / Starting customers | < 5% monthly (SMB), < 1% monthly (Enterprise) |
| Revenue churn | MRR lost / Starting MRR | < 2% monthly |
| Net revenue retention | (Starting MRR + Expansion - Contraction - Churn) / Starting MRR | > 110% |

### Net Revenue Retention (NRR)
- NRR > 100% means you grow even without new customers
- Best SaaS companies: NRR 120-150% (massive expansion revenue)
- NRR < 100% means the leaky bucket is emptying faster than you fill it

## Unit Economics

### Customer Acquisition Cost (CAC)
- CAC = (Sales + Marketing spend) / New customers acquired
- Include salaries, tools, ad spend, content production costs
- Blended CAC vs paid CAC (organic excluded)

### Lifetime Value (LTV)
- LTV = ARPU / Monthly churn rate (simple formula)
- LTV = ARPU * Gross margin / Monthly churn rate (margin-adjusted)
- **LTV:CAC ratio**: target > 3:1 (return 3x the acquisition cost)
- **CAC payback period**: months to recoup CAC — target < 12 months

## Operational Metrics

### Key Benchmarks
| Metric | Seed | Series A | Series B+ |
|--------|------|----------|-----------|
| MRR | $10-50K | $50-200K | $500K+ |
| MRR growth (MoM) | 15-20% | 10-15% | 5-10% |
| Gross margin | > 60% | > 70% | > 75% |
| Burn multiple | < 3x | < 2x | < 1.5x |

### Burn Multiple
- Burn multiple = Net burn / Net new ARR
- Measures efficiency: how much cash burned per dollar of new ARR
- < 1x is exceptional (generating ARR faster than burning cash)

## Dashboard Requirements

- Real-time MRR waterfall (new, expansion, contraction, churn)
- Cohort analysis: retention curves by signup month
- LTV:CAC ratio trending over time
- Revenue breakdown by plan tier and segment
- Leading indicators: trial-to-paid conversion, activation rate, NPS
